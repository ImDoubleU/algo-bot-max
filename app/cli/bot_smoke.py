from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app.bot.backend_client import AccessBackendClient
from app.bot.max_long_polling import simulate_callback, simulate_command
from app.core.config import get_settings, is_placeholder

DEFAULT_OFFLINE_COMMANDS = ("/start",)
DEFAULT_BACKEND_COMMANDS = ("/start",)
DEFAULT_CALLBACKS = ("help",)
PROFILE_COMMANDS = {
    "basic": DEFAULT_BACKEND_COMMANDS,
    "store": DEFAULT_BACKEND_COMMANDS,
    "ops": DEFAULT_BACKEND_COMMANDS,
}
PROFILE_CALLBACKS = {
    "basic": DEFAULT_CALLBACKS,
    "store": DEFAULT_CALLBACKS,
    "ops": ("help", "feedback"),
}
SMOKE_PROFILES = tuple(PROFILE_COMMANDS)
ALL_PROFILE = "all"
BACKEND_FAILURE_MARKERS = (
    "Backend API не подключен",
    "Не получилось",
    "MAX_BACKEND_API_BASE",
)


def response_summary(response: dict[str, Any]) -> dict[str, Any]:
    text = str(response.get("text") or "")
    attachments = response.get("attachments") or []
    return {
        "text_len": len(text),
        "first_line": text.splitlines()[0] if text else "",
        "attachments": len(attachments) if isinstance(attachments, list) else 0,
    }


def error_result(name: str, message: str, **details: Any) -> dict[str, Any]:
    return {
        "name": name,
        "status": "error",
        "first_line": message,
        "text_len": len(message),
        "attachments": 0,
        **details,
    }


def response_status(response: dict[str, Any], *, backend_required: bool) -> str:
    text = str(response.get("text") or "")
    if not text.strip():
        return "error"
    if backend_required and any(marker in text for marker in BACKEND_FAILURE_MARKERS):
        return "error"
    return "ok"


def profile_checks(profile: str) -> tuple[list[str], list[str]]:
    profiles = SMOKE_PROFILES if profile == ALL_PROFILE else (profile,)
    commands = list(
        dict.fromkeys(
            command
            for selected_profile in profiles
            for command in PROFILE_COMMANDS[selected_profile]
        )
    )
    callbacks = list(
        dict.fromkeys(
            payload
            for selected_profile in profiles
            for payload in PROFILE_CALLBACKS[selected_profile]
        )
    )
    return commands, callbacks


def run_command_check(
    *,
    command_text: str,
    user_id: int,
    backend_client: AccessBackendClient | None,
    default_tenant_slug: str,
    backend_required: bool,
) -> dict[str, Any]:
    name = f"command:{command_text}"
    try:
        response = simulate_command(
            command_text=command_text,
            user_id=user_id,
            backend_client=backend_client,
            default_tenant_slug=default_tenant_slug,
        )
    except Exception as exc:  # noqa: BLE001
        return error_result(name, str(exc), error_type=exc.__class__.__name__)

    status = response_status(response, backend_required=backend_required)
    result = {
        "name": name,
        "status": status,
        **response_summary(response),
    }
    if status != "ok":
        result["text"] = str(response.get("text") or "")
    return result


def run_callback_check(
    *,
    payload: str,
    user_id: int,
    backend_client: AccessBackendClient | None,
    default_tenant_slug: str,
    backend_required: bool,
) -> dict[str, Any]:
    name = f"callback:{payload}"
    try:
        response = simulate_callback(
            payload=payload,
            user_id=user_id,
            backend_client=backend_client,
            default_tenant_slug=default_tenant_slug,
        )
    except Exception as exc:  # noqa: BLE001
        return error_result(name, str(exc), error_type=exc.__class__.__name__)

    status = response_status(response, backend_required=backend_required)
    callback_id = response.get("callback_id")
    if not callback_id:
        status = "error"
    result = {
        "name": name,
        "status": status,
        "callback_answered": bool(callback_id),
        "notification": response.get("notification"),
        **response_summary(response),
    }
    if status != "ok":
        result["text"] = (
            str(response.get("text") or "")
            if callback_id
            else "Callback did not use answer_callback"
        )
    return result


def run_smoke(
    *,
    user_id: int,
    with_backend: bool,
    profile: str,
    commands: list[str] | None = None,
    callbacks: list[str] | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    default_tenant_slug = settings.default_tenant_slug

    has_explicit_checks = commands is not None or callbacks is not None

    if profile != "basic" and not with_backend and not has_explicit_checks:
        return [
            error_result(
                "smoke_profile",
                f"profile '{profile}' requires --with-backend or explicit --command/--callback",
            )
        ]

    backend_client: AccessBackendClient | None = None
    if with_backend:
        if is_placeholder(settings.max_backend_api_base):
            return [
                error_result(
                    "backend_config",
                    "MAX_BACKEND_API_BASE is not configured.",
                    mode="backend",
                )
            ]
        backend_client = AccessBackendClient(
            settings.max_backend_api_base,
            timeout_seconds=settings.max_backend_timeout_seconds,
        )

    results: list[dict[str, Any]] = []
    if has_explicit_checks:
        selected_commands = commands or []
        selected_callbacks = callbacks or []
    else:
        if with_backend:
            selected_commands, selected_callbacks = profile_checks(profile)
        else:
            selected_commands = list(DEFAULT_OFFLINE_COMMANDS)
            selected_callbacks = list(DEFAULT_CALLBACKS)

    for command_text in selected_commands:
        results.append(
            run_command_check(
                command_text=command_text,
                user_id=user_id,
                backend_client=backend_client,
                default_tenant_slug=default_tenant_slug,
                backend_required=with_backend,
            )
        )
    for payload in selected_callbacks:
        results.append(
            run_callback_check(
                payload=payload,
                user_id=user_id,
                backend_client=backend_client,
                default_tenant_slug=default_tenant_slug,
                backend_required=with_backend,
            )
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local smoke checks for MAX bot.")
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        help="MAX user_id for local simulation.",
    )
    parser.add_argument(
        "--with-backend",
        action="store_true",
        help="Use MAX_BACKEND_API_BASE and run smoke through the backend API client.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted((*SMOKE_PROFILES, ALL_PROFILE)),
        default="basic",
        help=(
            "Read-only smoke profile to run when explicit commands are not provided. "
            "Use all to run every backend scenario."
        ),
    )
    parser.add_argument(
        "--command",
        action="append",
        dest="commands",
        help="Additional or custom command to simulate. Can be passed multiple times.",
    )
    parser.add_argument(
        "--callback",
        action="append",
        dest="callbacks",
        help="Additional or custom callback payload to simulate. Can be passed multiple times.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON result.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    results = run_smoke(
        user_id=args.user_id,
        with_backend=args.with_backend,
        profile=args.profile,
        commands=args.commands,
        callbacks=args.callbacks,
    )
    has_errors = any(item["status"] != "ok" for item in results)

    if args.json:
        print(
            json.dumps(
                {"status": "error" if has_errors else "ok", "checks": results},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for item in results:
            print(f"{item['status']}: {item['name']} - {item['first_line']}")

    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
