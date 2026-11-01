"""Build annotated H.264/PNG/WebVTT guides; never operates a signed session."""

import argparse
import base64
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from html import escape
from pathlib import Path

import imageio_ffmpeg
from capture import CACHE, ROOT, Capture, write_audit
from playwright.sync_api import sync_playwright
from scenarios import FIXED_TARGETS, TOP, definitions
from screens import SCREENS

HERE = Path(__file__).parent
OUT = ROOT / "app/web/static/miniapp/assets/help/guides"
CATALOG = ROOT / "app/web/static/miniapp/app-help-media-catalog.js"
NODE = os.environ.get(
    "HELP_MEDIA_NODE",
    "C:/Users/dibot/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe",
)


def faq():
    return json.loads(
        subprocess.check_output([NODE, str(HERE / "extract_faq.cjs")], cwd=ROOT, encoding="utf-8")
    )


def required(items):
    # The fallback only supports preparing assets before the metadata agent lands.
    explicit = any("video" in item for item in items)
    return [x for x in items if x.get("video") is True or (not explicit and x.get("steps"))]


def audiences(item):
    if "audiences" in item:
        return item["audiences"]
    roles = item.get("roles", [])
    return roles if roles else ["parent", "student", "staff"]


def id_for(question):
    legacy = {TOP[0][4]: "parent", TOP[1][4]: "student", TOP[-1][4]: "connections"}
    return legacy.get(question, "faq-" + hashlib.sha1(question.encode()).hexdigest()[:12])


def timestamp(seconds):
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}"


def short_title(text):
    first = re.split(r"[.!?] |: ", text)[0]
    if first.count("«") > first.count("»"):
        first = first.rsplit("«", 1)[0].strip()
    words = first.split()
    if len(words) > 7:
        words = words[:7]
        while words[-1].lower() in {"и", "или", "в", "на", "по", "с", "к", "для", "из"}:
            words.pop()
        first = " ".join(words).rstrip("«,:;") + "..."
        if first.count("«") > first.count("»"):
            first = first.replace("...", "»...")
    return first.rstrip(".")


def captions_for(guide):
    lines = ["WEBVTT", ""]
    for index, step in enumerate(guide["timeline"]):
        lines.extend(
            [
                str(index + 1),
                f"{timestamp(step['time'])} --> {timestamp(step['time'] + step['duration'])}",
                escape(step["text"], quote=False),
                "",
            ]
        )
    return "\n".join(lines)


def source_fingerprint():
    fingerprint = hashlib.sha256()
    static = ROOT / "app/web/static/miniapp"
    sources = [
        path for path in sorted(static.glob("*.js")) if path.name != "app-help-media-catalog.js"
    ] + sorted(static.glob("*.css"))
    sources += [
        static / "index.html",
        HERE / "capture.py",
        HERE / "screens.py",
        HERE / "external.py",
        HERE / "assets/parent-invitation.png",
    ]
    sources += sorted((HERE / "templates").glob("*"))
    for source in sources:
        fingerprint.update(str(source.relative_to(ROOT)).encode())
        fingerprint.update(source.read_bytes())
    return fingerprint.hexdigest()


def compile_item(item, definition):
    video_steps = definition.get("video_steps")
    if not video_steps:
        raise ValueError("Missing focused editorial video plan: " + item["question"])
    steps = [step["text"] for step in video_steps]
    shots = [FIXED_TARGETS.get(step["shot"], step["shot"]) for step in video_steps]
    audience = audiences(item)
    family = bool({"parent", "student"} & set(audience))
    support_scene = (
        "supportstaff"
        if not family
        else ("supportstudent" if audience == ["student"] else "support")
    )
    shots = [
        s.replace("support@", support_scene + "@").replace(
            'supportrole@[data-support-role="parent"]', "supportrole@.support-role-picker"
        )
        for s in shots
    ]
    if family:
        staff = [
            s
            for s in shots
            if s.split("@")[0] in SCREENS
            and SCREENS[s.split("@")[0]].role not in ("parent", "student", "public")
        ]
        if staff:
            raise ValueError(f"{item['question']}: family audience contains staff screen: {staff}")
    timeline = []
    time = 0
    for index, (text, shot) in enumerate(zip(steps, shots, strict=True)):
        duration = min(13, max(5, math.ceil((len(text) / 23 + 1.5) * 4) / 4))
        timeline.append(
            {
                "time": time,
                "duration": duration,
                "title": short_title(text),
                "text": text,
                "shot": shot,
                "action": video_steps[index].get("action", "observe"),
            }
        )
        time += duration
    return {
        "id": id_for(item["question"]),
        "title": item["question"],
        "duration": time,
        "timeline": timeline,
    }


def encode(path, frames, duration):
    destination = path
    path = CACHE / (path.stem + ".render.mp4")
    manifest = CACHE / (path.stem + "-concat.txt")
    lines = []
    for frame, hold in frames:
        lines.extend([f"file '{frame.as_posix()}'", f"duration {hold:.3f}"])
    lines.append(f"file '{frames[-1][0].as_posix()}'")
    manifest.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-vf",
            "fps=12",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            "-t",
            str(duration),
            str(path),
        ],
        check=True,
    )
    if path.stat().st_size >= 1000000:
        raise ValueError(f"{path.name} exceeds 1 MB: {path.stat().st_size}")
    path.replace(destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate all definitions, screens and targets without encoding",
    )
    parser.add_argument("--only", help="Question substring or asset id for iterative builds")
    parser.add_argument("--fresh", action="store_true", help="Ignore cached source shots")
    parser.add_argument(
        "--staff-only",
        action="store_true",
        help="Build the independently owned staff batch; final publication still requires all FAQs",
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    items = required(faq())
    defs = definitions()
    if not args.staff_only:
        from scenario_family import family_definitions

        defs.update(family_definitions(items))
    from review import apply_reviews

    defs = apply_reviews(items, defs)
    for definition in defs.values():
        definition["shots"] = [FIXED_TARGETS.get(shot, shot) for shot in definition["shots"]]
    compiled, errors = {}, []
    for item in items:
        if args.staff_only and {"parent", "student"} & set(audiences(item)):
            continue
        q = item["question"]
        if args.only and args.only not in q and args.only != id_for(q):
            continue
        try:
            if q not in defs:
                raise ValueError("Missing scenario: " + q)
            compiled[q] = compile_item(item, defs[q])
        except Exception as error:
            errors.append(str(error))
    (CACHE / "definition-errors.json").write_text(
        json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"Required {len(items)}, compiled {len(compiled)}, definition errors {len(errors)}",
        flush=True,
    )
    for error in errors:
        print("DEFINITION", error, flush=True)
    selected = {
        q: g for q, g in compiled.items() if not args.only or args.only in q or args.only == g["id"]
    }
    previous = {}
    if CATALOG.exists():
        previous = json.loads(
            subprocess.check_output(
                [NODE, str(HERE / "extract_catalog.cjs"), str(CATALOG)],
                encoding="utf-8",
            )
        )["catalog"]
    review_report = {
        "required": len(items),
        "reviewed": len(compiled),
        "records": [
            {
                "question": question,
                "review_note": defs[question]["review_note"],
                "before_duration": previous.get(question, {}).get("duration"),
                "duration": guide["duration"],
                "steps": guide["timeline"],
            }
            for question, guide in compiled.items()
        ],
    }
    (CACHE / "editorial-review.json").write_text(
        json.dumps(review_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    shots = sorted(set(s["shot"] for g in selected.values() for s in g["timeline"]))
    cache_file = CACHE / "shots.json"
    fingerprint_file = CACHE / "source-fingerprint.txt"
    current_fingerprint = source_fingerprint()
    sources_changed = (
        not fingerprint_file.exists() or fingerprint_file.read_text() != current_fingerprint
    )
    captured = (
        {}
        if args.fresh or sources_changed or not cache_file.exists()
        else json.loads(cache_file.read_text(encoding="utf-8"))
    )
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel="msedge", headless=True)
        capture = Capture(browser)
        inventories = {}
        for position, spec in enumerate(shots, start=1):
            if spec in captured and Path(captured[spec]["path"]).exists() and not args.check:
                continue
            try:
                record = capture.shot(spec)
                captured[spec] = record
                name = spec.split("@")[0]
                if name not in inventories:
                    inventories[name] = capture.page.locator(
                        "button,input,select,textarea,summary,[id]"
                    ).evaluate_all(
                        'els=>els.filter(e=>e.getClientRects().length).map(e=>({tag:e.tagName,id:e.id,attrs:[...e.attributes].filter(a=>a.name.startsWith("data-")||["name","type","aria-label"].includes(a.name)).map(a=>[a.name,a.value]),text:(e.innerText||e.title||e.placeholder||"").slice(0,100)}))'
                    )
            except Exception as error:
                message = spec + ": " + str(error).splitlines()[0]
                errors.append(message)
                print("TARGET", message, flush=True)
            if position % 25 == 0 or position == len(shots):
                print(f"Checked sources {position}/{len(shots)}", flush=True)
        cache_file.write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")
        (CACHE / "control-map.json").write_text(
            json.dumps(inventories, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        write_audit(capture, [captured[s] for s in shots if s in captured])
        capture.close()
        if not errors:
            fingerprint_file.write_text(current_fingerprint)
        if args.check:
            (CACHE / "errors.json").write_text(
                json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                f"Validated targets {len(captured)}/{len(shots)}; errors {len(errors)}", flush=True
            )
            browser.close()
            return 1 if errors else 0
        if errors:
            browser.close()
            return 1
        scene = browser.new_page(viewport={"width": 960, "height": 720}, device_scale_factor=1)
        scene.goto((HERE / "templates/scene.html").as_uri())
        build_records = []
        completed_file = CACHE / "completed.json"
        completed = (
            json.loads(completed_file.read_text(encoding="utf-8"))
            if completed_file.exists()
            else {}
        )
        for q, guide in selected.items():
            for step in guide["timeline"]:
                if step["action"] == "click" and not captured[step["shot"]].get("clickable"):
                    raise ValueError(q + ": click annotation targets a non-clickable element")
            signature = hashlib.sha256(
                json.dumps(guide, ensure_ascii=False, sort_keys=True).encode()
            )
            signature.update((HERE / "templates/scene.html").read_bytes())
            for step in guide["timeline"]:
                signature.update(Path(captured[step["shot"]]["path"]).read_bytes())
            fingerprint = signature.hexdigest()
            if completed.get(guide["id"]) == fingerprint and all(
                (OUT / (guide["id"] + ext)).exists() for ext in (".mp4", ".png", ".vtt")
            ):
                (OUT / (guide["id"] + ".vtt")).write_text(captions_for(guide), encoding="utf-8")
                print("CACHED", guide["id"], q, flush=True)
                continue
            frames = []
            for index, step in enumerate(guide["timeline"]):
                source = captured[step["shot"]]
                data = {
                    **source,
                    "image": "data:image/png;base64,"
                    + base64.b64encode(Path(source["path"]).read_bytes()).decode(),
                    "name": q,
                    "index": index + 1,
                    "total": len(guide["timeline"]),
                    "title": step["title"],
                    "text": step["text"],
                    "result": step.get("result", False),
                    "action": step["action"],
                }
                scene.evaluate("setScene", data)
                if not scene.evaluate("textFits()"):
                    raise ValueError(q + ": text overflows scene")
                phases = range(4) if step["action"] == "click" else (3,)
                for phase in phases:
                    scene.evaluate("setPhase", phase)
                    frame = CACHE / f"{guide['id']}-{index}-{phase}.png"
                    scene.screenshot(path=str(frame), animations="disabled")
                    hold = (0.16 if phase < 3 else step["duration"] - 0.48)
                    frames.append((frame, hold if step["action"] == "click" else step["duration"]))
                    if index == 0 and phase == 3:
                        scene.screenshot(path=str(OUT / (guide["id"] + ".png")))
            encode(OUT / (guide["id"] + ".mp4"), frames, guide["duration"])
            (OUT / (guide["id"] + ".vtt")).write_text(captions_for(guide), encoding="utf-8")
            completed[guide["id"]] = fingerprint
            completed_file.write_text(json.dumps(completed, indent=2), encoding="utf-8")
            build_records.append(
                {
                    "id": guide["id"],
                    "question": q,
                    "duration": guide["duration"],
                    "bytes": (OUT / (guide["id"] + ".mp4")).stat().st_size,
                    "shots": [s["shot"] for s in guide["timeline"]],
                }
            )
            print(f"BUILT {guide['id']} {guide['duration']}s {q}", flush=True)
        browser.close()
    # Never publish a partial catalog referencing missing files.
    missing = [
        g["id"]
        for g in compiled.values()
        if any(not (OUT / (g["id"] + ext)).exists() for ext in (".mp4", ".png", ".vtt"))
    ]
    publish = not missing and not args.only and not args.staff_only and len(compiled) == len(items)
    if publish:
        catalog = {
            q: {k: v for k, v in g.items() if k != "timeline"}
            | {"steps": [[s["time"], s["title"], s["text"]] for s in g["timeline"]]}
            for q, g in compiled.items()
        }
        top = [
            {"id": i, "label": label, "icon": icon, "audiences": aud, "question": q}
            for i, label, icon, aud, q in TOP
            if q in catalog
        ]
        CATALOG.write_text(
            "// Generated by tools/help_media/build.py. Do not edit.\n"
            "const HELP_MEDIA_CATALOG = Object.freeze("
            + json.dumps(catalog, ensure_ascii=False, indent=2)
            + ");\n\nconst HELP_TOP_GUIDES = Object.freeze("
            + json.dumps(top, ensure_ascii=False, indent=2)
            + ");\n",
            encoding="utf-8",
        )
    (CACHE / "build-report.json").write_text(
        json.dumps(
            {"required": len(items), "built_now": build_records, "missing_assets": missing},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"Built {len(build_records)}; missing assets {len(missing)}; catalog published {publish}",
        flush=True,
    )
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
