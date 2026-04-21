from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from dynasty_mcp.context import Context
from dynasty_mcp.models import Player, Value
from dynasty_mcp.tools.league import _resolve_your_roster_id
from dynasty_mcp.tools.rosters import _player_from_sleeper, _value_map


class DraftPick(BaseModel):
    season: str
    round: int
    original_roster_id: int
    current_roster_id: int
    pick_number: int | None = None
    player: Player | None = None


class DraftView(BaseModel):
    draft_id: str
    status: Literal["pre_draft", "drafting", "completed"]
    season: str
    type: str
    my_picks: list[DraftPick]
    all_picks: list[DraftPick]
    rookie_pool: list[Player]


async def get_draft(
    ctx: Context, *, year: str | None = None
) -> DraftView:
    if not ctx.league_id:
        raise ValueError("league_id required")

    drafts = await ctx.sleeper.get_drafts(ctx.league_id)
    if not drafts:
        raise ValueError("no drafts found for league")
    if year:
        draft = next((d for d in drafts if str(d.get("season")) == str(year)), None)
        if draft is None:
            raise ValueError(f"no draft for year {year}")
    else:
        draft = next((d for d in drafts if d.get("status") == "pre_draft"), drafts[0])

    draft_id = draft["draft_id"]
    draft_full = await ctx.sleeper.get_draft(draft_id)
    picks_raw = await ctx.sleeper.get_draft_picks(draft_id)
    traded = await ctx.sleeper.get_traded_picks(ctx.league_id)
    my_roster_id = await _resolve_your_roster_id(ctx, ctx.league_id)

    league = await ctx.sleeper.get_league(ctx.league_id)
    players = await ctx.sleeper.get_players()
    rosters = await ctx.sleeper.get_rosters(ctx.league_id)
    fc = await ctx.fantasycalc.get_current(league)
    values = _value_map(fc)

    status = draft.get("status") or "pre_draft"
    season = str(draft.get("season") or "")
    draft_type = draft.get("type") or "snake"

    all_picks: list[DraftPick] = []
    if status == "completed" or picks_raw:
        for p in picks_raw:
            pid = p.get("player_id")
            all_picks.append(
                DraftPick(
                    season=season,
                    round=int(p.get("round") or 0),
                    original_roster_id=int(p.get("roster_id") or 0),
                    current_roster_id=int(p.get("roster_id") or 0),
                    pick_number=p.get("pick_no"),
                    player=_player_from_sleeper(pid, players.get(pid, {}))
                    if pid
                    else None,
                )
            )
    else:
        rounds = int((draft_full.get("settings") or {}).get("rounds") or 4)
        num_teams = int(league.get("total_rosters") or 12)
        pick_owner: dict[tuple[str, int, int], int] = {
            (season, r, roster_id): roster_id
            for r in range(1, rounds + 1)
            for roster_id in range(1, num_teams + 1)
        }
        for tp in traded:
            if str(tp.get("season")) != season:
                continue
            key = (season, int(tp["round"]), int(tp["roster_id"]))
            if key in pick_owner:
                pick_owner[key] = int(tp["owner_id"])
        for (s, r, orig), curr in pick_owner.items():
            all_picks.append(
                DraftPick(
                    season=s,
                    round=r,
                    original_roster_id=orig,
                    current_roster_id=curr,
                    pick_number=None,
                    player=None,
                )
            )

    my_picks = [p for p in all_picks if p.current_roster_id == my_roster_id]

    rostered = {pid for r in rosters for pid in (r.get("players") or [])}
    rookie_pool: list[Player] = []
    for pid, val in sorted(values.items(), key=lambda kv: kv[1], reverse=True):
        data = players.get(pid)
        if data is None or pid in rostered:
            continue
        if int(data.get("years_exp") or 99) != 0:
            continue
        rookie_pool.append(_player_from_sleeper(pid, data))

    return DraftView(
        draft_id=draft_id,
        status=status,  # type: ignore[arg-type]
        season=season,
        type=draft_type,
        my_picks=my_picks,
        all_picks=all_picks,
        rookie_pool=rookie_pool,
    )
