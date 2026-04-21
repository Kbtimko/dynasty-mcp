from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from dynasty_mcp.cache import Cache

BASE_URL = "https://api.sleeper.app/v1"

# Transient-error classes we retry once with backoff.
_TRANSIENT = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.RemoteProtocolError,
)


@dataclass
class SleeperClient:
    cache: Cache
    refresh_days: int = 7
    timeout: float = 30.0

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=self.timeout) as c:
            try:
                resp = await c.get(path, params=params)
            except _TRANSIENT:
                await asyncio.sleep(1.0)
                resp = await c.get(path, params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_state(self) -> dict[str, Any]:
        return await self._get("/state/nfl")

    async def get_user(self, username_or_id: str) -> dict[str, Any]:
        return await self._get(f"/user/{username_or_id}")

    async def get_user_leagues(self, user_id: str, season: str) -> list[dict[str, Any]]:
        return await self._get(f"/user/{user_id}/leagues/nfl/{season}")

    async def get_league(self, league_id: str) -> dict[str, Any]:
        return await self._get(f"/league/{league_id}")

    async def get_rosters(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/rosters")

    async def get_league_users(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/users")

    async def get_matchups(self, league_id: str, week: int) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/matchups/{week}")

    async def get_transactions(self, league_id: str, week: int) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/transactions/{week}")

    async def get_traded_picks(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/traded_picks")

    async def get_drafts(self, league_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/league/{league_id}/drafts")

    async def get_draft(self, draft_id: str) -> dict[str, Any]:
        return await self._get(f"/draft/{draft_id}")

    async def get_draft_picks(self, draft_id: str) -> list[dict[str, Any]]:
        return await self._get(f"/draft/{draft_id}/picks")

    async def get_trending(
        self, kind: str, *, lookback_hours: int = 24, limit: int = 25
    ) -> list[dict[str, Any]]:
        return await self._get(
            f"/players/nfl/trending/{kind}",
            params={"lookback_hours": lookback_hours, "limit": limit},
        )

    async def get_players(self, *, force: bool = False) -> dict[str, Any]:
        cached, _ = self.cache.get_players()
        if cached is not None and not force and not self.cache.players_stale(
            self.refresh_days
        ):
            return cached
        try:
            data = await self._get("/players/nfl")
        except (httpx.HTTPError, *_TRANSIENT):
            # Upstream unreachable or erroring: fall back to stale cache if we
            # have one, otherwise re-raise. Callers inspect players_stale() if
            # they need to report staleness to the user.
            if cached is not None:
                return cached
            raise
        self.cache.put_players(data, fetched_at=datetime.now(timezone.utc))
        return data
