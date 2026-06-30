from __future__ import annotations

from app.bot.max_long_polling import (
    AccessBackendClient,
    BackendApiError,
    LongPollingBot,
    MaxApiClient,
    MaxApiError,
    PendingContact,
    SimulationMaxClient,
    main,
    simulate_command,
)

__all__ = [
    "AccessBackendClient",
    "BackendApiError",
    "LongPollingBot",
    "MaxApiClient",
    "MaxApiError",
    "PendingContact",
    "SimulationMaxClient",
    "main",
    "simulate_command",
]


if __name__ == "__main__":
    raise SystemExit(main())
