from app.schemas.access import StudentResolveRequest
from app.services.access import build_rate_limit_key, hash_contact_id, normalize_contact_id
from app.services.deep_links import (
    build_max_bot_deeplink,
    make_contact_payload,
    parse_contact_payload,
)


def test_normalize_contact_id_strips_spaces_and_uppercases() -> None:
    assert normalize_contact_id(" 681 ab ") == "681AB"


def test_hash_contact_id_does_not_expose_raw_id() -> None:
    hashed = hash_contact_id("681")

    assert hashed != "681"
    assert len(hashed) == 64


def test_rate_limit_key_is_tenant_and_actor_scoped() -> None:
    payload = StudentResolveRequest(
        tenant_slug="nn-partner-a",
        contact_id="681",
        max_user_id=123,
    )

    assert build_rate_limit_key(payload) == "contact-id-entry:nn-partner-a:123"


def test_deep_link_payload_roundtrip() -> None:
    payload = make_contact_payload(" 681 ab ")

    assert payload == "cid_681AB"
    assert parse_contact_payload(payload) == "681AB"


def test_deep_link_keeps_legacy_sid_payload_compatible() -> None:
    assert parse_contact_payload("sid_681") == "681"


def test_build_max_bot_deeplink() -> None:
    link = build_max_bot_deeplink("@AlgoBot", "681")

    assert link == "https://max.ru/AlgoBot?start=cid_681"
