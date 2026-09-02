from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINIAPP = ROOT / "app" / "web" / "static" / "miniapp"


def test_demo_students_are_active_for_role_previews() -> None:
    source = (MINIAPP / "app-core.js").read_text(encoding="utf-8")
    match = re.search(r"let students = \[(.*?)\];\s*\n\s*let accessLinks", source, re.DOTALL)

    assert match is not None
    student_block = match.group(1)
    assert student_block.count('status: "active"') == 3


def test_miniapp_static_assets_share_cache_version() -> None:
    source = (MINIAPP / "index.html").read_text(encoding="utf-8")
    versions = re.findall(r"(?:styles|app(?:-[a-z]+)?)\.js?\?v=([0-9.]+)", source)

    # CSS is captured separately because its extension is not JavaScript.
    versions.extend(re.findall(r"styles\.css\?v=([0-9.]+)", source))
    assert versions
    assert set(versions) == {"0.80.0"}
