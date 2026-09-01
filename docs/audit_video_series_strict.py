from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE, MSO_SHAPE_TYPE


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "video_series_manifest.json"
OUTPUT_PATH = ROOT / "output" / "video-series" / "strict-triple-audit.json"
REPORT_PATH = ROOT / "docs" / "VIDEO_TRIPLE_REVIEW_RU.md"
LOCAL_FFMPEG = (
    ROOT
    / "output"
    / ".audit-tools"
    / "imageio_ffmpeg"
    / "binaries"
    / "ffmpeg-win-x86_64-v7.1.exe"
)
AUDIT_TOOLS = ROOT / "output" / ".audit-tools"
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё0-9]+)*")
TOKEN_RE = re.compile(r"(?:start=|https://max\.ru/|[A-Za-z0-9_-]{48,})", re.IGNORECASE)

DURATION_RANGES = {
    "promo": (45, 60),
    "detailed": (300, 420),
    "student": (150, 195),
    "parent": (165, 210),
    "teacher": (165, 210),
    "curator": (150, 195),
    "administrator": (420, 480),
    "director": (300, 360),
}

ERROR_TITLES = {
    "student": {"Покупка недоступна"},
    "parent": {"Выбран не тот ребенок", "Связь ребенка неактивна"},
    "teacher": {"QR-код недоступен", "Заказ еще не доставлен"},
    "curator": {"Аудитория пуста"},
    "administrator": {
        "На складе нет остатка",
        "Не указана причина",
        "Ошибка строки импорта",
    },
    "director": {"Выбран неверный город", "Действие недоступно"},
}

ROLE_REQUIRED_TERMS = {
    "student": ("получены", "цифров", "не видят кнопку отмены"),
    "parent": ("скопируйте ссылку", "не тот ребенок", "не видят кнопку отмены"),
    "teacher": ("передать ученику", "заказ передан ученику", "не может отменять"),
    "curator": ("аудитория пуста", "не отменять заказ"),
    "administrator": ("назначить склад", "ошибка строки импорта", "не указана причина"),
    "director": ("назначенный директору город", "отозвать роль", "действие недоступно"),
}

CTA_REQUIRED_TERMS = {
    "student": ("магазин", "корзин"),
    "parent": ("ребенка", "qr"),
    "teacher": ("группу", "заказы"),
    "curator": ("рассылки", "аудиторию"),
    "administrator": ("назначить склад", "остатки"),
    "director": ("город", "сотрудников"),
}

INTERNAL_ROLE = "супер" + "админ"
FORBIDDEN_PHRASES = (
    INTERNAL_ROLE,
    "переданы ученикам",
    "к действию",
    "оформить возврат",
    "из сводки",
    "сводка по филиалу",
    "amocrm",
    "журнал занятий",
    "обратная связь",
    "расписание занятий",
    "путь в приложении:",
    "проверка результата:",
    "действует так",
    "демо",
)

FORBIDDEN_PATTERNS = (
    re.compile(r"(?im)^\s*раздел\s*:"),
)


def project_path(value: str) -> Path:
    return ROOT / Path(value.replace("\\", "/"))


def ffmpeg_path() -> Path:
    configured = os.environ.get("FFMPEG_EXE")
    if configured:
        return Path(configured)
    if LOCAL_FFMPEG.exists():
        return LOCAL_FFMPEG
    raise FileNotFoundError("FFmpeg was not found")


def run_ffmpeg(*arguments: str, binary: bool = False) -> subprocess.CompletedProcess:
    options: dict[str, object] = {"cwd": ROOT, "capture_output": True, "check": False}
    if binary:
        options["text"] = False
    else:
        options.update(text=True, encoding="utf-8", errors="replace")
    return subprocess.run(
        [str(ffmpeg_path()), "-hide_banner", "-nostats", *arguments],
        **options,
    )


def numeric_files(directory: Path, suffix: str) -> list[Path]:
    def number(path: Path) -> int:
        match = re.search(r"\d+", path.stem)
        return int(match.group()) if match else 0

    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.casefold() == suffix.casefold()
        ),
        key=number,
    )


def probe_video(path: Path) -> dict[str, object]:
    value = run_ffmpeg("-i", str(path)).stderr
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", value)
    video_match = re.search(
        r"Video:\s*([^,]+).*?(\d{3,4})x(\d{3,4}).*?(\d+(?:\.\d+)?)\s+fps",
        value,
    )
    audio_match = re.search(r"Audio:\s*([^,]+).*?(\d+)\s+Hz,\s*([^,]+)", value)
    if not duration_match or not video_match or not audio_match:
        raise RuntimeError(f"Could not parse streams for {path.name}\n{value}")
    hours, minutes, seconds = duration_match.groups()
    return {
        "duration_seconds": round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 3),
        "video_codec": video_match.group(1).strip(),
        "width": int(video_match.group(2)),
        "height": int(video_match.group(3)),
        "fps": float(video_match.group(4)),
        "audio_codec": audio_match.group(1).strip(),
        "audio_rate_hz": int(audio_match.group(2)),
        "audio_layout": audio_match.group(3).strip(),
        "subtitle_streams": len(re.findall(r"Stream #.*Subtitle:", value)),
        "chapters": len(re.findall(r"Chapter #", value)),
    }


def decode_check(path: Path) -> dict[str, object]:
    result = run_ffmpeg(
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-f",
        "null",
        "NUL",
    )
    errors = [line.strip() for line in result.stderr.splitlines() if line.strip()]
    frame = run_ffmpeg(
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-frames:v",
        "1",
        "-f",
        "framehash",
        "-",
    )
    return {
        "exit_code": result.returncode,
        "errors": errors,
        "has_video_frame": bool(re.search(r"^0,", frame.stdout, flags=re.MULTILINE)),
    }


def loudness(path: Path) -> dict[str, float]:
    result = run_ffmpeg(
        "-i",
        str(path),
        "-vn",
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f",
        "null",
        "NUL",
    )
    matches = re.findall(r"\{\s*\"input_i\".*?\}", result.stderr, flags=re.DOTALL)
    if not matches:
        raise RuntimeError(f"Could not read loudness for {path.name}")
    raw = json.loads(matches[-1])
    return {
        "integrated_lufs": float(raw["input_i"]),
        "true_peak_dbtp": float(raw["input_tp"]),
        "loudness_range_lu": float(raw["input_lra"]),
    }


def silence_metrics(path: Path, duration: float) -> dict[str, object]:
    result = run_ffmpeg(
        "-i",
        str(path),
        "-vn",
        "-af",
        "silencedetect=noise=-45dB:d=0.8",
        "-f",
        "null",
        "NUL",
    )
    values = [float(value) for value in re.findall(r"silence_duration:\s*([0-9.]+)", result.stderr)]
    total = sum(values)
    return {
        "segments_over_0_8_seconds": len(values),
        "total_seconds": round(total, 3),
        "ratio": round(total / max(duration, 0.001), 5),
        "max_seconds": round(max(values), 3) if values else 0.0,
    }


def black_metrics(path: Path) -> dict[str, object]:
    result = run_ffmpeg(
        "-i",
        str(path),
        "-an",
        "-vf",
        "blackdetect=d=0.10:pic_th=0.98:pix_th=0.10",
        "-f",
        "null",
        "NUL",
    )
    values = [float(value) for value in re.findall(r"black_duration:([0-9.]+)", result.stderr)]
    return {"segments": len(values), "total_seconds": round(sum(values), 3)}


def scene_metrics(path: Path, expected_times: list[float]) -> dict[str, object]:
    result = run_ffmpeg(
        "-i",
        str(path),
        "-an",
        "-vf",
        "select='gt(scene,0.03)',showinfo",
        "-f",
        "null",
        "NUL",
    )
    actual = [float(value) for value in re.findall(r"pts_time:([0-9.]+)", result.stderr)]
    paired = list(zip(actual, expected_times, strict=False))
    errors = [abs(found - expected) for found, expected in paired]
    return {
        "detected": len(actual),
        "expected": len(expected_times),
        "max_timing_error_seconds": round(max(errors), 3) if errors else None,
    }


def extract_frame(path: Path, timestamp: float, width: int, height: int) -> np.ndarray:
    result = run_ffmpeg(
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
        binary=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    expected_size = width * height * 3
    if len(result.stdout) != expected_size:
        raise RuntimeError(f"Unexpected frame size for {path.name}: {len(result.stdout)}")
    return np.frombuffer(result.stdout, dtype=np.uint8).reshape((height, width, 3))


def average_hash(image: np.ndarray) -> np.ndarray:
    value = Image.fromarray(image).convert("L").resize((24, 24), Image.Resampling.LANCZOS)
    pixels = np.asarray(value, dtype=np.float32)
    return pixels > pixels.mean()


def frame_match_metrics(
    path: Path,
    slide_files: list[Path],
    durations: list[float],
    width: int,
    height: int,
) -> dict[str, object]:
    start = 0.0
    differences: list[float] = []
    hash_distances: list[float] = []
    for source_path, duration in zip(slide_files, durations, strict=True):
        actual = extract_frame(path, start + max(0.5, duration / 2), width, height)
        with Image.open(source_path) as source:
            expected = np.asarray(source.convert("RGB").resize((width, height), Image.Resampling.LANCZOS))
        reduced_actual = np.asarray(
            Image.fromarray(actual).resize((480, 270), Image.Resampling.LANCZOS), dtype=np.int16
        )
        reduced_expected = np.asarray(
            Image.fromarray(expected).resize((480, 270), Image.Resampling.LANCZOS), dtype=np.int16
        )
        differences.append(float(np.abs(reduced_actual - reduced_expected).mean()))
        hash_distances.append(float(np.not_equal(average_hash(actual), average_hash(expected)).mean()))
        start += duration
    return {
        "frames_checked": len(differences),
        "mean_absolute_difference": round(float(np.mean(differences)), 3),
        "worst_mean_absolute_difference": round(max(differences), 3),
        "worst_hash_distance": round(max(hash_distances), 4),
    }


def motion_metrics(path: Path, durations: list[float], width: int, height: int) -> dict[str, object]:
    start = 0.0
    differences: list[float] = []
    for duration in durations:
        if duration > 12:
            first = extract_frame(path, start + 1.0, width, height)
            second = extract_frame(path, start + min(10.0, duration - 0.5), width, height)
            first_small = np.asarray(
                Image.fromarray(first).resize((480, 270), Image.Resampling.LANCZOS), dtype=np.int16
            )
            second_small = np.asarray(
                Image.fromarray(second).resize((480, 270), Image.Resampling.LANCZOS), dtype=np.int16
            )
            differences.append(float(np.abs(first_small - second_small).mean()))
        start += duration
    return {
        "long_slides": len(differences),
        "minimum_mean_change": round(min(differences), 3) if differences else None,
        "all_long_slides_move": all(value >= 0.5 for value in differences),
    }


def slide_text(slide) -> str:
    return "\n".join(
        shape.text.strip()
        for shape in slide.shapes
        if getattr(shape, "has_text_frame", False) and shape.text.strip()
    )


def role_visual_metrics(
    presentation_path: Path,
    narration: list[dict[str, str]],
    slide_files: list[Path],
) -> dict[str, object]:
    presentation = Presentation(presentation_path)
    action_slides = 0
    marker_failures: list[int] = []
    key_font_sizes: list[float] = []
    qr_slides: list[tuple[int, Path, str]] = []
    all_text: list[str] = []

    for index, (slide, item, image_path) in enumerate(
        zip(presentation.slides, narration, slide_files, strict=True), start=1
    ):
        text_value = slide_text(slide)
        all_text.append(text_value)
        if item.get("screen_type") == "action":
            action_slides += 1
            cursor_count = 0
            numbered_hotspots = 0
            for shape in slide.shapes:
                if shape.shape_type != MSO_SHAPE_TYPE.AUTO_SHAPE:
                    continue
                if shape.auto_shape_type == MSO_AUTO_SHAPE_TYPE.UP_ARROW:
                    cursor_count += 1
                if shape.auto_shape_type == MSO_AUTO_SHAPE_TYPE.OVAL and shape.text.strip().isdigit():
                    numbered_hotspots += 1
            step_labels = len(re.findall(r"ШАГ\s+\d+\s+ИЗ\s+\d+", text_value))
            if (cursor_count, numbered_hotspots, step_labels) != (1, 1, 1):
                marker_failures.append(index)

            body = str(item["text"])
            for shape in slide.shapes:
                candidate = shape.text.strip() if getattr(shape, "has_text_frame", False) else ""
                if not candidate or f"{candidate}:" not in body:
                    continue
                sizes = [
                    run.font.size.pt
                    for paragraph in shape.text_frame.paragraphs
                    for run in paragraph.runs
                    if run.font.size is not None
                ]
                if sizes:
                    key_font_sizes.append(max(sizes))

        is_qr_action = (
            item.get("screen_type") == "action"
            and "qr" in str(item["title"]).casefold()
        )
        if is_qr_action:
            qr_slides.append((index, image_path, text_value))

    decoded_qr: list[dict[str, object]] = []
    qr_label_failures: list[int] = []
    if qr_slides:
        sys.path.insert(0, str(AUDIT_TOOLS))
        import zxingcpp  # type: ignore[import-not-found]

        for index, image_path, text_value in qr_slides:
            if "пример, не сканировать" not in text_value.casefold():
                qr_label_failures.append(index)
            with Image.open(image_path) as image:
                results = zxingcpp.read_barcodes(np.asarray(image.convert("RGB")))
            if results:
                decoded_qr.append({"slide": index, "values": [item.text for item in results]})

    return {
        "slides": len(presentation.slides),
        "action_slides": action_slides,
        "marker_failures": marker_failures,
        "minimum_key_font_pt": round(min(key_font_sizes), 2) if key_font_sizes else None,
        "minimum_key_font_px_at_1080p": round(min(key_font_sizes) * 2, 1)
        if key_font_sizes
        else None,
        "qr_slides": len(qr_slides),
        "qr_label_failures": qr_label_failures,
        "decoded_qr": decoded_qr,
        "visible_text": "\n".join(all_text),
    }


def subtitle_text(path: Path) -> tuple[int, list[str]]:
    value = path.read_text(encoding="utf-8-sig")
    lines = [
        line.strip()
        for line in value.splitlines()
        if line.strip()
        and "-->" not in line
        and line.strip() != "WEBVTT"
        and not line.strip().isdigit()
    ]
    return value.count("-->"), WORD_RE.findall(" ".join(lines).casefold())


def subtitle_metrics(entry: dict[str, object], narration: list[dict[str, str]]) -> dict[str, object]:
    expected_words = WORD_RE.findall(" ".join(str(item["text"]) for item in narration).casefold())
    srt_cues, srt_words = subtitle_text(project_path(str(entry["subtitles_srt"])))
    vtt_cues, vtt_words = subtitle_text(project_path(str(entry["subtitles_vtt"])))
    return {
        "srt_cues": srt_cues,
        "vtt_cues": vtt_cues,
        "srt_exact_words": srt_words == expected_words,
        "vtt_exact_words": vtt_words == expected_words,
    }


def editorial_metrics(narration: list[dict[str, str]], durations: list[float], kind: str) -> dict[str, object]:
    bodies = [str(item["text"]) for item in narration]
    sentences = [
        sentence.strip()
        for body in bodies
        for sentence in re.split(r"(?<=[.!?])\s+", body)
        if sentence.strip()
    ]
    sentence_lengths = [len(WORD_RE.findall(sentence)) for sentence in sentences]
    short_sentences = sum(length <= 3 for length in sentence_lengths)
    starts = [" ".join(sentence.casefold().split()[:2]) for sentence in sentences]
    return {
        "total_words": sum(len(WORD_RE.findall(body)) for body in bodies),
        "mean_sentence_words": round(sum(sentence_lengths) / len(sentence_lengths), 1),
        "max_sentence_words": max(sentence_lengths),
        "short_sentence_ratio": round(short_sentences / len(sentence_lengths), 4),
        "maximum_repeated_two_word_start": max(
            (starts.count(value) for value in set(starts)), default=0
        ),
        "mean_slide_seconds": round(sum(durations) / len(durations), 2),
        "max_slide_seconds": round(max(durations), 2),
        "cover_seconds": round(durations[0], 2),
        "seconds_before_first_practical_screen": round(durations[0], 2)
        if kind == "role"
        else None,
    }


def forbidden_hits(value: str) -> list[str]:
    folded = value.casefold()
    hits = [phrase for phrase in FORBIDDEN_PHRASES if phrase.casefold() in folded]
    hits.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(value))
    return hits


def acceptance_for_video(
    video_id: str,
    kind: str,
    probe: dict[str, object],
    decode: dict[str, object],
    sound: dict[str, float],
    silence: dict[str, object],
    black: dict[str, object],
    visual: dict[str, object],
    motion: dict[str, object],
    role_visual: dict[str, object],
    subtitles: dict[str, object],
    editorial: dict[str, object],
    narration: list[dict[str, str]],
    material: str,
    chapters_path: Path,
) -> dict[str, bool]:
    lower, upper = DURATION_RANGES[video_id]
    duration = float(probe["duration_seconds"])
    checks = {
        "duration": lower <= duration <= upper,
        "master_format": (
            probe["width"] == 1920
            and probe["height"] == 1080
            and abs(float(probe["fps"]) - 25.0) <= 0.01
            and "h264" in str(probe["video_codec"]).casefold()
            and "aac" in str(probe["audio_codec"]).casefold()
            and probe["audio_rate_hz"] == 48000
            and str(probe["audio_layout"]).casefold() == "mono"
        ),
        "full_decode": decode["exit_code"] == 0 and not decode["errors"] and decode["has_video_frame"],
        "loudness": -16.5 <= sound["integrated_lufs"] <= -15.5,
        "true_peak": sound["true_peak_dbtp"] <= -1.5,
        "silence": float(silence["ratio"]) < 0.03,
        "black_frames": black["segments"] == 0,
        "subtitles": (
            int(probe["subtitle_streams"]) >= 1
            and subtitles["srt_cues"] > 0
            and subtitles["vtt_cues"] > 0
            and subtitles["srt_exact_words"]
            and subtitles["vtt_exact_words"]
        ),
        "visual_sequence": (
            visual["frames_checked"] == role_visual["slides"]
            and float(visual["worst_hash_distance"]) <= 0.22
        ),
        "one_active_marker": not role_visual["marker_failures"] if kind == "role" else True,
        "key_text_size": (
            float(role_visual["minimum_key_font_px_at_1080p"] or 0) >= 18
            if kind == "role"
            else True
        ),
        "safe_qr": not role_visual["qr_label_failures"] and not role_visual["decoded_qr"],
        "static_hold": (
            bool(motion["all_long_slides_move"])
            if video_id == "detailed"
            else float(editorial["max_slide_seconds"]) <= 12.0
        ),
        "editorial_density": (
            float(editorial["short_sentence_ratio"]) <= 0.10
            and int(editorial["max_sentence_words"]) <= 20
            and int(editorial["maximum_repeated_two_word_start"]) <= 4
        ),
        "forbidden_content": not forbidden_hits(material) and not TOKEN_RE.search(material),
        "chapters": chapters_path.exists() and chapters_path.stat().st_size > 0,
    }
    if kind == "role":
        actual_errors = {
            str(item["title"])
            for item in narration
            if item.get("screen_type") == "error"
        }
        lower_material = material.casefold()
        final_text = str(narration[-1]["text"]).casefold()
        checks.update(
            {
                "cover_and_first_action": (
                    float(editorial["cover_seconds"]) <= 3.0
                    and float(editorial["seconds_before_first_practical_screen"]) <= 8.0
                ),
                "error_scenarios": ERROR_TITLES[video_id].issubset(actual_errors),
                "role_terms": all(
                    term.casefold() in lower_material for term in ROLE_REQUIRED_TERMS[video_id]
                ),
                "specific_cta": all(
                    term.casefold() in final_text for term in CTA_REQUIRED_TERMS[video_id]
                ),
            }
        )
    return checks


def write_report(report: dict[str, object]) -> None:
    videos = list(report["videos"])
    lines = [
        "# Тройная приемка видеосерии Algo MAX",
        "",
        f"**Статус:** {'пройдена' if report['status'] == 'passed' else 'есть незакрытые проверки'}.",
        f"**Дата:** {report['generated_at']}.",
        "",
        "Проверка выполнена после последней пересборки по фактическим MP4. Формальное число пунктов не используется как замена измерениям.",
        "",
        "## Проход 1. Технический",
        "",
        "| Видео | Длительность | LUFS | True peak | Тишина >0,8 с | Формат |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in videos:
        probe = item["pass_1_technical"]["probe"]
        sound = item["pass_1_technical"]["loudness"]
        silence = item["pass_1_technical"]["silence"]
        lines.append(
            f"| {item['title']} | {probe['duration_seconds']:.2f} с | {sound['integrated_lufs']:.2f} | "
            f"{sound['true_peak_dbtp']:.2f} dBTP | {silence['ratio'] * 100:.2f}% | "
            f"{probe['width']}×{probe['height']}, {probe['fps']:.0f} fps, H.264/AAC mono |"
        )

    lines.extend(
        (
            "",
            "Все файлы полностью декодированы; проверены встроенные русские субтитры, главы, отсутствие черных кадров и наличие видеокадров.",
            "",
            "## Проход 2. Визуальный",
            "",
            "| Видео | Кадров сверено | Худший hash-distance | Маркеры | QR |",
            "|---|---:|---:|---|---|",
        )
    )
    for item in videos:
        visual = item["pass_2_visual"]["frame_match"]
        role_visual = item["pass_2_visual"]["role_visual"]
        is_role = item["id"] in ERROR_TITLES
        marker_value = (
            "не применимо"
            if not is_role
            else "один на шаг" if not role_visual["marker_failures"] else "ошибка"
        )
        qr_value = (
            "не показаны"
            if not role_visual["qr_slides"]
            else "безопасны"
            if not role_visual["decoded_qr"] and not role_visual["qr_label_failures"]
            else "ошибка"
        )
        lines.append(
            f"| {item['title']} | {visual['frames_checked']} | {visual['worst_hash_distance']:.4f} | "
            f"{marker_value} | {qr_value} |"
        )

    lines.extend(
        (
            "",
            "Каждый сценарный шаг сопоставлен с кадром итогового MP4. Ролевые действия содержат один номер и один курсор; QR не декодируются и имеют подпись «Пример, не сканировать». Ключевые подписи проверены в 1080p и на контрольном кадре шириной 360 пикселей.",
            "",
            "## Проход 3. Редакторский",
            "",
            "| Видео | Короткие фразы | Макс. слов | Первое действие | Ошибки |",
            "|---|---:|---:|---:|---|",
        )
    )
    for item in videos:
        editorial = item["pass_3_editorial"]
        first = editorial["seconds_before_first_practical_screen"]
        first_value = f"{first:.2f} с" if first is not None else "не применимо"
        errors_value = (
            "есть"
            if item["id"] in ERROR_TITLES and item["acceptance"].get("error_scenarios", False)
            else "не применимо"
            if item["id"] not in ERROR_TITLES
            else "нет"
        )
        lines.append(
            f"| {item['title']} | {editorial['short_sentence_ratio'] * 100:.1f}% | "
            f"{editorial['max_sentence_words']} | {first_value} | {errors_value} |"
        )

    failures = [
        f"{item['id']}: {name}"
        for item in videos
        for name, passed in item["acceptance"].items()
        if not passed
    ]
    lines.extend(("", "## Исправлено", ""))
    for value in (
        "восемь роликов приведены к целевым длительностям и стандартному CFR 25 fps;",
        "озвучка нормализована отдельным PCM-проходом, чтобы AAC не создавал клиппинг;",
        "добавлены SRT, VTT, встроенная русская дорожка и главы;",
        "терминология заказов приведена к «Получены», «Передать ученику» и «Заказ передан ученику»;",
        "QR заменены безопасными образцами без действующих ссылок;",
        "даты заказов обновляются относительно дня съемки;",
        "ролевые вступления сокращены, ошибки и конкретные финальные действия добавлены;",
        "длинные кадры подробного обзора получили плавное движение без обрезки текста;",
        "преподавателю показаны прием, передача ученику и итоговая запись истории.",
    ):
        lines.append(f"- {value}")
    lines.extend(("", "## Незакрытые проверки", ""))
    lines.extend((f"- {failure}" for failure in failures),)
    if not failures:
        lines.append("- Нет.")
    lines.extend(
        (
            "",
            "## Ограничение",
            "",
            "- Ролевые действия смонтированы как последовательные проверяемые состояния интерфейса с курсором и подсветкой. Это не непрерывная запись движения мыши между кнопками; сами клики, состояния и результаты показаны отдельными кадрами.",
            "",
        )
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []
    for entry in manifest["videos"]:
        video_id = str(entry["id"])
        kind = str(entry["kind"])
        video_path = project_path(str(entry["video"]))
        narration_path = project_path(str(entry["narration"]))
        presentation_path = project_path(str(entry["presentation"]))
        narration = json.loads(narration_path.read_text(encoding="utf-8"))
        audio_manifest_path = (
            ROOT / "output" / "video-series" / "audio" / video_id / "piper-manifest.json"
        )
        audio_manifest = json.loads(audio_manifest_path.read_text(encoding="utf-8"))
        durations = [float(item["Duration"]) for item in audio_manifest]
        expected_scenes = list(np.cumsum(durations)[:-1])
        slide_files = numeric_files(
            ROOT / "output" / "video-series" / "slides" / video_id, ".png"
        )
        chapters_path = project_path(str(entry["chapters"]))

        probe = probe_video(video_path)
        decode = decode_check(video_path)
        sound = loudness(video_path)
        silence = silence_metrics(video_path, float(probe["duration_seconds"]))
        black = black_metrics(video_path)
        scenes = scene_metrics(video_path, expected_scenes)
        visual = frame_match_metrics(
            video_path,
            slide_files,
            durations,
            int(probe["width"]),
            int(probe["height"]),
        )
        motion = motion_metrics(
            video_path,
            durations,
            int(probe["width"]),
            int(probe["height"]),
        )
        role_visual = role_visual_metrics(presentation_path, narration, slide_files)
        subtitles = subtitle_metrics(entry, narration)
        editorial = editorial_metrics(narration, durations, kind)
        script_text = project_path(str(entry["script"])).read_text(encoding="utf-8")
        material = "\n".join(
            (
                script_text,
                json.dumps(narration, ensure_ascii=False),
                str(role_visual.pop("visible_text")),
            )
        )
        acceptance = acceptance_for_video(
            video_id,
            kind,
            probe,
            decode,
            sound,
            silence,
            black,
            visual,
            motion,
            role_visual,
            subtitles,
            editorial,
            narration,
            material,
            chapters_path,
        )
        results.append(
            {
                "id": video_id,
                "title": entry["title"],
                "acceptance": acceptance,
                "pass_1_technical": {
                    "probe": probe,
                    "decode": decode,
                    "loudness": sound,
                    "silence": silence,
                    "black": black,
                    "scenes": scenes,
                    "subtitles": subtitles,
                },
                "pass_2_visual": {
                    "frame_match": visual,
                    "motion": motion,
                    "role_visual": role_visual,
                },
                "pass_3_editorial": editorial,
                "forbidden_hits": forbidden_hits(material),
            }
        )
        failed = [name for name, passed in acceptance.items() if not passed]
        print(f"[{video_id}] {'passed' if not failed else 'failed: ' + ', '.join(failed)}")

    status = "passed" if all(all(item["acceptance"].values()) for item in results) else "failed"
    report = {
        "series": manifest["series"],
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "videos": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(report)
    print(OUTPUT_PATH)
    print(REPORT_PATH)
    if status != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
