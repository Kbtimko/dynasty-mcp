from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

from dynasty_mcp.context import Context
from dynasty_mcp.models import (
    ResetTradeFinderResult,
    RosterEntry,
    SlotType,
    TradeAsset,
    TradeProposal,
)
from dynasty_mcp.reset_scoring import (
    asset_value_under_reset,
    pick_value_under_reset,
    rank_slates,
)
from dynasty_mcp.tools.rosters import TeamSpec, _classify, _player_from_sleeper, _resolve_roster, _value_map


@dataclass
class _PlayerAsset:
    entry: RosterEntry
    owner_id: int


@dataclass
class _PickAsset:
    asset_id: str
    display_name: str
    season: str
    round_: int
    base_value: int
    owner_id: int


_Asset = _PlayerAsset | _PickAsset


def _pick_display_name(season: str, round_: int) -> str:
    if round_ == 1:
        return f"{season} Mid 1st"
    ordinals = {2: "2nd", 3: "3rd", 4: "4th", 5: "5th"}
    return f"{season} {ordinals.get(round_, f'{round_}th')}"


def _build_pick_value_map(fc_values: list[dict]) -> dict[str, int]:
    """Return {display_name: value} for FC rows that have no sleeperId (picks)."""
    result: dict[str, int] = {}
    for row in fc_values:
        player = row.get("player") or {}
        if not player.get("sleeperId"):
            name = player.get("name") or ""
            val = row.get("value")
            if name and val is not None:
                result[name] = int(val)
    return result


def _build_pick_pool(
    roster_ids: list[int],
    traded_picks: list[dict[str, Any]],
    seasons: list[str],
    rounds: list[int],
    pick_value_map: dict[str, int],
) -> list[_PickAsset]:
    """Build all picks with default ownership, then apply traded-pick overrides."""
    picks: dict[str, _PickAsset] = {}
    for rid in roster_ids:
        for season in seasons:
            for round_ in rounds:
                asset_id = f"{season}_{round_}_from_r{rid}"
                display_name = _pick_display_name(season, round_)
                picks[asset_id] = _PickAsset(
                    asset_id=asset_id,
                    display_name=display_name,
                    season=season,
                    round_=round_,
                    base_value=pick_value_map.get(display_name, 0),
                    owner_id=rid,
                )
    for tp in traded_picks:
        rid = tp.get("roster_id")
        round_ = tp.get("round")
        season = str(tp.get("season", ""))
        new_owner = tp.get("owner_id")
        if rid is None or round_ is None or not season or new_owner is None:
            continue
        asset_id = f"{season}_{round_}_from_r{rid}"
        if asset_id in picks:
            old = picks[asset_id]
            picks[asset_id] = _PickAsset(
                asset_id=old.asset_id,
                display_name=old.display_name,
                season=old.season,
                round_=old.round_,
                base_value=old.base_value,
                owner_id=int(new_owner),
            )
    return list(picks.values())


def _slate_slot_map(slate) -> dict[str, str]:
    if slate is None:
        return {}
    return {
        "qb": slate.qb.player.player_id,
        "rb_te": slate.rb_te.player.player_id,
        "wr_te": slate.wr_te.player.player_id,
    }


def _slate_all_ids(slate) -> set[str]:
    if slate is None:
        return set()
    return {
        slate.qb.player.player_id,
        slate.rb_te.player.player_id,
        slate.wr_te.player.player_id,
        *[t.player.player_id for t in slate.taxi],
    }


def _to_trade_asset(
    asset: _Asset,
    receiver_post_entries: list[RosterEntry],
    receiver_post_slate_ids: set[str],
    probability: float,
    current_season: str,
) -> TradeAsset:
    if isinstance(asset, _PlayerAsset):
        return TradeAsset(
            kind="player",
            asset_id=asset.entry.player.player_id,
            display_name=asset.entry.player.full_name,
            raw_value=asset.entry.value.current or 0,
            reset_adjusted_value=asset_value_under_reset(
                asset.entry, receiver_post_entries, probability
            ),
            protectable_on_receiver=asset.entry.player.player_id in receiver_post_slate_ids,
        )
    return TradeAsset(
        kind="pick",
        asset_id=asset.asset_id,
        display_name=asset.display_name,
        raw_value=asset.base_value,
        reset_adjusted_value=pick_value_under_reset(
            asset.season, asset.round_, probability, current_season, asset.base_value
        ),
        protectable_on_receiver=False,
    )


def _protection_change_flags(
    base_slots: dict[str, str],
    post_slots: dict[str, str],
) -> list[str]:
    flags = []
    for slot in ("qb", "rb_te", "wr_te"):
        if base_slots.get(slot) != post_slots.get(slot):
            flags.append(f"fills_my_{slot}_protection")
    return flags


def _asset_raw_value(asset: _Asset) -> int:
    if isinstance(asset, _PlayerAsset):
        return asset.entry.value.current or 0
    return asset.base_value


def _asset_outgoing_value(
    asset: _Asset,
    sender_entries: list[RosterEntry],
    probability: float,
    current_season: str,
) -> int:
    if isinstance(asset, _PlayerAsset):
        return asset_value_under_reset(asset.entry, sender_entries, probability)
    return pick_value_under_reset(
        asset.season, asset.round_, probability, current_season, asset.base_value
    )


def _asset_incoming_value(
    asset: _Asset,
    receiver_post_entries: list[RosterEntry],
    probability: float,
    current_season: str,
) -> int:
    if isinstance(asset, _PlayerAsset):
        return asset_value_under_reset(asset.entry, receiver_post_entries, probability)
    return pick_value_under_reset(
        asset.season, asset.round_, probability, current_season, asset.base_value
    )


async def reset_trades(
    ctx: Context,
    *,
    partner: TeamSpec | None = None,
    reset_probability: float = 0.0,
    max_send: int = 2,
    max_recv: int = 2,
    min_edge: int = 500,
    top_n: int = 10,
) -> ResetTradeFinderResult:
    if not ctx.league_id:
        raise ValueError("league_id required")

    league = await ctx.sleeper.get_league(ctx.league_id)
    rosters_raw = await ctx.sleeper.get_rosters(ctx.league_id)
    users_raw = await ctx.sleeper.get_league_users(ctx.league_id)
    players_data = await ctx.sleeper.get_players()
    fc = await ctx.fantasycalc.get_current(league)

    values = _value_map(fc)
    pick_value_map = _build_pick_value_map(fc)

    notes: list[str] = []

    by_user_id = {u["user_id"]: u for u in users_raw}
    me_user = next(
        (u for u in users_raw
         if (u.get("username") or u.get("display_name") or "").lower() == ctx.username.lower()),
        None,
    )
    if me_user is None:
        raise ValueError(f"username {ctx.username!r} not in league")
    me_roster_raw = next(
        (r for r in rosters_raw if r.get("owner_id") == me_user["user_id"]),
        None,
    )
    if me_roster_raw is None:
        raise ValueError(f"no roster for {ctx.username!r}")
    my_roster_id = int(me_roster_raw["roster_id"])

    def build_valued_entries(roster_raw: dict[str, Any]) -> list[RosterEntry]:
        from dynasty_mcp.models import Value
        entries = []
        for pid in (roster_raw.get("players") or []):
            data = players_data.get(pid, {})
            slot = _classify(pid, roster_raw)
            val = values.get(pid)
            entries.append(RosterEntry(
                player=_player_from_sleeper(pid, data),
                slot_type=slot,
                value=Value(current=val),
                starter=pid in (roster_raw.get("starters") or []),
            ))
        return [e for e in entries if e.value.current is not None]

    traded_picks_raw = await ctx.sleeper.get_traded_picks(ctx.league_id)
    all_roster_ids = [int(r["roster_id"]) for r in rosters_raw]
    current_year = ctx.season
    next_year = str(int(current_year) + 1)
    all_picks = _build_pick_pool(
        roster_ids=all_roster_ids,
        traded_picks=traded_picks_raw,
        seasons=[current_year, next_year],
        rounds=[1, 2, 3, 4],
        pick_value_map=pick_value_map,
    )
    unmatched_picks = sum(1 for p in all_picks if p.base_value == 0)
    if unmatched_picks:
        notes.append(
            f"{unmatched_picks} picks have no FantasyCalc value match; treated as 0."
        )

    if partner is not None:
        partner_roster_raw, _ = await _resolve_roster(ctx, ctx.league_id, partner)
        counterparty_roster_ids = [int(partner_roster_raw["roster_id"])]
    else:
        counterparty_roster_ids = [
            int(r["roster_id"]) for r in rosters_raw
            if int(r["roster_id"]) != my_roster_id
        ]

    my_entries = build_valued_entries(me_roster_raw)
    my_picks = [p for p in all_picks if p.owner_id == my_roster_id]
    my_base_slate_list = rank_slates(my_entries, n=1)
    my_base_slate = my_base_slate_list[0] if my_base_slate_list else None
    my_base_slot_map = _slate_slot_map(my_base_slate)

    my_players_sorted = sorted(my_entries, key=lambda e: e.value.current or 0, reverse=True)[:15]
    my_combined: list[_Asset] = (
        [_PlayerAsset(entry=e, owner_id=my_roster_id) for e in my_players_sorted]
        + my_picks
    )
    my_combined.sort(key=_asset_raw_value, reverse=True)
    my_pool = my_combined[:15]

    all_proposals: list[TradeProposal] = []

    for their_roster_id in counterparty_roster_ids:
        their_roster_raw = next(
            r for r in rosters_raw if int(r["roster_id"]) == their_roster_id
        )
        their_user = by_user_id.get(their_roster_raw.get("owner_id"), {})
        their_username = their_user.get("username") or their_user.get("display_name") or ""
        their_entries = build_valued_entries(their_roster_raw)
        their_picks = [p for p in all_picks if p.owner_id == their_roster_id]
        their_players_sorted = sorted(
            their_entries, key=lambda e: e.value.current or 0, reverse=True
        )[:15]
        their_combined: list[_Asset] = (
            [_PlayerAsset(entry=e, owner_id=their_roster_id) for e in their_players_sorted]
            + their_picks
        )
        their_combined.sort(key=_asset_raw_value, reverse=True)
        their_pool = their_combined[:15]

        for send_size in range(1, max_send + 1):
            for recv_size in range(1, max_recv + 1):
                for send_combo in combinations(my_pool, send_size):
                    for recv_combo in combinations(their_pool, recv_size):
                        send_pids = {
                            a.entry.player.player_id
                            for a in send_combo if isinstance(a, _PlayerAsset)
                        }
                        recv_pids = {
                            a.entry.player.player_id
                            for a in recv_combo if isinstance(a, _PlayerAsset)
                        }
                        my_post_entries = (
                            [e for e in my_entries if e.player.player_id not in send_pids]
                            + [a.entry for a in recv_combo if isinstance(a, _PlayerAsset)]
                        )
                        their_post_entries = (
                            [e for e in their_entries if e.player.player_id not in recv_pids]
                            + [a.entry for a in send_combo if isinstance(a, _PlayerAsset)]
                        )

                        my_outgoing = sum(
                            _asset_outgoing_value(a, my_entries, reset_probability, current_year)
                            for a in send_combo
                        )
                        my_incoming = sum(
                            _asset_incoming_value(a, my_post_entries, reset_probability, current_year)
                            for a in recv_combo
                        )
                        their_outgoing = sum(
                            _asset_outgoing_value(a, their_entries, reset_probability, current_year)
                            for a in recv_combo
                        )
                        their_incoming = sum(
                            _asset_incoming_value(a, their_post_entries, reset_probability, current_year)
                            for a in send_combo
                        )
                        my_net_edge = my_incoming - my_outgoing
                        their_net_edge = their_incoming - their_outgoing

                        if my_net_edge < min_edge or their_net_edge < min_edge:
                            continue

                        my_post_slate_list = rank_slates(my_post_entries, n=1)
                        my_post_slate = my_post_slate_list[0] if my_post_slate_list else None
                        my_post_slate_ids = _slate_all_ids(my_post_slate)
                        my_post_slot_map = _slate_slot_map(my_post_slate)

                        their_post_slate_list = rank_slates(their_post_entries, n=1)
                        their_post_slate = their_post_slate_list[0] if their_post_slate_list else None
                        their_post_slate_ids = _slate_all_ids(their_post_slate)

                        my_send_assets = [
                            _to_trade_asset(
                                a,
                                receiver_post_entries=their_post_entries,
                                receiver_post_slate_ids=their_post_slate_ids,
                                probability=reset_probability,
                                current_season=current_year,
                            )
                            for a in send_combo
                        ]
                        my_recv_assets = [
                            _to_trade_asset(
                                a,
                                receiver_post_entries=my_post_entries,
                                receiver_post_slate_ids=my_post_slate_ids,
                                probability=reset_probability,
                                current_season=current_year,
                            )
                            for a in recv_combo
                        ]

                        flags: list[str] = []
                        flags.extend(_protection_change_flags(my_base_slot_map, my_post_slot_map))

                        send_players = [a for a in send_combo if isinstance(a, _PlayerAsset)]
                        if send_players and all(
                            asset_value_under_reset(a.entry, my_entries, 1.0) == 0
                            for a in send_players
                        ):
                            flags.append("i_surrender_unprotectable_depth")

                        all_assets = list(send_combo) + list(recv_combo)
                        future_picks = [
                            a for a in all_assets
                            if isinstance(a, _PickAsset) and a.season > current_year
                        ]
                        if future_picks and reset_probability > 0:
                            pct = int(reset_probability * 100)
                            flags.append(f"future_pick_discounted_{pct}%")

                        if any(
                            isinstance(a, _PlayerAsset)
                            and a.entry.slot_type == SlotType.TAXI
                            for a in recv_combo
                        ):
                            flags.append("partner_rebuilds_taxi")

                        all_proposals.append(TradeProposal(
                            rank=0,
                            partner_roster_id=their_roster_id,
                            partner_username=their_username,
                            my_send=my_send_assets,
                            my_recv=my_recv_assets,
                            my_net_edge=my_net_edge,
                            partner_net_edge=their_net_edge,
                            rationale_flags=flags,
                        ))

    all_proposals.sort(key=lambda p: p.my_net_edge, reverse=True)
    top_proposals = all_proposals[:top_n]
    for i, p in enumerate(top_proposals, start=1):
        p.rank = i

    return ResetTradeFinderResult(
        reset_probability=reset_probability,
        proposals=top_proposals,
        considered_partners=counterparty_roster_ids,
        notes=notes,
    )
