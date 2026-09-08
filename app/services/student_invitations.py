from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from uuid import UUID

import qrcode
from qrcode.image.svg import SvgPathImage

from app.core.config import get_settings

STUDENT_INVITE_PREFIX = "student_"
STUDENT_INVITE_VERSION_V1 = b"s1"
STUDENT_INVITE_VERSION_V2 = b"s2"
STUDENT_INVITE_VERSION_V3 = b"s3"
STUDENT_INVITE_TEACHER_MARKER = b"t"
STUDENT_INVITE_SIGNATURE_BYTES = 16
MAX_PAYLOAD_LIMIT = 128


class StudentInvitationError(ValueError):
    pass


class StudentInvitationIssuer(StrEnum):
    LEGACY = "legacy"
    PARENT = "parent"
    TEACHER = "teacher"


@dataclass(frozen=True, slots=True)
class VerifiedStudentInvitation:
    tenant_id: UUID
    student_id: UUID
    sponsor_access_link_id: UUID | None
    issuer: StudentInvitationIssuer


def _signature(version: bytes, payload: bytes) -> bytes:
    secret = get_settings().app_secret_key.encode("utf-8")
    return hmac.new(
        secret,
        version + payload,
        hashlib.sha256,
    ).digest()[:STUDENT_INVITE_SIGNATURE_BYTES]


def issue_student_invitation_token(
    tenant_id: UUID,
    student_id: UUID,
    sponsor_access_link_id: UUID | None = None,
) -> str:
    identity = tenant_id.bytes + student_id.bytes
    version = STUDENT_INVITE_VERSION_V1
    if sponsor_access_link_id is not None:
        identity += sponsor_access_link_id.bytes
        version = STUDENT_INVITE_VERSION_V2
    payload = identity + _signature(version, identity)
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def issue_teacher_student_invitation_token(tenant_id: UUID, student_id: UUID) -> str:
    identity = tenant_id.bytes + student_id.bytes + STUDENT_INVITE_TEACHER_MARKER
    payload = identity + _signature(STUDENT_INVITE_VERSION_V3, identity)
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def verify_student_invitation_details(token: str) -> VerifiedStudentInvitation:
    try:
        padding = "=" * (-len(token) % 4)
        payload = base64.urlsafe_b64decode(f"{token}{padding}")
    except (binascii.Error, ValueError, TypeError) as exc:
        raise StudentInvitationError("Некорректная ссылка ученика") from exc
    legacy_length = 32 + STUDENT_INVITE_SIGNATURE_BYTES
    sponsored_length = 48 + STUDENT_INVITE_SIGNATURE_BYTES
    teacher_length = 33 + STUDENT_INVITE_SIGNATURE_BYTES
    if len(payload) == legacy_length:
        version = STUDENT_INVITE_VERSION_V1
        identity_length = 32
        issuer = StudentInvitationIssuer.LEGACY
    elif len(payload) == sponsored_length:
        version = STUDENT_INVITE_VERSION_V2
        identity_length = 48
        issuer = StudentInvitationIssuer.PARENT
    elif len(payload) == teacher_length:
        version = STUDENT_INVITE_VERSION_V3
        identity_length = 33
        issuer = StudentInvitationIssuer.TEACHER
    else:
        raise StudentInvitationError("Некорректная ссылка ученика")

    identity = payload[:identity_length]
    supplied_signature = payload[identity_length:]
    if not hmac.compare_digest(supplied_signature, _signature(version, identity)):
        raise StudentInvitationError("Некорректная подпись ссылки ученика")
    if (
        issuer == StudentInvitationIssuer.TEACHER
        and identity[32:33] != STUDENT_INVITE_TEACHER_MARKER
    ):
        raise StudentInvitationError("Некорректная ссылка ученика")
    sponsor_access_link_id = (
        UUID(bytes=identity[32:48]) if identity_length == 48 else None
    )
    return VerifiedStudentInvitation(
        tenant_id=UUID(bytes=identity[:16]),
        student_id=UUID(bytes=identity[16:32]),
        sponsor_access_link_id=sponsor_access_link_id,
        issuer=issuer,
    )


def verify_student_invitation_token(token: str) -> tuple[UUID, UUID, UUID | None]:
    invitation = verify_student_invitation_details(token)
    return (
        invitation.tenant_id,
        invitation.student_id,
        invitation.sponsor_access_link_id,
    )


def build_student_invitation_link(
    bot_username: str,
    tenant_id: UUID,
    student_id: UUID,
    sponsor_access_link_id: UUID | None = None,
) -> str:
    username = bot_username.strip().lstrip("@")
    if not username:
        raise StudentInvitationError("Bot username is empty")
    payload = (
        f"{STUDENT_INVITE_PREFIX}"
        f"{issue_student_invitation_token(tenant_id, student_id, sponsor_access_link_id)}"
    )
    if len(payload) > MAX_PAYLOAD_LIMIT:
        raise StudentInvitationError(
            f"Payload is longer than {MAX_PAYLOAD_LIMIT} characters"
        )
    return f"https://max.ru/{username}?start={payload}"


def build_teacher_student_invitation_link(
    bot_username: str,
    tenant_id: UUID,
    student_id: UUID,
) -> str:
    username = bot_username.strip().lstrip("@")
    if not username:
        raise StudentInvitationError("Bot username is empty")
    payload = (
        f"{STUDENT_INVITE_PREFIX}"
        f"{issue_teacher_student_invitation_token(tenant_id, student_id)}"
    )
    if len(payload) > MAX_PAYLOAD_LIMIT:
        raise StudentInvitationError(
            f"Payload is longer than {MAX_PAYLOAD_LIMIT} characters"
        )
    return f"https://max.ru/{username}?start={payload}"


def invitation_qr_data_url(link: str) -> str:
    qr = _invitation_qr(link)
    image = qr.make_image(image_factory=SvgPathImage)
    output = BytesIO()
    image.save(output)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def invitation_qr_png(link: str) -> bytes:
    qr = _invitation_qr(link)
    image = qr.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _invitation_qr(link: str) -> qrcode.QRCode:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(link)
    qr.make(fit=True)
    return qr
