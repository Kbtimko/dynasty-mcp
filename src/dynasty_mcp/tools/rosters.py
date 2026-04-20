from __future__ import annotations

from typing import Any

from dynasty_mcp.context import Context
from dynasty_mcp.models import Player, RosterEntry, RosterSummary, RosterView, SlotType, TeamValueBreakdown, Value


TeamSpec = int | str  # "me" | roster_id | username


async def _resolve_roster(
    ctx: Context, league_id: str, team: TeamSpec
) -> tuple[dict[str, Any], dict[str, Any]]:
    rosters = await ctx.sleeper.get_rosters(league_id)
    users = await ctx.sleeper.get_league_users(league_id)

    def user_by_id(uid: str | None) -> dict[str, Any]:
        return next((u for u in users if u.get("user_id") == uid), {})

    def name_of(u: dict[str, Any]) -> str:
        return (u.get("username") or u.get("display_name") or "").lower()

    if team == "me":
        me = next((u for u in users if name_of(u) == ctx.username.lower()), None)
        if me is None:
            raise ValueError(f"username {ctx.username!r} not in league")
        roster = next((r for r in rosters if r.get("owner_id") == me["user_id"]), None)
        if roster is None:
            raise ValueError(f"no roster for {ctx.username!r}")
        return roster, me

    if isinstance(team, int):
        roster = next((r for r in rosters if int(r.get("roster_id", 0)) == team), None)
        if roster is None:
            raise ValueError(f"unknown team roster_id={team}")
        return roster, user_by_id(roster.get("owner_id"))

    # string: treat as username (with display_name fallback)
    target_user = next((u for u in users if name_of(u) == team.lower()), None)
    if target_user is None:
        raise ValueError(f"unknown team username={team!r}")
    roster = next(
        (r for r in rosters if r.get("owner_id") == target_user["user_id"]), None
    )
    if roster is None:
        raise ValueError(f"no roster for username={team!r}")
    return roster, target_user


def _classify(player_id: str, roster: dict[str, Any]) -> SlotType:
    if player_id in (roster.get("taxi") or []):
        return SlotType.TAXI
    if player_id in (roster.get("reserve") or []):
        return SlotType.IR
    if player_id in (roster.get("starters") or []):
        return SlotType.ACTIVE
    return SlotType.BENCH


def _player_from_sleeper(pid: str, data: dict[str, Any]) -> Player:
    full_name = (
        data.get("full_name")
        or " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p)
        or pid
    )
    return Player(
        player_id=pid,
        full_name=full_name,
        position=(data.get("position") or "UNK"),
        team=data.get("team"),
        age=data.get("age"),
        status=data.get("status"),
    )


def _value_map(fc_values: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in fc_values:
        player = row.get("player") or {}
        sid = str(player.get("sleeperId") or "")
        val = row.get("value")
        if sid and val is not None:
            out[sid] = int(val)
    return out


async def get_roster(ctx: Context, *, team: TeamSpec = "me") -> RosterView:
    if not ctx.league_id:
        raise ValueError("league_id required")
    league = await ctx.sleeper.get_league(ctx.league_id)
    roster, owner = await _resolve_roster(ctx, ctx.league_id, team)
    players = await ctx.sleeper.get_players()
    fc = await ctx.fantasycalc.get_current(league)
    values = _value_map(fc)

    entries: list[RosterEntry] = []
    total_active = total_taxi = total_ir = 0
    all_pids: list[str] = list(roster.get("players") or [])

    for pid in all_pids:
        data = players.get(pid, {})
        slot = _classify(pid, roster)
        val = values.get(pid)
        entries.append(
            RosterEntry(
                player=_player_from_sleeper(pid, data),
                slot_type=slot,
                value=Value(current=val),
                starter=pid in (roster.get("starters") or []),
            )
        )
        if val is None:
            continue
        if slot == SlotType.ACTIVE or slot == SlotType.BENCH:
            total_active += val
        elif slot == SlotType.TAXI:
            total_taxi += val
        elif slot == SlotType.IR:
            total_ir += val

    return RosterView(
        roster_id=int(roster.get("roster_id", 0)),
        owner_username=owner.get("username") or owner.get("display_name") or "",
        owner_display_name=owner.get("display_name"),
        entries=entries,
        total_value_active=total_active,
        total_value_taxi=total_taxi,
        total_value_ir=total_ir,
    )


async def list_rosters(ctx: Context) -> list[RosterSummary]:
    if not ctx.league_id:
        raise ValueError("league_id required")
    league = await ctx.sleeper.get_league(ctx.league_id)
    rosters = await ctx.sleeper.get_rosters(league_id=ctx.league_id)
    users = await ctx.sleeper.get_league_users(ctx.league_id)
    players = await ctx.sleeper.get_players()
    fc = await ctx.fantasycalc.get_current(league)
    values = _value_map(fc)

    by_user = {u["user_id"]: u for u in users}
    out: list[RosterSummary] = []
    for r in rosters:
        pids = r.get("players") or []
        total = sum(values.get(pid, 0) for pid in pids)
        ranked = sorted(pids, key=lambda pid: values.get(pid, 0), reverse=True)[:5]
        top = [
            _player_from_sleeper(pid, players.get(pid, {})).full_name
            for pid in ranked
        ]
        owner = by_user.get(r.get("owner_id"), {})
        out.append(
            RosterSummary(
                roster_id=int(r["roster_id"]),
                owner_username=owner.get("username") or owner.get("display_name") or "",
                total_value=total,
                top_assets=top,
            )
        )
    return out


def _age_cohort(age: int | None) -> str:
    if age is None:
        return "unknown"
    if age < 25:
        return "under_25"
    if age <= 28:
        return "25_28"
    return "29_plus"


async def get_team_value_breakdown(
    ctx: Context, *, team: TeamSpec = "me"
) -> TeamValueBreakdown:
    view = await get_roster(ctx, team=team)
    by_pos: dict[str, int] = {}
    by_age: dict[str, int] = {"under_25": 0, "25_28": 0, "29_plus": 0, "unknown": 0}
    for entry in view.entries:
        val = entry.value.current or 0
        by_pos[entry.player.position] = by_pos.get(entry.player.position, 0) + val
        by_age[_age_cohort(entry.player.age)] += val
    return TeamValueBreakdown(
        roster_id=view.roster_id,
        by_position=by_pos,
        by_age_cohort=by_age,
        taxi_stash_value=view.total_value_taxi,
        ir_value=view.total_value_ir,
        active_value=view.total_value_active,
    )
