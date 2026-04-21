from __future__ import annotations

from dynasty_mcp.context import Context
from dynasty_mcp.models import (
    ProtectionSlot,
    ResetOptimizerResult,
    SlateOption,
    SlotType,
    Swap,
)
from dynasty_mcp.reset_scoring import rank_slates, value_at_risk
from dynasty_mcp.tools.rosters import TeamSpec, get_roster


async def reset_optimizer(
    ctx: Context,
    *,
    team: TeamSpec = "me",
    reset_probability: float = 1.0,
    top_n: int = 5,
) -> ResetOptimizerResult:
    view = await get_roster(ctx, team=team)

    notes: list[str] = []
    valued_entries = []
    for entry in view.entries:
        if entry.value.current is None:
            notes.append(
                f"{entry.player.full_name} has no FantasyCalc value, skipped"
            )
        else:
            valued_entries.append(entry)

    # reset_probability does not affect slate ranking — optimizer always picks the slate
    # that maximizes protected value assuming a reset occurs. Probability weighting is the
    # trade finder's job (see reset_trades tool). The parameter is stored on the result for
    # context and future composability.
    slates = rank_slates(valued_entries, n=top_n)

    total_value = sum(e.value.current or 0 for e in view.entries)
    taxi_pool_size = sum(
        1
        for e in valued_entries
        if e.slot_type == SlotType.TAXI
    )

    if not slates:
        notes.append("No valid protection slates found (roster has no QB?).")
        return ResetOptimizerResult(
            roster_id=view.roster_id,
            owner_username=view.owner_username,
            reset_probability=reset_probability,
            total_roster_value=total_value,
            options=[],
            taxi_pool_size=taxi_pool_size,
            notes=notes,
        )

    rank1 = slates[0]

    if len(rank1.taxi) < 3:
        unused = 3 - len(rank1.taxi)
        notes.append(
            f"{unused} TAXI protection slot(s) unused — fewer than 3 valued TAXI players."
        )

    options: list[SlateOption] = []
    for rank_idx, slate in enumerate(slates, start=1):
        swaps: list[Swap] = []
        if rank_idx > 1:
            for slot, r1_entry, r_entry in [
                (ProtectionSlot.QB, rank1.qb, slate.qb),
                (ProtectionSlot.RB_TE, rank1.rb_te, slate.rb_te),
                (ProtectionSlot.WR_TE, rank1.wr_te, slate.wr_te),
            ]:
                if r1_entry.player.player_id != r_entry.player.player_id:
                    swaps.append(
                        Swap(
                            slot=slot,
                            from_player=r1_entry.player.player_id,
                            to_player=r_entry.player.player_id,
                            value_delta=(r_entry.value.current or 0)
                            - (r1_entry.value.current or 0),
                        )
                    )
            # TAXI slot diffs
            r1_taxi_ids = {t.player.player_id for t in rank1.taxi}
            slate_taxi_ids = {t.player.player_id for t in slate.taxi}
            if r1_taxi_ids != slate_taxi_ids:
                # Build lookup maps for value_delta computation
                rank1_taxi_map = {t.player.player_id: t for t in rank1.taxi}
                slate_taxi_map = {t.player.player_id: t for t in slate.taxi}
                removed = sorted(r1_taxi_ids - slate_taxi_ids)
                added = sorted(slate_taxi_ids - r1_taxi_ids)
                for removed_id, added_id in zip(removed, added):
                    swaps.append(
                        Swap(
                            slot=ProtectionSlot.TAXI,
                            from_player=removed_id,
                            to_player=added_id,
                            value_delta=(slate_taxi_map[added_id].value.current or 0)
                            - (rank1_taxi_map[removed_id].value.current or 0),
                        )
                    )
        options.append(
            SlateOption(
                rank=rank_idx,
                protected=slate,
                protected_value=slate.protected_value,
                value_at_risk=value_at_risk(view.entries, slate),
                swaps_from_top=swaps,
            )
        )

    return ResetOptimizerResult(
        roster_id=view.roster_id,
        owner_username=view.owner_username,
        reset_probability=reset_probability,
        total_roster_value=total_value,
        options=options,
        taxi_pool_size=taxi_pool_size,
        notes=notes,
    )
