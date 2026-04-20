from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from dynasty_mcp.cache import Cache

BASE_URL = "https://api.fantasycalc.com"


def derive_params(league: dict[str, Any]) -> dict[str, Any]:
    positions = league.get("roster_positions") or []
    num_qbs = 2 if "SUPER_FLEX" in positions else 1
    num_teams = league.get("total_rosters", 12)
    ppr = float((league.get("scoring_settings") or {}).get("rec", 1.0))
    return {
        "isDynasty": "true",
        "numQbs": num_qbs,
        "numTeams": num_teams,
        "ppr": ppr,
    }


@dataclass
class FantasyCalcClient:
    cache: Cache
    refresh_hours: int = 24
    timeout: float = 30.0

    async def get_current(
        self, league: dict[str, Any], *, force: bool = False
    ) -> list[dict[str, Any]]:
        if not force and not self.cache.values_stale(self.refresh_hours):
            latest = self.cache.get_latest_values()
            if latest is not None:
                values, _ = latest
                return values

        params = derive_params(league)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=self.timeout) as c:
            resp = await c.get("/values/current", params=params)
            resp.raise_for_status()
            data = resp.json()
        self.cache.put_values_snapshot(data, fetched_at=datetime.now(timezone.utc))
        return data
