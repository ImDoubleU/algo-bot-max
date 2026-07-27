from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KNOWLEDGE_BASE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "knowledge_base.json"
)


class KnowledgeBaseError(RuntimeError):
    pass


def clean_knowledge_label(value: str) -> str:
    label = " ".join(str(value).split())
    while label and not label[0].isalnum():
        label = label[1:].lstrip()
    return label


class KnowledgeBaseService:
    def __init__(self, path: Path = KNOWLEDGE_BASE_PATH) -> None:
        self.path = path

    def _structure(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise KnowledgeBaseError("Не удалось загрузить базу знаний") from exc
        structure = data.get("hub_structure")
        if not isinstance(structure, dict):
            raise KnowledgeBaseError("Некорректная структура базы знаний")
        return structure

    def main_sections(self) -> list[dict[str, Any]]:
        sections = self._structure().get("main_sections") or []
        return [section for section in sections if isinstance(section, dict)]

    def section_ids(self) -> set[str]:
        structure = self._structure()
        main_ids = {
            str(section.get("id") or "")
            for section in structure.get("main_sections") or []
            if isinstance(section, dict)
        }
        subsections = structure.get("subsections") or {}
        return {section_id for section_id in main_ids if section_id} | {
            str(section_id) for section_id in subsections
        }

    def section(self, section_id: str) -> dict[str, Any] | None:
        structure = self._structure()
        for section in structure.get("main_sections") or []:
            if isinstance(section, dict) and section.get("id") == section_id:
                return section
        subsection = (structure.get("subsections") or {}).get(section_id)
        return subsection if isinstance(subsection, dict) else None
