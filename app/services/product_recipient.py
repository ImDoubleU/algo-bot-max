"""Recipient details are order data, never credentials or verified identities."""

import re

RECIPIENT_LABELS = {
    "steam_login": "Логин Steam",
    "roblox_username": "Username Roblox",
    "phone": "Номер телефона",
}


def validate_recipient(field: str | None, value: str | None) -> str | None:
    cleaned = (value or "").strip()
    if field is None:
        if cleaned:
            raise ValueError("Для этого товара данные аккаунта не запрашиваются")
        return None
    label = RECIPIENT_LABELS.get(field)
    if label is None:
        raise ValueError("Настройка данных получателя изменилась. Обновите магазин")
    if not cleaned:
        raise ValueError(f"Укажите {label}")
    if field == "phone":
        if not re.fullmatch(r"\+?[0-9 ()-]+", cleaned):
            raise ValueError("Номер телефона: используйте цифры и код страны")
        digits = re.sub(r"\D", "", cleaned)
        if not 10 <= len(digits) <= 15:
            raise ValueError("Проверьте номер телефона: нужно от 10 до 15 цифр")
        return ("+" if cleaned.startswith("+") else "") + digits
    # Allow legacy/system-generated names too. Format is not account verification.
    if not re.fullmatch(r"[A-Za-z0-9_]{3,64}", cleaned):
        raise ValueError(f"{label}: введите имя аккаунта латиницей, без пробелов и ссылок")
    return cleaned


def recipient_matches(field: str | None, stored: str | None, requested: str | None) -> bool:
    try:
        return stored == validate_recipient(field, requested)
    except ValueError:
        return False
