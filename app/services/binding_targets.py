"""Retain the target of a link without retaining its bearer token or URL."""

import re
from urllib.parse import parse_qs, urlsplit

from app.services.deep_links import parse_contact_payload, parse_shop_payload
from app.services.student_invitations import (
    StudentInvitationError,
    verify_student_invitation_details,
)


def contact_target(value, *, tenant_slug=None):
    target_id = parse_contact_payload(value) if isinstance(value, str) else None
    if not target_id or not re.fullmatch(r"[A-Z0-9_-]{1,120}", target_id):
        return None
    result = {"kind": "contact", "id": target_id}
    if isinstance(tenant_slug, str) and tenant_slug:
        result["tenant_slug"] = tenant_slug.strip().lower()
    return result


def target_from_launch(value, *, allow_bare_id=False):
    if not isinstance(value, str) or len(value) > 4096:
        return None
    value = value.strip()
    if value.lower().startswith(("https://", "http://")):
        try:
            url = urlsplit(value)
            if url.scheme != "https" or url.hostname != "max.ru":
                return None
            starts = parse_qs(url.query).get("start", [])
            if len(starts) != 1:
                return None
            value = starts[0]
        except ValueError:
            return None
    if value.startswith("student_"):
        try:
            invitation = verify_student_invitation_details(value[len("student_"):])
        except StudentInvitationError:
            return None
        return {"kind": "student", "id": str(invitation.student_id),
                "tenant_id": str(invitation.tenant_id), "issuer": invitation.issuer.value}
    if value.casefold().startswith("shop_"):
        tenant_slug, contact_id = parse_shop_payload(value)
        return contact_target(contact_id, tenant_slug=tenant_slug)
    if value.startswith(("cid_", "sid_", "contact_", "contact:", "id_", "id:")):
        return contact_target(value)
    if allow_bare_id and not value.casefold().startswith(("staff_", "knowledge_")):
        return contact_target(value)
    return None


def webhook_target(update):
    if update.get("update_type") == "bot_started":
        return target_from_launch(update.get("payload"), allow_bare_id=True)
    if update.get("update_type") == "message_created":
        message = update.get("message") or {}
        return target_from_launch((message.get("body") or {}).get("text"))
    return None
