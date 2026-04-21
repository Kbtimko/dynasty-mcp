from __future__ import annotations

from itertools import combinations
from typing import Iterator

from dynasty_mcp.models import ProtectionSlate, RosterEntry, SlotType


def enumerate_slates(entries: list[RosterEntry]) -> Iterator[ProtectionSlate]:
    """Yield every legal protection slate for the given roster entries.

    QB slot: any entry with position == "QB".
    RB/TE slot: any entry with position in {"RB", "TE"}, not already chosen.
    WR/TE slot: any entry with position in {"WR", "TE"}, not already chosen.
    TAXI slots: 0–3 entries with slot_type == SlotType.TAXI, not already chosen.
    No player may appear in more than one slot.
    """
    qbs = [e for e in entries if e.player.position == "QB"]
    if not qbs:
        return

    rb_te_pool = [e for e in entries if e.player.position in {"RB", "TE"}]
    wr_te_pool = [e for e in entries if e.player.position in {"WR", "TE"}]
    taxi_pool = [e for e in entries if e.slot_type == SlotType.TAXI]

    for qb in qbs:
        for rb_te in rb_te_pool:
            if rb_te.player.player_id == qb.player.player_id:
                continue
            for wr_te in wr_te_pool:
                pid = wr_te.player.player_id
                if pid in {qb.player.player_id, rb_te.player.player_id}:
                    continue
                chosen = {qb.player.player_id, rb_te.player.player_id, pid}
                remaining_taxi = [
                    t for t in taxi_pool if t.player.player_id not in chosen
                ]
                max_taxi = min(3, len(remaining_taxi))
                for taxi_count in range(max_taxi + 1):
                    for taxi_combo in combinations(remaining_taxi, taxi_count):
                        protected_value = (
                            (qb.value.current or 0)
                            + (rb_te.value.current or 0)
                            + (wr_te.value.current or 0)
                            + sum(t.value.current or 0 for t in taxi_combo)
                        )
                        yield ProtectionSlate(
                            qb=qb,
                            rb_te=rb_te,
                            wr_te=wr_te,
                            taxi=list(taxi_combo),
                            protected_value=protected_value,
                        )


def _slate_sort_key(slate: ProtectionSlate) -> tuple:
    pids = sorted(
        [
            slate.qb.player.player_id,
            slate.rb_te.player.player_id,
            slate.wr_te.player.player_id,
            *[t.player.player_id for t in slate.taxi],
        ]
    )
    return (-slate.protected_value, tuple(pids))


def rank_slates(entries: list[RosterEntry], *, n: int = 5) -> list[ProtectionSlate]:
    """Return the top-n slates by protected_value descending.

    Deterministic tiebreak: sorted player_id tuple ascending.
    Returns [] when n == 0 or no valid slates exist.
    """
    if n <= 0:
        return []
    all_slates = list(enumerate_slates(entries))
    all_slates.sort(key=_slate_sort_key)
    return all_slates[:n]


def value_at_risk(entries: list[RosterEntry], slate: ProtectionSlate) -> int:
    """Sum of value.current (None → 0) for every entry NOT in the protection slate."""
    protected_ids = {
        slate.qb.player.player_id,
        slate.rb_te.player.player_id,
        slate.wr_te.player.player_id,
        *[t.player.player_id for t in slate.taxi],
    }
    return sum(
        e.value.current or 0
        for e in entries
        if e.player.player_id not in protected_ids
    )


def pick_value_under_reset(
    season: str,
    round_: int,
    probability: float,
    current_season: str,
    base_value: int,
) -> int:
    """Return reset-adjusted value for a draft pick.

    Current-year picks (season == current_season) are never voided; returns base_value.
    Future-year picks are discounted by probability: int(base_value * (1 - probability)).
    """
    if season == current_season:
        return base_value
    return int(base_value * (1 - probability))


def asset_value_under_reset(
    entry: RosterEntry,
    owner_entries: list[RosterEntry],
    probability: float,
) -> int:
    """Compute reset-aware value for a player asset on a given roster.

    protected_contribution = max(0, best_slate_with_player - best_slate_without_player).
    reset_value = int(probability * protected_contribution + (1 - probability) * raw).
    """
    without = [e for e in owner_entries if e.player.player_id != entry.player.player_id]

    best_with_slates = rank_slates(owner_entries, n=1)
    best_without_slates = rank_slates(without, n=1)

    best_with = best_with_slates[0].protected_value if best_with_slates else 0
    best_without = best_without_slates[0].protected_value if best_without_slates else 0

    protected_contribution = max(0, best_with - best_without)
    raw = entry.value.current or 0
    return int(probability * protected_contribution + (1 - probability) * raw)
