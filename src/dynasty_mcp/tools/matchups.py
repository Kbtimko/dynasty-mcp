from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from dynasty_mcp.context import Context
from dynasty_mcp.models import Player, RosterEntry, SlotType, Value
from dynasty_mcp.tools.league import _resolve_your_roster_id
from dynasty_mcp.tools.rosters import _player_from_sleeper, _value_map


class MatchupView(BaseModel):
    week: int
    my_roster_id: int
    opponent_roster_id: int | None
    my_starters: list[RosterEntry]
    opponent_starters: list[RosterEntry] | None
    my_bench_value: int
    opponent_bench_value: int | None


async def _fetch_projections(season: str, week: int) -> dict[str, float]:
    try:
        async with httpx.AsyncClient(
            base_url="https://api.sleeper.com", timeout=15
        ) as c:
            resp = await c.get(
                f"/projections/nfl/{season}/{week}",
                params=[
                    ("season_type", "regular"),
                    ("position[]", "QB"),
                    ("position[]", "RB"),
                    ("position[]", "WR"),
                    ("position[]", "TE"),
                    ("position[]", "K"),
                    ("position[]", "DEF"),
                ],
            )
            resp.raise_for_status()
            rows = resp.json() or []
    except (httpx.HTTPError, ValueError):
        return {}
    out: dict[str, float] = {}
    for row in rows:
        pid = str(row.get("player_id") or "")
        stats = row.get("stats") or {}
        pts = stats.get("pts_ppr") or stats.get("pts_half_ppr") or stats.get("pts_std")
        if pid and pts is not None:
            out[pid] = float(pts)
    return out


async def get_matchup(ctx: Context, *, week: int | None = None) -> MatchupView:
    if not ctx.league_id:
        raise ValueError("league_id required")
    state = await ctx.sleeper.get_state()
    resolved_week = int(week if week is not None else state.get("week") or 1)

    league = await ctx.sleeper.get_league(ctx.league_id)
    rosters = await ctx.sleeper.get_rosters(ctx.league_id)
    matchups = await ctx.sleeper.get_matchups(ctx.league_id, resolved_week)
    players = await ctx.sleeper.get_players()
    fc = await ctx.fantasycalc.get_current(league)
    values = _value_map(fc)
    my_roster_id = await _resolve_your_roster_id(ctx, ctx.league_id)
    projections = await _fetch_projections(
        str(league.get("season") or ctx.season), resolved_week
    )

    my_match = next(
        (m for m in matchups if int(m.get("roster_id", 0)) == my_roster_id), None
    )
    if my_match is None:
        raise ValueError(f"no matchup for roster {my_roster_id} in week {resolved_week}")
    matchup_id = my_match.get("matchup_id")
    opp_match = next(
        (
            m
            for m in matchups
            if m.get("matchup_id") == matchup_id
            and int(m.get("roster_id", 0)) != my_roster_id
        ),
        None,
    )

    def build(match: dict[str, Any]) -> tuple[list[RosterEntry], int]:
        starters = [pid for pid in (match.get("starters") or []) if pid]
        all_players = match.get("players") or []
        starter_set = set(starters)
        entries = [
            RosterEntry(
                player=_player_from_sleeper(pid, players.get(pid, {})),
                slot_type=SlotType.ACTIVE,
                value=Value(current=values.get(pid), delta_7d=None),
                starter=True,
                projection=projections.get(pid),
            )
            for pid in starters
        ]
        bench_value = sum(
            values.get(pid, 0) for pid in all_players if pid not in starter_set
        )
        return entries, bench_value

    my_entries, my_bench = build(my_match)
    if opp_match is None:
        return MatchupView(
            week=resolved_week,
            my_roster_id=my_roster_id,
            opponent_roster_id=None,
            my_starters=my_entries,
            opponent_starters=None,
            my_bench_value=my_bench,
            opponent_bench_value=None,
        )
    opp_entries, opp_bench = build(opp_match)
    return MatchupView(
        week=resolved_week,
        my_roster_id=my_roster_id,
        opponent_roster_id=int(opp_match.get("roster_id", 0)),
        my_starters=my_entries,
        opponent_starters=opp_entries,
        my_bench_value=my_bench,
        opponent_bench_value=opp_bench,
    )
