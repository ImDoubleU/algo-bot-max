import logging
import subprocess
import sys

import pytest
from alembic.config import Config

from alembic import command
from app.core.config import get_settings


@pytest.fixture
def migration_database(tmp_path, monkeypatch):
    path = tmp_path / "migration-logging.db"
    monkeypatch.setenv("DATABASE_SYNC_URL", f"sqlite:///{path.as_posix()}")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{path.as_posix()}")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_embedded_migration_preserves_host_logging(migration_database, caplog):
    config = Config("alembic.ini")
    config.attributes["configure_logger"] = False
    root = logging.getLogger()
    logger = logging.getLogger("app.core.binding_diagnostics")
    with caplog.at_level(logging.INFO, logger=logger.name):
        handlers, level, disabled = list(root.handlers), root.level, logger.disabled
        command.upgrade(config, "base")
        assert root.handlers == handlers
        assert root.level == level
        assert logger.disabled == disabled
        logger.info("embedded_migration_logging_preserved")
    assert "embedded_migration_logging_preserved" in caplog.text


def test_cli_migration_does_not_disable_application_loggers(migration_database):
    # Run CLI-style logging setup in its own process, just like deployment.
    script = """
import logging
from alembic import command
from alembic.config import Config

logger = logging.getLogger("app.core.binding_diagnostics")
logger.setLevel(logging.INFO)
command.upgrade(Config("alembic.ini"), "base")
assert not logger.disabled
logger.info("cli_migration_logging_preserved")
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "cli_migration_logging_preserved" in result.stderr
