from __future__ import annotations

from app.bot.backend_client import AccessBackendClient, BackendApiError
from app.bot.max_client import MaxApiClient, MaxApiError, SimulationMaxClient
from app.bot.max_long_polling import (
    LongPollingBot,
    main,
    simulate_callback,
    simulate_command,
)
from app.bot.models import BotResponse, PendingContact

__all__ = [
    "AccessBackendClient",
    "BackendApiError",
    "BotResponse",
    "LongPollingBot",
    "MaxApiClient",
    "MaxApiError",
    "PendingContact",
    "SimulationMaxClient",
    "main",
    "simulate_callback",
    "simulate_command",
]


if __name__ == "__main__":
    raise SystemExit(main())
