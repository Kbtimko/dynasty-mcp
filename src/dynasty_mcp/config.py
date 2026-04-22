from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import platformdirs


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "dynasty-mcp" / "config.toml"

VALID_TRANSPORTS: frozenset[str] = frozenset({"stdio", "http", "streamable-http", "sse"})


@dataclass(frozen=True)
class Config:
    sleeper_username: str
    sleeper_league_id: str | None
    values_source: str
    cache_path: Path
    players_refresh_days: int
    values_refresh_hours: int
    transport: str
    host: str
    port: int


def _default_cache_path() -> Path:
    return Path(platformdirs.user_data_dir("dynasty-mcp")) / "cache.db"


def load_config(path: Path | None = None) -> Config:
    cfg_path = path or DEFAULT_CONFIG_PATH

    # Explicit path must exist. Default path is optional — env vars can substitute.
    if path is not None and not cfg_path.exists():
        raise ConfigError(f"Config file not found at {cfg_path}")

    raw: dict = {}
    if cfg_path.exists():
        with cfg_path.open("rb") as f:
            raw = tomllib.load(f)

    sleeper = raw.get("sleeper", {})
    username = os.environ.get("SLEEPER_USERNAME") or sleeper.get("username")
    if not username or not str(username).strip():
        raise ConfigError(
            "Missing required field: sleeper.username "
            "(set in config or SLEEPER_USERNAME env var)"
        )

    values = raw.get("values", {})
    cache = raw.get("cache", {})
    server = raw.get("server", {})

    cache_path_raw = cache.get("path")
    cache_path = Path(cache_path_raw).expanduser() if cache_path_raw else _default_cache_path()

    try:
        players_refresh_days = int(cache.get("players_refresh_days", 7))
        values_refresh_hours = int(cache.get("values_refresh_hours", 24))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid cache config value: {exc}") from exc

    transport = os.environ.get("DYNASTY_TRANSPORT") or server.get("transport", "stdio")
    if transport not in VALID_TRANSPORTS:
        raise ConfigError(
            f"Invalid server.transport {transport!r}: must be one of {sorted(VALID_TRANSPORTS)}"
        )
    host = os.environ.get("DYNASTY_HOST") or server.get("host", "0.0.0.0")
    try:
        port = int(os.environ.get("DYNASTY_PORT") or server.get("port", 8000))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid server.port: {exc}") from exc

    return Config(
        sleeper_username=str(username).strip(),
        sleeper_league_id=os.environ.get("SLEEPER_LEAGUE_ID") or sleeper.get("league_id"),
        values_source=values.get("source", "fantasycalc"),
        cache_path=cache_path,
        players_refresh_days=players_refresh_days,
        values_refresh_hours=values_refresh_hours,
        transport=transport,
        host=host,
        port=port,
    )
