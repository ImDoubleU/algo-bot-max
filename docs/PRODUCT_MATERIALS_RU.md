# Материалы по продукту Algo MAX

Актуальная редакция собрана для интерфейса 0.86.2.

## Полное руководство

- PPTX: `Algo_MAX_Руководство_по_ролям.pptx`.
- PDF: `..\output\pdf\Algo_MAX_Полное_руководство.pdf`.
- Текст по кнопкам: `INTERACTION_GUIDE_RU.md`.
- Реестр экранов: `SCREENSHOT_REGISTER_RU.md`.
- Объем: 100 слайдов, 42 проверяемых пользовательских сценария.

## Общая презентация

- PPTX: `Algo_MAX_Презентация_продукта.pptx`.
- PDF: `..\output\pdf\Algo_MAX_Презентация_продукта.pdf`.
- Текст ведущего: `VIDEO_SCRIPT_RU.md`.
- Объем: 40 слайдов.

## Серия видео

Серия состоит из короткого знакомства, обзора на 6–8 минут и отдельных видео для ученика, родителя, преподавателя, куратора, администратора и директора.

- Индекс: `VIDEO_SERIES_RU.md`.
- PPTX, покадровые планы и тексты: `video-series`.
- PDF по ролям: `..\output\pdf\video-series`.
- MP4 без звуковой дорожки, SRT, VTT и главы: `..\output\video-series`.
- Проверка: `QA_REPORT_RU.md` и `..\output\training-materials-qa.json`.

MP4 намеренно собраны без голоса. Время каждого кадра рассчитано для живой русской речи в темпе 125–140 слов в минуту. В каждом сценарии есть таблица: таймкод, экран, действие курсора, текст диктора и текст на экране.

## Пересборка

```powershell
max_bot_venv\Scripts\python.exe docs\build_role_guide.py
max_bot_venv\Scripts\python.exe docs\build_product_presentation.py
max_bot_venv\Scripts\python.exe docs\build_video_series.py
max_bot_venv\Scripts\python.exe docs\build_screenshot_register.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File docs\export_product_materials.ps1 -SkipVideo
powershell.exe -NoProfile -ExecutionPolicy Bypass -File docs\export_video_series.ps1
max_bot_venv\Scripts\python.exe docs\audit_training_materials.py
```

Сборка не меняет рабочую базу и не выполняет развертывание.
