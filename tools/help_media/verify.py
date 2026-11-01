"""Verify the deliverable against live-on-disk FAQ metadata, never the backend."""

import argparse
import hashlib
import json
import re
import subprocess
import sys

import imageio_ffmpeg
from build import CATALOG, HERE, NODE, OUT, audiences, compile_item, faq, required
from PIL import Image
from review import apply_reviews
from scenario_family import family_definitions
from scenarios import FIXED_TARGETS, definitions
from screens import SCREENS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--decode", action="store_true")
    args = parser.parse_args()
    payload = json.loads(
        subprocess.check_output(
            [NODE, str(HERE / "extract_catalog.cjs"), str(CATALOG)], encoding="utf-8"
        )
    )
    all_items = faq()
    items = required(all_items)
    definitions_by_q = definitions()
    definitions_by_q.update(family_definitions(items))
    definitions_by_q = apply_reviews(items, definitions_by_q)
    errors, records = [], []
    catalog = payload["catalog"]
    expected = {item["question"] for item in items}
    if set(catalog) != expected:
        errors.append(
            {"missing": sorted(expected - set(catalog)), "extra": sorted(set(catalog) - expected)}
        )
    ids = [record["id"] for record in catalog.values()]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate asset ids: dedicated question clips expected")
    for item in items:
        q = item["question"]
        if q not in catalog:
            continue
        definition = dict(definitions_by_q[q])
        definition["shots"] = [FIXED_TARGETS.get(s, s) for s in definition["shots"]]
        compiled = compile_item(item, definition)
        record = catalog[q]
        expected_steps = [[s["time"], s["title"], s["text"]] for s in compiled["timeline"]]
        if record["duration"] != compiled["duration"] or record["steps"] != expected_steps:
            errors.append(q + ": catalog differs from current scenario/FAQ")
        files = {}
        for ext in (".mp4", ".png", ".vtt"):
            path = OUT / (record["id"] + ext)
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(str(path) + ": missing/empty")
                continue
            files[ext] = {
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        png = OUT / (record["id"] + ".png")
        if png.exists():
            with Image.open(png) as poster:
                if poster.size != (960, 720):
                    errors.append(q + ": wrong poster dimensions")
                red_pixels = sum(
                    r > 180 and g < 80 and b < 100 for r, g, b in poster.convert("RGB").getdata()
                )
                if red_pixels < 80:
                    errors.append(q + ": no substantial red annotation")
        vtt = OUT / (record["id"] + ".vtt")
        if vtt.exists():
            text = vtt.read_text(encoding="utf-8")
            if not text.startswith("WEBVTT\n") or text.count(" --> ") != len(record["steps"]):
                errors.append(q + ": invalid caption count")
        video = OUT / (record["id"] + ".mp4")
        actual_duration = None
        if video.exists():
            if video.stat().st_size >= 1000000:
                errors.append(q + ": video exceeds 1 MB")
            command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(video)]
            command += ["-f", "null", "-"] if args.decode else []
            probe = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
            if match:
                h, m, s = map(float, match.groups())
                actual_duration = h * 3600 + m * 60 + s
                if abs(actual_duration - record["duration"]) > 0.15:
                    errors.append(q + ": duration mismatch")
            else:
                errors.append(q + ": unreadable video metadata")
            if (
                "Video: h264" not in probe.stderr
                or "960x720" not in probe.stderr
                or "Audio:" in probe.stderr
            ):
                errors.append(q + ": wrong video codec, size or unexpected audio")
            if args.decode and probe.returncode:
                errors.append(q + ": decode failed")
        roles = sorted(
            {
                SCREENS[s["shot"].split("@")[0]].role
                if s["shot"].split("@")[0] in SCREENS
                else "public"
                for s in compiled["timeline"]
            }
        )
        if {"parent", "student"} & set(audiences(item)) and set(roles) - {
            "parent",
            "student",
            "public",
        }:
            errors.append(q + ": staff scene in family-visible clip")
        records.append(
            {
                "question": q,
                "id": record["id"],
                "audiences": audiences(item),
                "scene_roles": roles,
                "duration": record["duration"],
                "decoded_duration": actual_duration,
                "chapters": len(record["steps"]),
                "files": files,
                "shots": [s["shot"] for s in compiled["timeline"]],
                "review_note": definition["review_note"],
            }
        )
    for top in payload["top"]:
        if top["question"] not in catalog or "staff" not in top["audiences"]:
            errors.append("Invalid top guide: " + top["id"])
        item = next((x for x in items if x["question"] == top["question"]), {})
        if set(top["audiences"]) - {"staff"} - set(item.get("audiences", [])):
            errors.append("Top guide audience exceeds FAQ audience: " + top["id"])
    report = {
        "faq_total": len(all_items),
        "required": len(items),
        "catalog": len(catalog),
        "dedicated_clips": len(set(ids)),
        "top_guides": len(payload["top"]),
        "decode_checked": args.decode,
        "video_bytes": sum(r["files"].get(".mp4", {}).get("bytes", 0) for r in records),
        "errors": errors,
        "records": records,
    }
    (HERE / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "records"}, ensure_ascii=False, indent=2
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
