from __future__ import annotations

from typing import Any

from dynasty_mcp.context import Context
from dynasty_mcp.models import LeagueContext


def _season_phase(state: dict[str, Any]) -> str:
    st = (state.get("season_type") or "").lower()
    if st in ("pre", "regular", "post"):
        return st
    return "offseason"


def _taxi_slots(league: dict[str, Any]) -> int:
    settings = league.get("settings") or {}
    return int(settings.get("taxi_slots", 0))


def _ir_slots(league: dict[str, Any]) -> int:
    settings = league.get("settings") or {}
    return int(settings.get("reserve_slots", 0))


def _count_position_slots(positions: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in positions:
        if p == "BN":
            continue
        counts[p] = counts.get(p, 0) + 1
    return counts


def _bench_slots(positions: list[str]) -> int:
    return sum(1 for p in positions if p == "BN")


async def _resolve_your_roster_id(ctx: Context, league_id: str) -> int:
    users = await ctx.sleeper.get_league_users(league_id)
    # Sleeper's /league/{id}/users response omits the `username` field; it only
    # has `display_name`.  Match on `username` first (future-proof), then fall
    # back to `display_name` so the function works with real fixture data.
    user = next(
        (
            u
            for u in users
            if (u.get("username") or u.get("display_name") or "").lower()
            == ctx.username.lower()
        ),
        None,
    )
    if user is None:
        raise ValueError(
            f"Username {ctx.username!r} not found among league members"
        )
    rosters = await ctx.sleeper.get_rosters(league_id)
    mine = next((r for r in rosters if r.get("owner_id") == user["user_id"]), None)
    if mine is None:
        raise ValueError(f"No roster for user {user['user_id']} in league {league_id}")
    return int(mine["roster_id"])


async def get_league_context(ctx: Context) -> LeagueContext:
    if not ctx.league_id:
        raise ValueError("league_id must be set — config or resolve from username")
    league = await ctx.sleeper.get_league(ctx.league_id)
    state = await ctx.sleeper.get_state()
    positions = league.get("roster_positions") or []
    scoring = league.get("scoring_settings") or {}
    your_roster_id = await _resolve_your_roster_id(ctx, ctx.league_id)

    return LeagueContext(
        league_id=ctx.league_id,
        season=str(league.get("season") or ctx.season),
        current_week=int(state.get("week") or 0),
        season_phase=_season_phase(state),  # type: ignore[arg-type]
        num_teams=int(league.get("total_rosters") or 12),
        num_qbs=2 if "SUPER_FLEX" in positions else 1,
        ppr=float(scoring.get("rec", 1.0)),
        roster_slots=_count_position_slots(positions),
        taxi_slots=_taxi_slots(league),
        bench_slots=_bench_slots(positions),
        ir_slots=_ir_slots(league),
        your_roster_id=your_roster_id,
    )
