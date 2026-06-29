from urllib.parse import quote

from app.services.access import normalize_contact_id

CONTACT_PAYLOAD_PREFIX = "cid_"
STUDENT_PAYLOAD_PREFIX = "sid_"
MAX_PAYLOAD_LIMIT = 128


class DeepLinkError(ValueError):
    pass


def make_contact_payload(contact_id: str) -> str:
    normalized = normalize_contact_id(contact_id)
    if not normalized:
        raise DeepLinkError("Contact ID is empty")

    payload = f"{CONTACT_PAYLOAD_PREFIX}{normalized}"
    if len(payload) > MAX_PAYLOAD_LIMIT:
        raise DeepLinkError(f"Payload is longer than {MAX_PAYLOAD_LIMIT} characters")

    return payload


def parse_contact_payload(payload: str | None) -> str | None:
    if not payload:
        return None

    value = payload.strip()
    if not value:
        return None

    if value.startswith(CONTACT_PAYLOAD_PREFIX):
        return normalize_contact_id(value[len(CONTACT_PAYLOAD_PREFIX) :])

    # Temporary compatibility for links generated before the contact-id decision.
    for prefix in (STUDENT_PAYLOAD_PREFIX, "contact_", "contact:", "id_", "id:"):
        if value.startswith(prefix):
            return normalize_contact_id(value[len(prefix) :])

    return normalize_contact_id(value)


def build_max_bot_deeplink(bot_username: str, contact_id: str) -> str:
    username = bot_username.strip().lstrip("@")
    if not username:
        raise DeepLinkError("Bot username is empty")

    payload = make_contact_payload(contact_id)
    return f"https://max.ru/{username}?start={quote(payload, safe='')}"


def make_student_payload(student_code: str) -> str:
    return make_contact_payload(student_code)


def parse_student_payload(payload: str | None) -> str | None:
    return parse_contact_payload(payload)
