# Серия видео по Algo MAX

Материалы разделены по задаче. Короткое видео знакомит с продуктом, подробное показывает сквозную систему, а ролевые видео обучают конкретной работе без повторения общей теории.

## Состав

| № | Видео | Для чего | Слайды | Оценка | Целевая длительность | Материалы |
|---:|---|---|---:|---:|---|---|
| 1 | Algo MAX — короткое знакомство | Быстро и понятно показать ценность продукта без обучения кнопкам. | 6 | 0:55 | 45–60 секунд | [MP4](../output\video-series\01_Algo_MAX_Короткое_знакомство.mp4) · [SRT](../output\video-series\01_Algo_MAX_Короткое_знакомство.srt) · [VTT](../output\video-series\01_Algo_MAX_Короткое_знакомство.vtt) · [главы](../output\video-series\01_Algo_MAX_Короткое_знакомство.chapters.txt) |
| 2 | Algo MAX — подробный обзор продукта | Показать роли, данные и полный цикл от начисления до выдачи награды. | 18 | 6:29 | 5–7 минут | [MP4](../output\video-series\02_Algo_MAX_Подробный_обзор.mp4) · [SRT](../output\video-series\02_Algo_MAX_Подробный_обзор.srt) · [VTT](../output\video-series\02_Algo_MAX_Подробный_обзор.vtt) · [главы](../output\video-series\02_Algo_MAX_Подробный_обзор.chapters.txt) |
| 3 | Algo MAX — Ученик | Показать пользователю с ролью «Ученик» доступные разделы, кнопки и ограничения. | 27 | 2:58 | 2:30–3:15 | [MP4](../output\video-series\03_Algo_MAX_Роль_Ученик.mp4) · [SRT](../output\video-series\03_Algo_MAX_Роль_Ученик.srt) · [VTT](../output\video-series\03_Algo_MAX_Роль_Ученик.vtt) · [главы](../output\video-series\03_Algo_MAX_Роль_Ученик.chapters.txt) |
| 4 | Algo MAX — Родитель | Показать пользователю с ролью «Родитель» доступные разделы, кнопки и ограничения. | 28 | 3:02 | 2:45–3:30 | [MP4](../output\video-series\04_Algo_MAX_Роль_Родитель.mp4) · [SRT](../output\video-series\04_Algo_MAX_Роль_Родитель.srt) · [VTT](../output\video-series\04_Algo_MAX_Роль_Родитель.vtt) · [главы](../output\video-series\04_Algo_MAX_Роль_Родитель.chapters.txt) |
| 5 | Algo MAX — Преподаватель | Показать пользователю с ролью «Преподаватель» доступные разделы, кнопки и ограничения. | 30 | 3:31 | 2:45–3:30 | [MP4](../output\video-series\05_Algo_MAX_Роль_Преподаватель.mp4) · [SRT](../output\video-series\05_Algo_MAX_Роль_Преподаватель.srt) · [VTT](../output\video-series\05_Algo_MAX_Роль_Преподаватель.vtt) · [главы](../output\video-series\05_Algo_MAX_Роль_Преподаватель.chapters.txt) |
| 6 | Algo MAX — Куратор | Показать пользователю с ролью «Куратор» доступные разделы, кнопки и ограничения. | 21 | 2:32 | 2:30–3:15 | [MP4](../output\video-series\06_Algo_MAX_Роль_Куратор.mp4) · [SRT](../output\video-series\06_Algo_MAX_Роль_Куратор.srt) · [VTT](../output\video-series\06_Algo_MAX_Роль_Куратор.vtt) · [главы](../output\video-series\06_Algo_MAX_Роль_Куратор.chapters.txt) |
| 7 | Algo MAX — Администратор | Показать пользователю с ролью «Администратор» доступные разделы, кнопки и ограничения. | 71 | 7:37 | 7–8 минут | [MP4](../output\video-series\07_Algo_MAX_Роль_Администратор.mp4) · [SRT](../output\video-series\07_Algo_MAX_Роль_Администратор.srt) · [VTT](../output\video-series\07_Algo_MAX_Роль_Администратор.vtt) · [главы](../output\video-series\07_Algo_MAX_Роль_Администратор.chapters.txt) |
| 8 | Algo MAX — Директор | Показать пользователю с ролью «Директор» доступные разделы, кнопки и ограничения. | 49 | 5:36 | 5–6 минут | [MP4](../output\video-series\08_Algo_MAX_Роль_Директор.mp4) · [SRT](../output\video-series\08_Algo_MAX_Роль_Директор.srt) · [VTT](../output\video-series\08_Algo_MAX_Роль_Директор.vtt) · [главы](../output\video-series\08_Algo_MAX_Роль_Директор.chapters.txt) |

## Правила использования

1. Для презентации продукта отправляйте только короткое видео.
2. Новому партнеру или руководителю после короткого видео отправляйте подробный обзор.
3. Сотруднику или члену семьи отправляйте только видео его роли и при необходимости ссылку на полное руководство.
4. Для обновления интерфейса сначала замените скриншоты в `user-guide-assets/visual-v6`, затем пересоберите серию.

## Пересборка

```powershell
max_bot_venv\Scripts\python.exe docs\build_video_series.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File docs\export_video_series.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File docs\build_video_contact_sheets.ps1
max_bot_venv\Scripts\python.exe docs\audit_video_series_strict.py
```

Готовые MP4, SRT, VTT и главы создаются в `output/video-series`. Редактируемые презентации, тексты диктора и JSON озвучки находятся в `docs/video-series`.
