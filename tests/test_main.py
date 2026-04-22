from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.config import Config, ConfigError
from dynasty_mcp.sources.sleeper import SleeperClient
from dynasty_mcp.__main__ import _resolve_league_id

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def cache(tmp_path: Path) -> Cache:
    return Cache.open(tmp_path / "cache.db")


@pytest.fixture
def client(cache: Cache) -> SleeperClient:
    return SleeperClient(cache=cache, refresh_days=7)


@pytest.mark.asyncio
async def test_resolve_league_id_raises_on_unknown_user(client: SleeperClient) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        mock.get("/user/nobody").respond(content=b"null", headers={"content-type": "application/json"})
        with pytest.raises(ConfigError, match="nobody"):
            await _resolve_league_id(client, "nobody", "2025")


@pytest.mark.asyncio
async def test_resolve_league_id_returns_single_league(client: SleeperClient) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as mock:
        mock.get("/user/dakeif").respond(json=load("sleeper_user.json"))
        user_id = load("sleeper_user.json")["user_id"]
        leagues = load("sleeper_user_leagues.json")[:1]
        mock.get(f"/user/{user_id}/leagues/nfl/2025").respond(json=leagues)
        result = await _resolve_league_id(client, "dakeif", "2025")
        assert result == leagues[0]["league_id"]


def test_http_transport_calls_run_with_args(tmp_path: Path) -> None:
    """When transport=http, server.run() receives transport/host/port."""
    from dynasty_mcp.__main__ import main

    http_config = Config(
        sleeper_username="dakeif",
        sleeper_league_id="123",
        values_source="fantasycalc",
        cache_path=tmp_path / "cache.db",
        players_refresh_days=7,
        values_refresh_hours=24,
        transport="http",
        host="0.0.0.0",
        port=8000,
    )
    mock_server = MagicMock()

    with (
        patch("dynasty_mcp.__main__.load_config", return_value=http_config),
        patch("dynasty_mcp.__main__.Cache"),
        patch("dynasty_mcp.__main__.SleeperClient"),
        patch("dynasty_mcp.__main__.FantasyCalcClient"),
        patch("dynasty_mcp.__main__.build_server", return_value=mock_server),
        patch("asyncio.run", return_value={"season": "2025"}),
    ):
        main()

    mock_server.run.assert_called_once_with(transport="http", host="0.0.0.0", port=8000)


def test_stdio_transport_calls_run_no_args(tmp_path: Path) -> None:
    """When transport=stdio, server.run() is called with no args."""
    from dynasty_mcp.__main__ import main

    stdio_config = Config(
        sleeper_username="dakeif",
        sleeper_league_id="123",
        values_source="fantasycalc",
        cache_path=tmp_path / "cache.db",
        players_refresh_days=7,
        values_refresh_hours=24,
        transport="stdio",
        host="0.0.0.0",
        port=8000,
    )
    mock_server = MagicMock()

    with (
        patch("dynasty_mcp.__main__.load_config", return_value=stdio_config),
        patch("dynasty_mcp.__main__.Cache"),
        patch("dynasty_mcp.__main__.SleeperClient"),
        patch("dynasty_mcp.__main__.FantasyCalcClient"),
        patch("dynasty_mcp.__main__.build_server", return_value=mock_server),
        patch("asyncio.run", return_value={"season": "2025"}),
    ):
        main()

    mock_server.run.assert_called_once_with()
