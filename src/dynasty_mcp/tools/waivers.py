from __future__ import annotations

from typing import Literal

from dynasty_mcp.context import Context
from dynasty_mcp.tools.rosters import _player_from_sleeper, _value_map
from dynasty_mcp.tools.values import PlayerValueRow
from dynasty_mcp.models import TrendingRow, Value


async def get_free_agents(
    ctx: Context,
    *,
    position: str | None = None,
    min_value: int = 0,
    limit: int = 25,
) -> list[PlayerValueRow]:
    if not ctx.league_id:
        raise ValueError("league_id required")
    league = await ctx.sleeper.get_league(ctx.league_id)
    rosters = await ctx.sleeper.get_rosters(ctx.league_id)
    players = await ctx.sleeper.get_players()
    fc = await ctx.fantasycalc.get_current(league)
    values = _value_map(fc)

    rostered: set[str] = set()
    for r in rosters:
        rostered.update(r.get("players") or [])

    rows: list[PlayerValueRow] = []
    for pid, val in sorted(values.items(), key=lambda kv: kv[1], reverse=True):
        if pid in rostered:
            continue
        if val < min_value:
            continue
        data = players.get(pid)
        if data is None:
            continue
        if position and data.get("position") != position:
            continue
        rows.append(
            PlayerValueRow(
                player=_player_from_sleeper(pid, data),
                value=Value(current=val),
            )
        )
        if len(rows) >= limit:
            break
    return rows


async def get_trending(
    ctx: Context,
    *,
    window: Literal["24h", "7d"] = "24h",
    type: Literal["add", "drop"] = "add",
    limit: int = 25,
) -> list[TrendingRow]:
    lookback = 24 if window == "24h" else 24 * 7
    raw = await ctx.sleeper.get_trending(type, lookback_hours=lookback, limit=limit)
    players = await ctx.sleeper.get_players()
    out: list[TrendingRow] = []
    for row in raw:
        pid = str(row.get("player_id") or "")
        data = players.get(pid)
        if data is None:
            continue
        out.append(
            TrendingRow(
                player=_player_from_sleeper(pid, data),
                count=int(row.get("count") or 0),
            )
        )
    return out
