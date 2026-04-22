from pathlib import Path

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


def test_whitespace_username_raises(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "   "\n')
    with pytest.raises(ConfigError, match="sleeper.username"):
        load_config(cfg_file)


def test_invalid_refresh_value_raises(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(
        cfg_file,
        """
        [sleeper]
        username = "alice"

        [cache]
        players_refresh_days = "not-a-number"
        """,
    )
    with pytest.raises(ConfigError, match="Invalid cache config"):
        load_config(cfg_file)


def test_server_defaults_when_section_absent(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "alice"\n')
    cfg = load_config(cfg_file)
    assert cfg.transport == "stdio"
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8000


def test_server_section_parsed(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(
        cfg_file,
        """
        [sleeper]
        username = "alice"

        [server]
        transport = "http"
        host = "127.0.0.1"
        port = 9000
        """,
    )
    cfg = load_config(cfg_file)
    assert cfg.transport == "http"
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 9000


def test_env_var_overrides_transport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DYNASTY_TRANSPORT", "http")
    monkeypatch.setenv("DYNASTY_HOST", "10.0.0.1")
    monkeypatch.setenv("DYNASTY_PORT", "7777")
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "alice"\n')
    cfg = load_config(cfg_file)
    assert cfg.transport == "http"
    assert cfg.host == "10.0.0.1"
    assert cfg.port == 7777


def test_env_var_overrides_sleeper_username(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLEEPER_USERNAME", "envuser")
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, "[sleeper]\n")  # no username in file
    cfg = load_config(cfg_file)
    assert cfg.sleeper_username == "envuser"


def test_env_var_overrides_sleeper_league_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLEEPER_LEAGUE_ID", "999")
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "alice"\n')
    cfg = load_config(cfg_file)
    assert cfg.sleeper_league_id == "999"


def test_default_path_missing_uses_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("dynasty_mcp.config.DEFAULT_CONFIG_PATH", tmp_path / "missing.toml")
    monkeypatch.setenv("SLEEPER_USERNAME", "envuser")
    cfg = load_config()  # no path arg; file does not exist
    assert cfg.sleeper_username == "envuser"
    assert cfg.transport == "stdio"  # default


def test_invalid_dynasty_port_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DYNASTY_PORT", "not-a-number")
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "alice"\n')
    with pytest.raises(ConfigError, match="server.port"):
        load_config(cfg_file)


def test_invalid_transport_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DYNASTY_TRANSPORT", "websocket")
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "alice"\n')
    with pytest.raises(ConfigError, match="server.transport"):
        load_config(cfg_file)
