from __future__ import annotations

import argparse
import json
import re
import wave
from pathlib import Path

from piper import PiperVoice, SynthesisConfig


TTS_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Algo MAX", "Алго Макс"),
    ("MAX ID", "идентификатор Макс"),
    ("MAX-аккаунт", "аккаунт Макс"),
    ("MAX", "Макс"),
    ("QR-код", "кью ар код"),
    ("QR-коды", "кью ар коды"),
    ("QR", "кью ар"),
    ("AC", "астрокоины"),
    ("XLSX", "файл Эксель"),
    ("CSV", "си эс ви"),
    ("Excel", "Эксель"),
    ("JPEG", "джейпег"),
    ("PNG", "пи эн джи"),
    ("WebP", "веб пи"),
    ("SKU", "артикул"),
    (" -> ", ", затем "),
)


def normalize_for_speech(text: str) -> str:
    result = " ".join(text.split())
    for source, target in TTS_REPLACEMENTS:
        result = result.replace(source, target)
    result = re.sub(r"\bN\s+строк\b", "указанное количество строк", result)
    result = re.sub(r"\s+([,.!?;:])", r"\1", result)
    return result


def synthesize_slide(
    voice: PiperVoice,
    text: str,
    output_path: Path,
    *,
    length_scale: float,
) -> float:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wav_file:
        voice.synthesize_wav(
            normalize_for_speech(text),
            wav_file,
            syn_config=SynthesisConfig(
                length_scale=length_scale,
                normalize_audio=True,
                volume=1.0,
            ),
        )

    with wave.open(str(output_path), "rb") as wav_file:
        return wav_file.getnframes() / wav_file.getframerate()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create offline Russian narration with Piper")
    parser.add_argument("--narration", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--length-scale", type=float, default=0.94)
    parser.add_argument("--slide-padding", type=float, default=0.35)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    narration = json.loads(args.narration.read_text(encoding="utf-8"))
    if not isinstance(narration, list) or not narration:
        raise ValueError("Narration JSON must contain a non-empty slide list")
    if not args.model.exists():
        raise FileNotFoundError(args.model)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for stale_track in args.output_dir.glob("slide-*.wav"):
        stale_track.unlink()

    voice = PiperVoice.load(str(args.model))
    manifest: list[dict[str, object]] = []
    for index, item in enumerate(narration, start=1):
        text = str(item.get("text") or "").strip()
        if not text:
            raise ValueError(f"Slide {index} has no narration text")
        output_path = (args.output_dir / f"slide-{index:02d}.wav").resolve()
        duration = synthesize_slide(
            voice,
            text,
            output_path,
            length_scale=args.length_scale,
        )
        manifest.append(
            {
                "Slide": index,
                "Path": str(output_path),
                "Duration": max(0.75, round(duration + args.slide_padding, 3)),
                "AudioSeconds": round(duration, 3),
                "PaddingSeconds": round(args.slide_padding, 3),
            }
        )
        print(f"[{index:02d}/{len(narration):02d}] {duration:.1f}s")

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    total_seconds = sum(float(item["AudioSeconds"]) for item in manifest)
    print(f"Created {len(manifest)} tracks, {total_seconds / 60:.1f} min")
    print(f"Manifest: {args.manifest.resolve()}")


if __name__ == "__main__":
    main()
