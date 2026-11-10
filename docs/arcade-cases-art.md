# Графика «Орбитальных кейсов»

Растровый фон создан встроенным `image_gen`, без API/CLI fallback. Исходный результат сохранён инструментом в каталоге generated_images; рабочий оптимизированный файл находится в `app/web/static/miniapp/cases/hangar.webp`.

20 предметных SVG созданы непосредственно в коде проекта в `app/web/static/miniapp/cases/`: radio, boots, thermos, compass, camera, headphones, helmet, board, plant, drone, gamepad, telescope, robot, fox, engine, satellite, ship, planet, portal, dragon. Рисунки кейсов находятся в `games-cases.js`. Это оригинальная графика, без заимствованных игровых логотипов и предметов.

Итоговый промпт растровой иллюстрации:

> Use case: stylized-concept. Asset type: polished raster key art for an original family-friendly space cargo case-opening collection game inside a school arcade. Create a cinematic premium 3D game illustration: a single beautifully designed rugged orange-and-ivory science fiction cargo case, with beveled industrial shell, metal hinges, a mint light in its mechanical latch, partly opened with a gentle warm light coming from inside. A small friendly maintenance robot with one camera eye stands beside it. Set in a midnight blue orbital cargo hangar, distant shelves out of focus and a view of a blue planet through a window. Composition: landscape 3:2, the case on the right half, generous quiet dark navy space on the left for HTML heading overlay. Art direction: tactile crafted materials, convincing reflections and soft shadows, cozy science fiction rather than military, clear silhouette, restrained teal and warm amber accents. Do not include any text, lettering, numbers, logos, people, guns, currency, jewels or gambling symbols. This is finished in-game key art, not a UI mockup. Strong visual hierarchy, rich detail on the case, clean background.

Файл перекодирован в WebP без изменения композиции и разрешения: 152 542 байта вместо 2 000 424 байт PNG. Векторные предметы используются как отдельные SVG, чтобы сохранять чёткость при прокрутке и на экране коллекции.
