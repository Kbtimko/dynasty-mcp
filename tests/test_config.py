from pathlib import Path
import tomllib

import pytest

from dynasty_mcp.config import Config, ConfigError, load_config


def write_toml(path: Path, body: str) -> None:
    path.write_text(body)


def test_loads_minimal_config(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "alice"\n')
    cfg = load_config(cfg_file)
    assert cfg.sleeper_username == "alice"
    assert cfg.sleeper_league_id is None
    assert cfg.values_source == "fantasycalc"
    assert cfg.players_refresh_days == 7
    assert cfg.values_refresh_hours == 24
    assert cfg.cache_path.name == "cache.db"


def test_loads_full_config(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(
        cfg_file,
        """
        [sleeper]
        username = "alice"
        league_id = "123"

        [values]
        source = "fantasycalc"

        [cache]
        path = "/tmp/override.db"
        players_refresh_days = 3
        values_refresh_hours = 6
        """,
    )
    cfg = load_config(cfg_file)
    assert cfg.sleeper_league_id == "123"
    assert cfg.cache_path == Path("/tmp/override.db")
    assert cfg.players_refresh_days == 3
    assert cfg.values_refresh_hours == 6


def test_missing_username_raises(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, "[sleeper]\n")
    with pytest.raises(ConfigError, match="sleeper.username"):
        load_config(cfg_file)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.toml")
