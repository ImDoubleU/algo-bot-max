from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "video_series_manifest.json"
LOCAL_FFMPEG = (
    ROOT
    / "output"
    / ".audit-tools"
    / "imageio_ffmpeg"
    / "binaries"
    / "ffmpeg-win-x86_64-v7.1.exe"
)
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё0-9]+)*")
# The AAC master lands about 0.4 LU below the normalized PCM source.
# This pre-compensation keeps encoded masters inside the -16 +/- 0.5 LUFS window.
TARGET_LOUDNESS = -15.5
PCM_TRUE_PEAK = -3.0


def project_path(value: str) -> Path:
    return ROOT / Path(value.replace("\\", "/"))


def ffmpeg_path(configured: str) -> Path:
    candidates = (
        Path(configured) if configured else None,
        Path(os.environ["FFMPEG_EXE"]) if os.environ.get("FFMPEG_EXE") else None,
        LOCAL_FFMPEG,
    )
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise FileNotFoundError("FFmpeg was not found. Set FFMPEG_EXE or use --ffmpeg.")


def numeric_files(directory: Path, suffix: str) -> list[Path]:
    def number(path: Path) -> int:
        match = re.search(r"\d+", path.stem)
        return int(match.group()) if match else 0

    return sorted(
        (path for path in directory.iterdir() if path.suffix.casefold() == suffix.casefold()),
        key=number,
    )


def format_srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def format_vtt_time(seconds: float) -> str:
    return format_srt_time(seconds).replace(",", ".")


def format_chapter_time(seconds: float) -> str:
    total = max(0, round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def caption_chunks(text: str, max_words: int = 14) -> list[str]:
    sentences = [
        value.strip()
        for value in re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
        if value.strip()
    ]
    chunks: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        if len(words) <= max_words:
            chunks.append(sentence)
            continue
        for index in range(0, len(words), max_words):
            chunk = " ".join(words[index : index + max_words])
            if index + max_words < len(words) and chunk[-1:] not in ",;:.!?":
                chunk += "…"
            chunks.append(chunk)
    return chunks or [text.strip()]


def write_subtitles(
    narration: list[dict[str, str]],
    tracks: list[dict[str, object]],
    srt_path: Path,
    vtt_path: Path,
) -> None:
    cues: list[tuple[float, float, str]] = []
    slide_start = 0.0
    for item, track in zip(narration, tracks, strict=True):
        chunks = caption_chunks(str(item["text"]))
        audio_seconds = max(float(track["AudioSeconds"]), 0.4)
        weights = [max(len(WORD_RE.findall(chunk)), 1) for chunk in chunks]
        total_weight = sum(weights)
        cue_start = slide_start + 0.04
        spoken_end = slide_start + audio_seconds
        for index, (chunk, weight) in enumerate(zip(chunks, weights, strict=True)):
            portion = audio_seconds * weight / total_weight
            cue_end = spoken_end if index == len(chunks) - 1 else cue_start + portion
            cues.append((cue_start, max(cue_end, cue_start + 0.35), chunk))
            cue_start = cue_end
        slide_start += float(track["Duration"])

    srt_lines: list[str] = []
    vtt_lines = ["WEBVTT", ""]
    for index, (start, end, text) in enumerate(cues, start=1):
        srt_lines.extend(
            (
                str(index),
                f"{format_srt_time(start)} --> {format_srt_time(end)}",
                text,
                "",
            )
        )
        vtt_lines.extend(
            (
                f"{format_vtt_time(start)} --> {format_vtt_time(end)}",
                text,
                "",
            )
        )
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    vtt_path.write_text("\n".join(vtt_lines), encoding="utf-8")


def write_audio_master(
    tracks: list[dict[str, object]],
    target_path: Path,
) -> tuple[float, list[float]]:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    output_params: tuple[int, int, int] | None = None
    slide_durations: list[float] = []
    with wave.open(str(target_path), "wb") as output:
        for index, track in enumerate(tracks, start=1):
            source_path = Path(str(track["Path"]))
            with wave.open(str(source_path), "rb") as source:
                params = (source.getnchannels(), source.getsampwidth(), source.getframerate())
                if output_params is None:
                    output_params = params
                    output.setnchannels(params[0])
                    output.setsampwidth(params[1])
                    output.setframerate(params[2])
                elif params != output_params:
                    raise ValueError(f"Audio format mismatch on slide {index}: {params} != {output_params}")
                frames = source.readframes(source.getnframes())
                output.writeframes(frames)
                actual_frames = source.getnframes()

            assert output_params is not None
            target_frames = max(round(float(track["Duration"]) * output_params[2]), actual_frames)
            padding_frames = target_frames - actual_frames
            if padding_frames:
                output.writeframes(b"\0" * padding_frames * output_params[0] * output_params[1])
            slide_durations.append(target_frames / output_params[2])

    return sum(slide_durations), slide_durations


def ffconcat_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "'\\''")


def write_visual_concat(slides: list[Path], durations: list[float], target_path: Path) -> None:
    lines = ["ffconcat version 1.0"]
    for slide, duration in zip(slides, durations, strict=True):
        lines.append(f"file '{ffconcat_path(slide)}'")
        lines.append(f"duration {duration:.6f}")
    lines.append(f"file '{ffconcat_path(slides[-1])}'")
    target_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def escape_metadata(value: str) -> str:
    return value.replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#")


def write_chapters(
    narration: list[dict[str, str]],
    durations: list[float],
    sidecar_path: Path,
    metadata_path: Path,
) -> None:
    starts: list[float] = []
    current = 0.0
    for duration in durations:
        starts.append(current)
        current += duration
    chapters = [
        (starts[index], str(item["chapter"]))
        for index, item in enumerate(narration)
        if item.get("chapter")
    ]
    if not chapters or chapters[0][0] > 0:
        chapters.insert(0, (0.0, str(narration[0]["title"])))

    sidecar_path.write_text(
        "\n".join(f"{format_chapter_time(start)}  {title}" for start, title in chapters) + "\n",
        encoding="utf-8",
    )
    metadata = [";FFMETADATA1", "title=Algo MAX"]
    for index, (start, title) in enumerate(chapters):
        end = chapters[index + 1][0] if index + 1 < len(chapters) else current
        metadata.extend(
            (
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={round(start * 1000)}",
                f"END={round(end * 1000)}",
                f"title={escape_metadata(title)}",
            )
        )
    metadata_path.write_text("\n".join(metadata) + "\n", encoding="utf-8")


def loudnorm_filter(ffmpeg: Path, audio_path: Path) -> str:
    measurement = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-nostats",
            "-i",
            str(audio_path),
            "-af",
            f"loudnorm=I={TARGET_LOUDNESS}:TP={PCM_TRUE_PEAK}:LRA=7:print_format=json",
            "-f",
            "null",
            "NUL",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    matches = re.findall(r"\{\s*\"input_i\".*?\}", measurement.stderr, flags=re.DOTALL)
    if measurement.returncode != 0 or not matches:
        raise RuntimeError(f"Loudness analysis failed:\n{measurement.stderr[-4000:]}")
    values = json.loads(matches[-1])
    return (
        f"loudnorm=I={TARGET_LOUDNESS}:TP={PCM_TRUE_PEAK}:LRA=7:"
        f"measured_I={values['input_i']}:"
        f"measured_TP={values['input_tp']}:"
        f"measured_LRA={values['input_lra']}:"
        f"measured_thresh={values['input_thresh']}:"
        f"offset={values['target_offset']}:linear=true:print_format=summary"
    )


def normalize_audio(ffmpeg: Path, source_path: Path, target_path: Path) -> None:
    """Render loudness normalization to PCM before the lossy AAC encode."""
    audio_filter = loudnorm_filter(ffmpeg, source_path)
    target_path.unlink(missing_ok=True)
    result = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-y",
            "-i",
            str(source_path),
            "-af",
            audio_filter,
            "-c:a",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            "48000",
            str(target_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Audio normalization failed:\n{result.stderr[-4000:]}")


def verify_video_frame(ffmpeg: Path, video_path: Path) -> None:
    result = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-v",
            "error",
            "-i",
            str(video_path),
            "-map",
            "0:v:0",
            "-frames:v",
            "1",
            "-f",
            "framehash",
            "-",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    decoded_frame = re.search(r"^0,", result.stdout, flags=re.MULTILINE)
    if result.returncode != 0 or not decoded_frame:
        details = (result.stderr or result.stdout)[-4000:]
        raise RuntimeError(f"Master contains no decodable video frame:\n{details}")


def build_master(video_id: str, manifest_path: Path, ffmpeg: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        entry = next(item for item in manifest["videos"] if item["id"] == video_id)
    except StopIteration as exc:
        raise ValueError(f"Unknown video id: {video_id}") from exc

    narration = json.loads(project_path(str(entry["narration"])).read_text(encoding="utf-8"))
    slide_dir = ROOT / "output" / "video-series" / "slides" / video_id
    audio_dir = ROOT / "output" / "video-series" / "audio" / video_id
    tracks = json.loads((audio_dir / "piper-manifest.json").read_text(encoding="utf-8"))
    slides = numeric_files(slide_dir, ".png")
    if len(slides) != len(narration) or len(tracks) != len(narration):
        raise ValueError(
            f"{video_id}: slides={len(slides)}, tracks={len(tracks)}, narration={len(narration)}"
        )

    video_path = project_path(str(entry["video"]))
    srt_path = project_path(str(entry["subtitles_srt"]))
    vtt_path = project_path(str(entry["subtitles_vtt"]))
    chapters_path = project_path(str(entry["chapters"]))
    work_dir = ROOT / "output" / "video-series" / ".work" / video_id
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_master = work_dir / "audio-master.wav"
    normalized_audio = work_dir / "audio-normalized.wav"
    visual_concat = work_dir / "visual.ffconcat"
    chapter_metadata = work_dir / "chapters.ffmetadata"

    total_seconds, durations = write_audio_master(tracks, audio_master)
    write_visual_concat(slides, durations, visual_concat)
    write_subtitles(narration, tracks, srt_path, vtt_path)
    write_chapters(narration, durations, chapters_path, chapter_metadata)
    normalize_audio(ffmpeg, audio_master, normalized_audio)
    visual_filter = "scale=1920:1080:flags=lanczos,fps=25,format=yuv420p"
    if entry["kind"] == "overview":
        visual_filter = (
            "scale=1984:1116:flags=lanczos,fps=25,"
            "crop=1920:1080:x='32+32*sin(t/5)':y='18+18*cos(t/6)',"
            "format=yuv420p"
        )

    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.unlink(missing_ok=True)
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(visual_concat),
        "-i",
        str(normalized_audio),
        "-i",
        str(srt_path),
        "-f",
        "ffmetadata",
        "-i",
        str(chapter_metadata),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-map",
        "2:0",
        "-map_metadata",
        "3",
        "-map_chapters",
        "3",
        "-vf",
        visual_filter,
        "-t",
        f"{total_seconds:.6f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-r",
        "25",
        "-fps_mode",
        "cfr",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ac",
        "1",
        "-ar",
        "48000",
        "-c:s",
        "mov_text",
        "-metadata:s:s:0",
        "language=rus",
        "-metadata:s:s:0",
        "title=Русские субтитры",
        "-disposition:s:0",
        "0",
        "-movflags",
        "+faststart",
        str(video_path),
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg master failed for {video_id}:\n{result.stderr[-8000:]}")
    verify_video_frame(ffmpeg, video_path)

    summary = {
        "id": video_id,
        "slides": len(slides),
        "duration_seconds": round(total_seconds, 3),
        "video": str(video_path),
        "video_bytes": video_path.stat().st_size,
        "srt": str(srt_path),
        "vtt": str(vtt_path),
        "chapters": str(chapters_path),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a 1080p video master with subtitles and chapters")
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--ffmpeg", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_master(args.video_id, args.manifest.resolve(), ffmpeg_path(args.ffmpeg))


if __name__ == "__main__":
    main()
