from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib import error, request
from urllib.parse import urlsplit

from app.core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
SQLITE_ENV_EXAMPLE = PROJECT_ROOT / ".env.sqlite.example"
TMP_DIR = PROJECT_ROOT / "tmp"
BACKEND_SMOKE_PROFILES = ("basic", "store", "ops")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a local SQLite development profile for the MAX bot.",
    )
    parser.add_argument(
        "--max-user-id",
        type=int,
        default=1,
        help="MAX user_id for demo access links, staff bootstrap and smoke checks.",
    )
    parser.add_argument(
        "--force-env",
        action="store_true",
        help="Overwrite .env from .env.sqlite.example.",
    )
    parser.add_argument(
        "--skip-env",
        action="store_true",
        help="Do not create or update .env.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Use this env file for child commands without copying it to .env.",
    )
    parser.add_argument("--skip-migrations", action="store_true")
    parser.add_argument("--skip-seed", action="store_true")
    parser.add_argument("--skip-staff", action="store_true")
    parser.add_argument("--skip-doctor", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument(
        "--with-backend-smoke",
        action="store_true",
        help="Run bot_smoke through MAX_BACKEND_API_BASE. Requires backend API to be running.",
    )
    parser.add_argument(
        "--backend-smoke-profile",
        choices=(*BACKEND_SMOKE_PROFILES, "all"),
        default="basic",
        help="Read-only bot_smoke profile for backend smoke runs. Use all for every profile.",
    )
    parser.add_argument(
        "--start-backend-smoke",
        action="store_true",
        help="Temporarily start uvicorn and run backend smoke against it.",
    )
    parser.add_argument(
        "--allow-non-sqlite",
        action="store_true",
        help="Allow migrations and seed against the current non-SQLite DATABASE_URL.",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=8000,
        help="Local API port for --start-backend-smoke.",
    )
    parser.add_argument(
        "--api-start-timeout",
        type=int,
        default=20,
        help="Seconds to wait for local API health during --start-backend-smoke.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without modifying files or running commands.",
    )
    return parser.parse_args()


def print_step(message: str) -> None:
    print(f"[dev-bootstrap] {message}", flush=True)


def resolve_env_file(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_absolute() else PROJECT_ROOT / path


def ensure_env(*, env_file: Path | None, force: bool, skip: bool, dry_run: bool) -> None:
    if env_file is not None:
        if not env_file.exists():
            raise SystemExit(f"{env_file} not found")
        print_step(f"use env file: {env_file}")
        return
    if skip:
        print_step("skip .env setup")
        return
    if not SQLITE_ENV_EXAMPLE.exists():
        raise SystemExit(".env.sqlite.example not found")
    if ENV_FILE.exists() and not force:
        print_step(".env already exists; keep it. Use --force-env to overwrite.")
        return

    action = f"copy {SQLITE_ENV_EXAMPLE.name} -> .env"
    if dry_run:
        print_step(f"dry-run: {action}")
        return

    shutil.copyfile(SQLITE_ENV_EXAMPLE, ENV_FILE)
    print_step(action)


def ensure_tmp(*, dry_run: bool) -> None:
    if dry_run:
        print_step("dry-run: create tmp directory")
        return
    TMP_DIR.mkdir(exist_ok=True)
    print_step("tmp directory is ready")


def read_env_file(env_path: Path = ENV_FILE) -> dict[str, str]:
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip().strip("'\"")
    return values


def planned_env_path(
    *,
    env_file: Path | None,
    force: bool,
    skip: bool,
    dry_run: bool,
) -> Path:
    if env_file is not None:
        return env_file
    if skip:
        return ENV_FILE
    if dry_run and (force or not ENV_FILE.exists()):
        return SQLITE_ENV_EXAMPLE
    return ENV_FILE


def bootstrap_environment(env_path: Path) -> dict[str, str]:
    env_values = read_env_file(env_path)
    if env_values:
        print_step(f"{env_path.name} values will be used for child commands")
    return {**os.environ, **env_values}


def database_scheme(database_url: str | None) -> str:
    if not database_url:
        return ""
    return urlsplit(database_url).scheme


def ensure_sqlite_profile(
    *,
    env: dict[str, str],
    allow_non_sqlite: bool,
    dry_run: bool,
) -> None:
    scheme = database_scheme(env.get("DATABASE_URL") or get_settings().database_url)
    if scheme.startswith("sqlite"):
        print_step(f"database profile: {scheme}")
        return
    if allow_non_sqlite:
        print_step(f"database profile: {scheme or 'unknown'} (--allow-non-sqlite)")
        return
    if dry_run:
        print_step(
            "dry-run warning: current DATABASE_URL is not SQLite; real run would stop "
            "unless --force-env or --allow-non-sqlite is used."
        )
        return
    raise SystemExit(
        "[dev-bootstrap] current DATABASE_URL is not SQLite. "
        "Use --force-env to copy .env.sqlite.example "
        "or --allow-non-sqlite to explicitly run against the current database."
    )


def run_command(command: list[str], *, dry_run: bool, env: dict[str, str] | None = None) -> None:
    printable = " ".join(command)
    if dry_run:
        print_step(f"dry-run: {printable}")
        return

    print_step(printable)
    try:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True, env=env)
    except subprocess.CalledProcessError as exc:
        message = f"[dev-bootstrap] command failed ({exc.returncode}): {printable}"
        raise SystemExit(message) from None


def selected_backend_smoke_profiles(profile: str) -> tuple[str, ...]:
    if profile == "all":
        return ("all",)
    return (profile,)


def wait_for_health(
    url: str,
    *,
    timeout: int,
    process: subprocess.Popen[bytes] | None = None,
) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"Backend exited before healthcheck: code={process.returncode}")
        try:
            with request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except (OSError, error.URLError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"Backend did not become healthy at {url}: {last_error}")


def run_backend_smoke_with_temp_api(
    *,
    python: str,
    user_id: int,
    profile: str,
    port: int,
    timeout: int,
    dry_run: bool,
    env: dict[str, str],
) -> None:
    api_base = f"http://127.0.0.1:{port}/api/v1"
    health_url = f"{api_base}/health"
    uvicorn_command = [
        python,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    profiles = selected_backend_smoke_profiles(profile)
    backend_env = {**env, "MAX_BACKEND_API_BASE": api_base}

    if dry_run:
        print_step(f"dry-run: start {' '.join(uvicorn_command)}")
        print_step(f"dry-run: wait for {health_url}")
        for selected_profile in profiles:
            run_command(
                [
                    python,
                    "-m",
                    "app.cli.bot_smoke",
                    "--with-backend",
                    "--user-id",
                    str(user_id),
                    "--profile",
                    selected_profile,
                ],
                dry_run=True,
                env=backend_env,
            )
        print_step("dry-run: stop temporary backend")
        return

    print_step(f"start temporary backend on {api_base}")
    process = subprocess.Popen(
        uvicorn_command,
        cwd=PROJECT_ROOT,
        env=backend_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_health(health_url, timeout=timeout, process=process)
        for selected_profile in profiles:
            run_command(
                [
                    python,
                    "-m",
                    "app.cli.bot_smoke",
                    "--with-backend",
                    "--user-id",
                    str(user_id),
                    "--profile",
                    selected_profile,
                ],
                dry_run=False,
                env=backend_env,
            )
    except RuntimeError as exc:
        raise SystemExit(f"[dev-bootstrap] backend startup failed: {exc}") from None
    finally:
        print_step("stop temporary backend")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    python = sys.executable
    env_file = resolve_env_file(args.env_file)

    ensure_env(env_file=env_file, force=args.force_env, skip=args.skip_env, dry_run=args.dry_run)
    ensure_tmp(dry_run=args.dry_run)
    env = bootstrap_environment(
        planned_env_path(
            env_file=env_file,
            force=args.force_env,
            skip=args.skip_env,
            dry_run=args.dry_run,
        )
    )
    ensure_sqlite_profile(env=env, allow_non_sqlite=args.allow_non_sqlite, dry_run=args.dry_run)

    if not args.skip_migrations:
        run_command([python, "-m", "alembic", "upgrade", "head"], dry_run=args.dry_run, env=env)
    if not args.skip_seed:
        run_command(
            [python, "-m", "app.cli.seed_store", "--max-user-id", str(args.max_user_id)],
            dry_run=args.dry_run,
            env=env,
        )
    if not args.skip_staff:
        run_command(
            [
                python,
                "-m",
                "app.cli.bootstrap_superadmin",
                "--max-user-id",
                str(args.max_user_id),
            ],
            dry_run=args.dry_run,
            env=env,
        )
    if not args.skip_doctor:
        run_command(
            [python, "-m", "app.cli.doctor", "--allow-missing-bot-token"],
            dry_run=args.dry_run,
            env=env,
        )
    if not args.skip_smoke:
        smoke_command = [python, "-m", "app.cli.bot_smoke", "--user-id", str(args.max_user_id)]
        if args.with_backend_smoke:
            for selected_profile in selected_backend_smoke_profiles(args.backend_smoke_profile):
                run_command(
                    [
                        *smoke_command,
                        "--with-backend",
                        "--profile",
                        selected_profile,
                    ],
                    dry_run=args.dry_run,
                    env=env,
                )
        else:
            run_command(smoke_command, dry_run=args.dry_run, env=env)
    if args.start_backend_smoke:
        run_backend_smoke_with_temp_api(
            python=python,
            user_id=args.max_user_id,
            profile=args.backend_smoke_profile,
            port=args.api_port,
            timeout=args.api_start_timeout,
            dry_run=args.dry_run,
            env=env,
        )

    print_step("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
