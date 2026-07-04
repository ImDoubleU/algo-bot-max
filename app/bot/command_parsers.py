from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccrueCommand:
    amount: int
    student_query: str
    reason: str


@dataclass(frozen=True)
class StaffRoleCommand:
    target_max_user_id: int
    role: str
    status: str
    display_name: str | None


@dataclass(frozen=True)
class BuyItemCommand:
    product_query: str
    quantity: int


@dataclass(frozen=True)
class BuyCommand:
    items: tuple[BuyItemCommand, ...]
    student_query: str | None


@dataclass(frozen=True)
class SetStockCommand:
    product_query: str
    available_quantity: int
    warehouse_query: str | None


@dataclass(frozen=True)
class TransferStockCommand:
    product_query: str
    quantity: int
    from_warehouse_query: str
    to_warehouse_query: str


@dataclass(frozen=True)
class WarehouseCommand:
    slug: str
    name: str
    warehouse_type: str
    address: str | None


@dataclass(frozen=True)
class ProductSetCommand:
    sku: str
    name: str
    price_astrocoins: int
    category_name: str
    status: str
    description: str | None


@dataclass(frozen=True)
class SetPriceCommand:
    product_query: str
    price_astrocoins: int


@dataclass(frozen=True)
class ProductStatusCommand:
    product_query: str
    status: str


@dataclass(frozen=True)
class SetPhotoCommand:
    product_query: str
    photo_url: str | None


def parse_staffrole_command(
    argument: str,
    *,
    forced_status: str | None = None,
) -> StaffRoleCommand | str:
    usage = (
        "Формат: /staffrole <MAX_USER_ID> <role> [active|revoked] [| имя]\n"
        "Роли: superadmin, partner_director, admin, curator, teacher.\n"
        "Примеры: /staffrole 123456 teacher | Мария\n"
        "/staffoff 123456 teacher"
    )
    raw = argument.strip()
    if not raw:
        return usage

    main_part, _, display_name = raw.partition("|")
    tokens = main_part.split()
    if len(tokens) < 2:
        return usage
    try:
        target_max_user_id = int(tokens[0])
    except ValueError:
        return "MAX user_id должен быть числом. Его можно узнать командой /id."
    if target_max_user_id <= 0:
        return "MAX user_id должен быть положительным числом."

    role = tokens[1].strip().lower()
    allowed_roles = {"superadmin", "partner_director", "admin", "curator", "teacher"}
    if role not in allowed_roles:
        return "Роль должна быть одной из: superadmin, partner_director, admin, curator, teacher."

    status = forced_status or (tokens[2].strip().lower() if len(tokens) >= 3 else "active")
    if status not in {"active", "revoked"}:
        return "Статус должен быть active или revoked."

    clean_display_name = display_name.strip() or None
    return StaffRoleCommand(
        target_max_user_id=target_max_user_id,
        role=role,
        status=status,
        display_name=clean_display_name,
    )


def parse_accrue_command(argument: str) -> AccrueCommand | str:
    text = argument.strip()
    usage = "Формат: /accrue <AC> <ученик> | <причина>. Например: /accrue 50 алиса | За проект"
    if not text:
        return usage
    if "|" not in text:
        return "Добавьте причину после `|`: /accrue 50 алиса | За проект"

    left, reason = (part.strip() for part in text.split("|", 1))
    amount_text, _, student_query = left.partition(" ")
    if not amount_text or not student_query.strip():
        return usage
    try:
        amount = int(amount_text)
    except ValueError:
        return "Сумма начисления должна быть целым числом. Например: /accrue 50 алиса | За проект"
    if amount <= 0 or amount > 10000:
        return "Сумма начисления должна быть от 1 до 10000 AC."
    if len(reason) < 2:
        return "Причина начисления должна быть не короче 2 символов."
    return AccrueCommand(
        amount=amount,
        student_query=student_query.strip(),
        reason=reason,
    )


def parse_buy_command(argument: str) -> BuyCommand | str:
    text = argument.strip()
    usage = (
        "Формат: /buy <SKU или товар> [шт.][, SKU шт.] [| <ученик>]. "
        "Например: /buy PEN-LOGO 2, BRACELET-SILICONE 1 | алиса"
    )
    if not text:
        return usage
    student_query: str | None = None
    if "|" in text:
        left, raw_student_query = (part.strip() for part in text.split("|", 1))
        if not raw_student_query:
            return usage
        student_query = raw_student_query
    else:
        left = text
    if not left:
        return usage

    parsed_items: list[BuyItemCommand] = []
    total_quantity = 0
    for raw_item in left.split(","):
        item_text = raw_item.strip()
        if not item_text:
            return usage
        parts = item_text.rsplit(maxsplit=1)
        product_query = item_text
        quantity = 1
        if len(parts) == 2:
            maybe_quantity = parts[1]
            try:
                quantity = int(maybe_quantity)
                product_query = parts[0].strip()
            except ValueError:
                quantity = 1

        if not product_query or len(product_query) < 2:
            return usage
        if quantity <= 0 or quantity > 20:
            return "Количество каждой позиции в заказе должно быть от 1 до 20 шт."
        total_quantity += quantity
        parsed_items.append(
            BuyItemCommand(
                product_query=product_query,
                quantity=quantity,
            )
        )

    if len(parsed_items) > 20:
        return "В одном заказе можно указать не больше 20 позиций."
    if total_quantity > 20:
        return "Общее количество товаров в одном заказе должно быть не больше 20 шт."
    if student_query is not None and len(student_query) < 2:
        return "Запрос ученика должен быть не короче 2 символов."
    return BuyCommand(
        items=tuple(parsed_items),
        student_query=student_query,
    )


def parse_warehouse_command(argument: str) -> WarehouseCommand | str:
    usage = (
        "Формат: /warehouse <slug> | <название> [| common|venue|partner|external] "
        "[| адрес].\n"
        "Например: /warehouse nn-main | Основной склад | common"
    )
    parts = [part.strip() for part in argument.split("|")]
    if len(parts) < 2 or len(parts) > 4:
        return usage

    slug = parts[0].strip().lower()
    name = parts[1].strip()
    warehouse_type = parts[2].strip().lower() if len(parts) >= 3 and parts[2] else "common"
    address = parts[3].strip() if len(parts) >= 4 and parts[3] else None

    if not slug or not name:
        return usage
    if len(slug) < 2 or len(slug) > 120:
        return "Slug склада должен быть от 2 до 120 символов."
    allowed_slug_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-_")
    if any(char not in allowed_slug_chars for char in slug):
        return "Slug склада должен содержать только латинские буквы, цифры, `-` и `_`."
    if len(name) < 2 or len(name) > 180:
        return "Название склада должно быть от 2 до 180 символов."
    allowed_types = {"common", "venue", "partner", "external"}
    if warehouse_type not in allowed_types:
        return "Тип склада: common, venue, partner или external."
    if address is not None and len(address) > 260:
        return "Адрес склада должен быть не длиннее 260 символов."
    return WarehouseCommand(
        slug=slug,
        name=name,
        warehouse_type=warehouse_type,
        address=address,
    )


def parse_productset_command(argument: str) -> ProductSetCommand | str:
    usage = (
        "Формат: /productset <SKU> | <название> | <цена AC> "
        "[| категория] [| active|hidden|archived] [| описание].\n"
        "Например: /productset PEN-LOGO | Ручка Алгоритмики | 120 | Канцелярия"
    )
    parts = [part.strip() for part in argument.split("|")]
    if len(parts) < 3 or len(parts) > 6:
        return usage

    sku = parts[0].strip().upper()
    name = parts[1].strip()
    price_text = parts[2].strip()
    category_name = parts[3].strip() if len(parts) >= 4 and parts[3] else "Без категории"
    status = parts[4].strip().lower() if len(parts) >= 5 and parts[4] else "active"
    description = parts[5].strip() if len(parts) >= 6 and parts[5] else None

    if len(sku) < 2 or len(sku) > 120:
        return "SKU должен быть от 2 до 120 символов."
    if any(character.isspace() for character in sku):
        return "SKU не должен содержать пробелы. Например: PEN-LOGO"
    if len(name) < 2 or len(name) > 200:
        return "Название товара должно быть от 2 до 200 символов."
    try:
        price_astrocoins = int(price_text)
    except ValueError:
        return "Цена должна быть целым числом AC. Например: /productset PEN-LOGO | Ручка | 120"
    if price_astrocoins < 0 or price_astrocoins > 1_000_000:
        return "Цена товара должна быть от 0 до 1000000 AC."
    if len(category_name) < 2 or len(category_name) > 160:
        return "Категория должна быть от 2 до 160 символов."
    allowed_statuses = {"active", "hidden", "archived"}
    if status not in allowed_statuses:
        return "Статус товара: active, hidden или archived."
    if description is not None and len(description) > 1000:
        return "Описание товара должно быть не длиннее 1000 символов."
    return ProductSetCommand(
        sku=sku,
        name=name,
        price_astrocoins=price_astrocoins,
        category_name=category_name,
        status=status,
        description=description,
    )


def parse_setprice_command(argument: str) -> SetPriceCommand | str:
    usage = "Формат: /setprice <SKU или товар> <цена AC>. Например: /setprice PEN-LOGO 120"
    text = argument.strip()
    if not text:
        return usage
    parts = text.rsplit(maxsplit=1)
    if len(parts) != 2:
        return usage
    product_query, price_text = parts[0].strip(), parts[1].strip()
    if len(product_query) < 2:
        return usage
    try:
        price_astrocoins = int(price_text)
    except ValueError:
        return "Цена должна быть целым числом AC. Например: /setprice PEN-LOGO 120"
    if price_astrocoins < 0 or price_astrocoins > 1_000_000:
        return "Цена товара должна быть от 0 до 1000000 AC."
    return SetPriceCommand(
        product_query=product_query,
        price_astrocoins=price_astrocoins,
    )


def parse_productstatus_command(
    argument: str,
    *,
    forced_status: str | None = None,
) -> ProductStatusCommand | str:
    allowed_statuses = {"active", "hidden", "archived"}
    if forced_status is not None and forced_status not in allowed_statuses:
        return "Статус товара: active, hidden или archived."

    text = argument.strip()
    if forced_status is not None:
        if len(text) < 2:
            return "Формат: /hideproduct <SKU или товар>. Например: /hideproduct PEN-LOGO"
        return ProductStatusCommand(product_query=text, status=forced_status)

    usage = (
        "Формат: /productstatus <SKU или товар> <active|hidden|archived>.\n"
        "Например: /productstatus PEN-LOGO hidden"
    )
    if not text:
        return usage
    parts = text.rsplit(maxsplit=1)
    if len(parts) != 2:
        return usage
    product_query, status = parts[0].strip(), parts[1].strip().lower()
    if len(product_query) < 2:
        return usage
    if status not in allowed_statuses:
        return "Статус товара: active, hidden или archived."
    return ProductStatusCommand(product_query=product_query, status=status)


def parse_setphoto_command(
    argument: str,
    *,
    clear_photo: bool = False,
) -> SetPhotoCommand | str:
    if clear_photo:
        product_query = argument.strip()
        if len(product_query) < 2:
            return "Формат: /clearphoto <SKU или товар>. Например: /clearphoto PEN-LOGO"
        return SetPhotoCommand(product_query=product_query, photo_url=None)

    usage = (
        "Формат: /setphoto <SKU или товар> | <https://url>.\n"
        "Например: /setphoto PEN-LOGO | https://example.com/pen.jpg"
    )
    text = argument.strip()
    if not text or "|" not in text:
        return usage
    product_query, _, photo_url = text.partition("|")
    product_query = product_query.strip()
    photo_url = photo_url.strip()
    if len(product_query) < 2 or not photo_url:
        return usage
    if len(photo_url) > 500:
        return "URL фото должен быть не длиннее 500 символов."
    normalized_url = photo_url.casefold()
    if not (normalized_url.startswith("https://") or normalized_url.startswith("http://")):
        return "URL фото должен начинаться с http:// или https://."
    return SetPhotoCommand(product_query=product_query, photo_url=photo_url)


def parse_setstock_command(argument: str) -> SetStockCommand | str:
    text = argument.strip()
    usage = "Формат: /setstock <SKU или товар> <остаток> [| склад]. Например: /setstock PEN-LOGO 18"
    if not text:
        return usage

    left, _, warehouse_query = text.partition("|")
    left = left.strip()
    warehouse_query = warehouse_query.strip() or None
    if not left:
        return usage
    parts = left.rsplit(maxsplit=1)
    if len(parts) != 2:
        return usage
    product_query, quantity_text = parts[0].strip(), parts[1].strip()
    if not product_query or len(product_query) < 2:
        return usage
    try:
        available_quantity = int(quantity_text)
    except ValueError:
        return "Остаток должен быть целым числом. Например: /setstock PEN-LOGO 18"
    if available_quantity < 0 or available_quantity > 100000:
        return "Остаток должен быть от 0 до 100000 шт."
    return SetStockCommand(
        product_query=product_query,
        available_quantity=available_quantity,
        warehouse_query=warehouse_query,
    )


def parse_transfer_command(argument: str) -> TransferStockCommand | str:
    text = argument.strip()
    usage = (
        "Формат: /transfer <SKU или товар> <шт> | <склад откуда> -> <склад куда>.\n"
        "Например: /transfer PEN-LOGO 3 | основной -> витрина"
    )
    if not text:
        return usage

    left, separator, route = text.partition("|")
    if not separator:
        return usage
    route_separator = "->" if "->" in route else ">"
    from_warehouse_query, route_separator, to_warehouse_query = route.partition(route_separator)
    if not route_separator:
        return usage

    left = left.strip()
    from_warehouse_query = from_warehouse_query.strip()
    to_warehouse_query = to_warehouse_query.strip()
    if not left or not from_warehouse_query or not to_warehouse_query:
        return usage

    parts = left.rsplit(maxsplit=1)
    if len(parts) != 2:
        return usage
    product_query, quantity_text = parts[0].strip(), parts[1].strip()
    if not product_query or len(product_query) < 2:
        return usage
    try:
        quantity = int(quantity_text)
    except ValueError:
        return (
            "Количество должно быть целым числом. "
            "Например: /transfer PEN-LOGO 3 | основной -> витрина"
        )
    if quantity <= 0 or quantity > 10000:
        return "Количество для переноса должно быть от 1 до 10000 шт."
    return TransferStockCommand(
        product_query=product_query,
        quantity=quantity,
        from_warehouse_query=from_warehouse_query,
        to_warehouse_query=to_warehouse_query,
    )
