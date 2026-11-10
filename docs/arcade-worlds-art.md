# Игровые поля: иллюстрации и отрисовка — 10 ноября 2026

Изменения относятся к самим игровым сценам. Обложки и игровые правила хранятся отдельно.

## Файлы

`app/web/static/miniapp/worlds/`: 14 WebP и 30 SVG. Шесть растровых окружений, четыре растровых персонажа/планеты и четыре кузова; 19 векторных персонажей, три поверхности и восемь отдельных иллюстраций шариков. Растровые оригиналы сохранены в CODEX_HOME/generated_images; в проект скопированы оптимизированные версии. Прозрачность персонажей и кузовов сохранена.

`games-world-art.js` загружает нужные картинки при открытии игры. Для персонажей остаётся векторный вариант и прежняя процедурная отрисовка на случай ошибки загрузки. Шарики сохраняют цвет даже при недоступности SVG. Колёса, подвеска, наклон кузова и столкновения считаются прежней симуляцией. Кузова накладываются отдельно; прозрачные арки совмещены с положениями колёс. Цвет кузова меняется при выборе окраски. Кэш окрашенных кузовов ограничен 12 изображениями.

`games-worlds.css` задаёт материалы и размеры игровых элементов. На высоких телефонах поля с фиксированными пропорциями открываются в компактном окне; гонка использует доступную высоту, а колбы располагаются по высоте экрана с учётом количества рядов. Все нажатия остаются в исходных координатах симуляции.

## Создание растровых изображений

Использован встроенный image_gen, без CLI и внешнего API-ключа. Новые сцены сгенерированы отдельно. Для кота, жука и робота использованы соответствующие обложки проекта как визуальные референсы. PNG преобразованы в WebP с сохранением альфа-канала. Нативные SVG нарисованы в коде и доступны для прямого редактирования.

## Набор промптов 1

Общая часть:

Use case: stylized-concept. Production background asset for the INSIDE of a polished family-friendly game, not a promotional cover. Portrait 4:5. Tactile stylized 3D environment, cinematic gentle lighting, beautifully crafted materials, restrained detail, readable composition. All playable actors and interface will be rendered separately, so leave the central 75 percent quiet with low contrast and generous empty negative space. No text, letters, numbers, logos, interfaces, characters or floating collectible objects.

### orbit

An orbital view into deep violet and midnight-blue outer space, delicate distant stars, a subtle lavender nebula curling at the outer edges, pale mint atmospheric glow at the extreme lower edge. Empty deep navy center from top to bottom. No planet in the center, no spaceship, no foreground objects. Magical calm depth, premium animated-film rendering.

Файл: `worlds/orbit.webp`. Оригинал: `exec-577bf613-3cb8-45b0-afce-e9088b63b9a6.png`.

### tower

A charming distant miniature city at golden hour viewed from a construction site. Tiny detailed teal and warm cream buildings only along the very bottom 20 percent and far edges. The upper and central 80 percent is clear soft warm blue sky fading toward cream at the bottom. A few delicate clouds near top edges. No cranes, no construction equipment, no close buildings. Beautiful handcrafted toy-city feel.

Файл: `worlds/tower.webp`. Оригинал: `exec-ef31f007-e9be-4f4c-b95d-5c8e11389857.png`.

### bubbles

The interior of a magical little deep teal underwater observatory. Deep navy-teal clear empty water fills central 80 percent. Very subtle warm caustics and distant light from above, a few sea plants and ceramic pebbles only along the outermost left and right lower corners. Elegant brass framing only at extreme edges. No bubbles, no fish or animals, no cannon. Dark quiet play area.

Файл: `worlds/bubbles.webp`. Оригинал: `exec-2e847315-7305-4932-be3b-aba1a3f473c9.png`.

### expedition

A tiny alien rescue sanctuary in a lush whimsical forest at twilight. Mint and turquoise plants with lilac flowers only along the outermost edges, a softly glowing curved greenhouse arch in the far background top edge. The middle 80 percent is a quiet deep desaturated green tabletop-like clearing, no objects in the center, no creatures, no spaceships. Soft depth of field, lovely premium tactile 3D game environment.

Файл: `worlds/expedition.webp`. Оригинал: `exec-382dbc21-c981-4af1-85c3-2765dbb554f8.png`.

## Набор промптов 2

### cat

Use case: stylized-concept. Make a production gameplay sprite of the orange cat astronaut from the reference illustration. Preserve the same friendly orange tabby character, ivory spacesuit, orange trims, glass helmet, tactile cinematic 3D style. One isolated full-body cat, facing mostly forward, three-quarter angle, paws and tail visible, a compact floating pose with open eyes and a cheerful determined expression. Strong compact readable silhouette at 48 pixels. Center the entire character in a square canvas with 10 percent clear padding, no cropping. Transparent background, no planet, stars, scenery, typography, frame, shadow puddle or UI.

Файл: `worlds/cat.webp`. Оригинал: `exec-67363307-b773-4d40-93af-4ef02c926355.png`.

### bug

Use case: stylized-concept. Make a production gameplay sprite of one mechanical green-and-brass beetle from the reference illustration. Preserve the distinctive emerald enamel shell, brass mechanics, six little articulated legs, two antennae, bright amber eyes. One isolated full beetle, viewed from slightly above and in front, centered, compact readable silhouette, friendly mischievous expression. Polished tactile 3D, beautiful soft neutral lighting. Entire beetle and legs inside square canvas, 10 percent padding. Genuinely transparent background; no circuitry, floor, tools, scenery, text, shadow puddle or UI.

Файл: `worlds/bug.webp`. Оригинал: `exec-13991fd2-059a-4e71-a0eb-45fa2e6eb90f.png`.

### robot

Use case: stylized-concept. Make a production gameplay sprite of a small friendly robot based on the robotic character from the reference illustration. Ivory ceramic and mint metal body, bright cyan eyes on a dark screen face, rounded compact square head, two stubby arms, two feet, one small amber antenna. NO detective hat, coat or magnifying glass. Clearly different silhouette from a beetle. Full-body front three-quarter view, friendly open expression, waving one hand. Tactile polished 3D, neutral soft lighting. Center entire character in square canvas with 10 percent padding. Transparent background, no floor, scenery, text, frame or UI.

Файл: `worlds/robot.webp`. Оригинал: `exec-d4a9cc81-a410-4169-821a-f392d94edc09.png`.

## Набор промптов 3

### planet

Use case: stylized-concept. A production gameplay sprite, one beautiful purple alien planet, isolated on a genuinely transparent background. Sphere viewed from space, tactile gently cratered violet and lavender surface, subtle swirl-like continental ridges, warm upper-left sunlight and deep cool lower-right shadow, beautifully dimensional polished animated-film 3D. A solid spherical planet only: NO RINGS, moons, characters, text, UI, stars, halo, backdrop or cast shadow. Centered, whole sphere fills 85 percent of a square canvas, clean silhouette.

Файл: `worlds/planet.webp`. Оригинал: `exec-2f940bcd-0f18-42a9-92fd-f1ff79b97fb0.png`.

### board

Use case: stylized-concept. Production portrait 4:5 background for a tap-the-bug arcade game. A richly tactile miniature green printed circuit board viewed exactly top down, filling the canvas. Deep desaturated emerald substrate, beautifully etched copper tracks, little gold vias and tiny bolts. A few realistic ceramic capacitors and dark rounded microchips ONLY in the outermost 10 percent along edges and corners. The central 80 percent must remain empty flat dark green substrate with subtle sparse traces, a quiet playable area, no component blocking it. Soft cinematic warm light, excellent physically based materials, tilt-shift miniature craftsmanship. No insects, robots, characters, text, letters, numbers, labels, logos or UI.

Файл: `worlds/board.webp`. Оригинал: `exec-e038e938-2a78-4edf-a845-64419d7073b4.png`.

### meadow

Use case: stylized-concept. Production panoramic 3:1 distant background layer for an original side-scrolling off-road driving game. Polished tactile stylized 3D miniature landscape, joyful richly detailed countryside, layered pale blue mountains, rolling distant green hills, tiny farm buildings and trees only far in background, beautiful soft clouds, warm sunlight. Camera is a SIDE VIEW looking horizontally, NOT isometric and NOT top down. Upper 60 percent is broad quiet blue sky, lower 40 percent distant landscape. No road in foreground, no ground platform, no vehicles, no characters, no text, no UI. The actual interactive ground and car will be drawn separately on top.

Файл: `worlds/meadow.webp`. Оригинал: `exec-f8897d6f-f99b-4031-ae58-17328a78e3e1.png`.

### car-scout

Use case: stylized-concept. One production game sprite of a charming rugged mustard-yellow short-wheelbase off-road jeep BODY ONLY, with a spare tire mounted at the back, roof luggage rack with a small beige travel bag, amber lamps and beautiful blue-tinted windows. Polished high-quality tactile miniature 3D, crisp physical materials. STRICT ORTHOGRAPHIC PERFECT SIDE PROFILE, vehicle nose points RIGHT, zero visible front or rear face, no perspective, level chassis. NO ROAD WHEELS OR TIRES OR HUBS OR SUSPENSION: leave the two road wheel arches open and transparent for separately animated wheels. Wheel centers at 18 and 82 percent of body width. Entire body centered, no clipping, transparent background, no ground, no shadow puddle, no text, no logos, no UI. Wide 2:1 canvas.

Файл: `worlds/car-scout.webp`. Оригинал: `exec-3ee01993-909a-4047-afdc-18b0916845e6.png`.

### car-buggy

Use case: stylized-concept. One production game sprite of a lively mint-green and brass dune buggy BODY ONLY, exposed tubular roll cage, low sporty open cockpit, small orange seat, visible compact engine behind cockpit, two small amber roof lamps. Polished high-quality tactile miniature 3D with crisp physical materials. STRICT ORTHOGRAPHIC PERFECT SIDE PROFILE, vehicle nose points RIGHT, zero visible front or rear face, no perspective, level chassis. NO ROAD WHEELS, TIRES, HUBS OR SUSPENSION: two wheel arches open and transparent, wheel centers at 18 and 82 percent of body width. Entire body centered, no clipping, transparent background, no ground or shadow puddle, no text, no logos, no UI. Wide 2:1 canvas.

Файл: `worlds/car-buggy.webp`. Оригинал: `exec-10d71a6e-98a1-4893-9210-349dd5f34168.png`.

### car-truck

Use case: stylized-concept. One production game sprite of a charming red-orange compact off-road delivery TRUCK BODY ONLY, short cab at RIGHT, two small blue-tinted cabin windows, beige canvas-covered cargo box at LEFT, warm metal trim and headlamps. Polished high-quality tactile miniature 3D with crisp physical materials. STRICT ORTHOGRAPHIC PERFECT SIDE PROFILE, nose points RIGHT, zero visible front or rear face, no perspective, level chassis. NO ROAD WHEELS, TIRES, HUBS OR SUSPENSION: two wheel arches open and transparent, wheel centers at 18 and 82 percent of body width. Entire body centered, no clipping, genuinely transparent background, no ground or shadow puddle, no text, logos or UI. Wide 2:1 canvas.

Файл: `worlds/car-truck.webp`. Оригинал: `exec-e6554a71-4b2f-436d-aebf-671b9ba50a33.png`.

### car-rover

Use case: stylized-concept. One production game sprite of a charming ivory and pale blue futuristic lunar exploration ROVER BODY ONLY, compact pressurized sloping cabin with large blue-tinted windows, small gold scientific antenna, a small solar panel on rear roof, warm amber lamps, gold thermal trim. Polished high-quality tactile miniature 3D with crisp physical materials. STRICT ORTHOGRAPHIC PERFECT SIDE PROFILE, nose points RIGHT, zero visible front or rear face, no perspective, level chassis. NO ROAD WHEELS, TIRES, HUBS OR SUSPENSION: two wheel arches open and transparent, wheel centers at 18 and 82 percent of body width. Entire body centered, no clipping, genuinely transparent background, no ground or shadow puddle, no text, logos or UI. Wide 2:1 canvas.

Файл: `worlds/car-rover.webp`. Оригинал: `exec-a40eec68-0c7f-4caf-b1d4-d8d9d1c47235.png`.

## Размер

Суммарно 684 КиБ. Картинки окружения загружаются для открываемой игры, а не всей коллекцией при входе в раздел.

## Проверка

Основной набор перед заключительной настройкой высоких телефонов: **96/96**. После настройки колб и компактных окон повторно прошли **14/14** проверок мобильных полей, графических ресурсов и перелёта шариков; дополнительно **6/6** проверок ресурсов, запасной отрисовки, четырёх кузовов с окраской и высоких телефонов. Наборы пересекаются и не складываются как количество уникальных тестов. Проверены Chromium и WebKit. Четыре кузова проверены на отдельном листе отрисовки и в настоящем заезде; на телефоне проверены перелёт шариков и расположение элементов.

Графическая версия не меняет экономику, награды, школьные данные или привязки. VPS не обновлялся.
