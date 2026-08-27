import hashlib
import re
import secrets
from urllib.parse import quote

from app.models.enums import StaffRole

STAFF_INVITATION_PAYLOAD_PREFIX = "staffi_"
STAFF_INVITATION_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,80}$")
STAFF_INVITATION_TTL_DAYS = 7


def invitable_staff_roles(actor_roles: set[StaffRole]) -> tuple[StaffRole, ...]:
    if StaffRole.SUPERADMIN in actor_roles:
        return (
            StaffRole.PARTNER_DIRECTOR,
            StaffRole.ADMIN,
            StaffRole.CURATOR,
            StaffRole.TEACHER,
        )
    if StaffRole.PARTNER_DIRECTOR in actor_roles:
        return (StaffRole.ADMIN, StaffRole.CURATOR, StaffRole.TEACHER)
    if StaffRole.ADMIN in actor_roles:
        return (StaffRole.CURATOR, StaffRole.TEACHER)
    return ()


def generate_staff_invitation_token() -> str:
    return secrets.token_urlsafe(24)


def staff_invitation_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def make_staff_invitation_payload(token: str) -> str:
    normalized = token.strip()
    if not STAFF_INVITATION_TOKEN_PATTERN.fullmatch(normalized):
        raise ValueError("Invalid staff invitation token")
    payload = f"{STAFF_INVITATION_PAYLOAD_PREFIX}{normalized}"
    if len(payload) > 128:
        raise ValueError("Staff invitation payload is too long")
    return payload


def parse_staff_invitation_payload(payload: str | None) -> str | None:
    raw = (payload or "").strip()
    if not raw.startswith(STAFF_INVITATION_PAYLOAD_PREFIX):
        return None
    token = raw[len(STAFF_INVITATION_PAYLOAD_PREFIX) :]
    return token if STAFF_INVITATION_TOKEN_PATTERN.fullmatch(token) else None


def build_max_bot_staff_invitation_deeplink(bot_username: str, token: str) -> str:
    username = bot_username.strip().lstrip("@")
    if not username:
        raise ValueError("MAX bot username is not configured")
    payload = make_staff_invitation_payload(token)
    return f"https://max.ru/{quote(username, safe='')}?start={quote(payload, safe='_-')}"
