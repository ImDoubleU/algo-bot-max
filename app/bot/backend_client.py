from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request

from app.core.miniapp_auth import issue_miniapp_token


class BackendApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AccessBackendClient:
    def __init__(self, api_base: str, *, timeout_seconds: int = 15) -> None:
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
        auth_tenant_slug: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.api_base}{path}"
        clean_params = {key: value for key, value in (params or {}).items() if value is not None}
        if clean_params:
            url = f"{url}?{parse.urlencode(clean_params)}"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        identity_source = body or params or {}
        max_user_id = identity_source.get("max_user_id")
        tenant_slug = identity_source.get("tenant_slug") or auth_tenant_slug
        if max_user_id and tenant_slug:
            headers["X-Miniapp-Token"] = issue_miniapp_token(
                max_user_id=int(max_user_id),
                tenant_slug=str(tenant_slug),
            )
        req = request.Request(
            url,
            data=data,
            method=method.upper(),
            headers=headers,
        )

        try:
            with request.urlopen(req, timeout=timeout or self.timeout_seconds) as response:
                raw = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(detail)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("detail"):
                detail = str(parsed["detail"])
            raise BackendApiError(
                f"HTTP {exc.code} {exc.reason}: {detail}",
                status_code=exc.code,
            ) from exc
        except error.URLError as exc:
            raise BackendApiError(f"Backend API недоступен: {exc}") from exc

        if not raw:
            return {}

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise BackendApiError(f"Backend API вернул некорректный JSON: {raw!r}") from exc

    def resolve_contact(
        self,
        *,
        tenant_slug: str,
        contact_id: str,
        max_user_id: int | None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/access/resolve-contact",
            body={
                "tenant_slug": tenant_slug,
                "contact_id": contact_id,
                "max_user_id": max_user_id,
            },
        )

    def create_links(
        self,
        *,
        tenant_slug: str,
        contact_id: str,
        max_user_id: int,
        role: str,
        username: str | None,
        display_name: str | None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/access/links",
            body={
                "tenant_slug": tenant_slug,
                "contact_id": contact_id,
                "max_user_id": max_user_id,
                "role": role,
                "username": username,
                "display_name": display_name,
            },
        )

    def create_student_invite_link(
        self,
        *,
        tenant_slug: str,
        token: str,
        max_user_id: int,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/access/student-invite",
            body={
                "tenant_slug": tenant_slug,
                "token": token,
                "max_user_id": max_user_id,
                "username": username,
                "display_name": display_name,
            },
        )

    def revoke_stopped_bot_access(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/access/bot-stopped",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "reason": "bot_stopped",
            },
        )

    def update_access_link_status(
        self,
        *,
        tenant_slug: str,
        max_user_id: int | None,
        link_id: str,
        status: str,
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/miniapp/access-links/{parse.quote(link_id)}",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "status": status,
            },
        )

    def update_staff_assignment(
        self,
        *,
        tenant_slug: str,
        max_user_id: int | None,
        target_max_user_id: int,
        role: str,
        status: str,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/miniapp/staff/assignments",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "target_max_user_id": target_max_user_id,
                "role": role,
                "status": status,
                "username": username,
                "display_name": display_name,
            },
        )

    def redeem_staff_invitation(
        self,
        *,
        token: str,
        max_user_id: int,
        auth_tenant_slug: str,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/miniapp/staff/invitations/redeem",
            body={
                "token": token,
                "max_user_id": max_user_id,
                "username": username,
                "display_name": display_name,
            },
            auth_tenant_slug=auth_tenant_slug,
        )

    def get_staff_onboarding_options(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/miniapp/staff/onboarding/options",
            params={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
            },
        )

    def get_session(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/miniapp/session",
            params={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
            },
        )

    def discover_session(
        self,
        *,
        default_tenant_slug: str,
        max_user_id: int,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/miniapp/session",
            params={"max_user_id": max_user_id},
            auth_tenant_slug=default_tenant_slug,
        )

    def get_readiness(self) -> dict[str, Any]:
        return self._request("GET", "/ready")

    def get_catalog(
        self,
        *,
        tenant_slug: str,
        max_user_id: int | None = None,
        include_inactive: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/miniapp/catalog",
            params={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "include_inactive": "true" if include_inactive else None,
            },
        )

    def get_ops_summary(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        low_stock_threshold: int = 5,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/miniapp/ops/summary",
            params={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "low_stock_threshold": low_stock_threshold,
            },
        )

    def update_order(
        self,
        *,
        order_id: str,
        action: str,
        tenant_slug: str,
        max_user_id: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        if action not in {"cancel", "issue"}:
            raise ValueError(f"Unsupported order action: {action}")
        return self._request(
            "POST",
            f"/miniapp/orders/{parse.quote(str(order_id))}/{action}",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "comment": comment,
            },
        )

    def create_order(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        student_id: str,
        items: list[dict[str, Any]],
        comment: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/miniapp/orders",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "student_id": student_id,
                "items": items,
                "comment": comment,
            },
        )

    def accrue_astrocoins(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        student_ids: list[str],
        amount: int,
        reason: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/miniapp/coins/accrue",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "student_ids": student_ids,
                "amount": amount,
                "reason": reason,
                "comment": comment,
            },
        )

    def adjust_inventory(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        product_id: str,
        warehouse_id: str,
        available_quantity: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/miniapp/inventory/adjust",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "available_quantity": available_quantity,
                "comment": comment,
            },
        )

    def transfer_inventory(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        product_id: str,
        from_warehouse_id: str,
        to_warehouse_id: str,
        quantity: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/miniapp/inventory/transfer",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "product_id": product_id,
                "from_warehouse_id": from_warehouse_id,
                "to_warehouse_id": to_warehouse_id,
                "quantity": quantity,
                "comment": comment,
            },
        )

    def upsert_warehouse(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        slug: str,
        name: str,
        warehouse_type: str = "common",
        address: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/miniapp/warehouses",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "slug": slug,
                "name": name,
                "warehouse_type": warehouse_type,
                "address": address,
            },
        )

    def upsert_product(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        sku: str,
        name: str,
        category_name: str,
        price_astrocoins: int,
        status: str = "active",
        description: str | None = None,
        category_slug: str | None = None,
        photo_url: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/miniapp/products",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "sku": sku,
                "name": name,
                "category_name": category_name,
                "category_slug": category_slug,
                "price_astrocoins": price_astrocoins,
                "status": status,
                "description": description,
                "photo_url": photo_url,
            },
        )
