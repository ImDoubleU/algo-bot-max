from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import build_video_series as video


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "SCREENSHOT_REGISTER_RU.md"


def main() -> None:
    specs = video.all_visual_specs()
    role_usage: dict[str, list[str]] = defaultdict(list)
    for role in video.ROLE_VIDEOS:
        for asset in role.assets:
            role_usage[asset].append(role.role)

    lines = [
        "# Реестр скриншотов Algo MAX",
        "",
        "Редакция 7, интерфейс 0.86.2. Все изображения получены из локального безопасного режима текущего приложения; рабочая база не изменялась.",
        "",
        "| Файл | Раздел и состояние | Путь на экране | Формат | Где используется |",
        "|---|---|---|---|---|",
    ]
    for asset, spec in sorted(specs.items(), key=lambda item: (item[1].section, item[1].title, item[0])):
        usage = ["Полное руководство", *role_usage.get(asset, [])]
        lines.append(
            f"| `{asset}` | {spec.section}: {spec.title} | {spec.path} | "
            f"{'mobile' if spec.mobile else 'desktop'} | {', '.join(dict.fromkeys(usage))} |"
        )

    lines.extend(
        [
            "",
            "## Контроль безопасности",
            "",
            "- Использованы только учебные имена, демонстрационные заказы и тестовые остатки.",
            "- Персональные ссылки и QR-коды показаны как учебные примеры и не должны сканироваться.",
            "- В реестр не включены служебные роли, токены, пароли и реальные идентификаторы пользователей.",
            "- Desktop и mobile сохранены отдельно там, где меняются навигация или положение кнопок.",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Created {OUTPUT} ({len(specs)} screenshots)")


if __name__ == "__main__":
    main()
