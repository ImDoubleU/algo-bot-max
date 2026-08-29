# Нейросетевая озвучка видео Algo MAX

По умолчанию видео собирается локальным движком Piper с русским голосом `ru_RU-dmitri-medium`. Облачный ключ и отдельный плагин не требуются.

## Подготовка один раз

Установить Piper в виртуальное окружение проекта:

```powershell
max_bot_venv\Scripts\python.exe -m pip install piper-tts==1.6.0
```

Скачать русскую модель в каталог воспроизводимых материалов:

```powershell
max_bot_venv\Scripts\python.exe -m piper.download_voices --download-dir output\tts-models ru_RU-dmitri-medium
```

Модель не добавляется в Git. При необходимости она загружается повторно этой же командой.

## Сборка

Нейросетевая озвучка и MP4:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File docs\export_product_materials.ps1
```

Старая системная озвучка Windows оставлена как резервный вариант:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File docs\export_product_materials.ps1 -TtsProvider Sapi
```

Перед синтезом текст автоматически адаптируется для произношения: `Algo MAX`, `AC`, `QR`, `Excel` и другие обозначения заменяются на читаемые русские варианты. Исходный текст слайдов при этом не меняется.

## Файлы

- модель: `output\tts-models\ru_RU-dmitri-medium.onnx`;
- дорожки по слайдам: `output\video\audio\slide-XX.wav`;
- манифест длительности: `output\video\audio\piper-manifest.json`;
- итоговое видео: `output\video\Algo_MAX_Обзор_продукта.mp4`.

Голос Dmitri обучен на наборе данных CC0. Движок Piper распространяется отдельно под GPL-3.0 и используется только как инструмент сборки документации.
