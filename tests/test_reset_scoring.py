from __future__ import annotations

from dynasty_mcp.models import (
    Player,
    ProtectionSlate,
    RosterEntry,
    SlotType,
    Value,
)
from dynasty_mcp.reset_scoring import enumerate_slates, rank_slates


def make_entry(
    player_id: str,
    position: str,
    value: int | None,
    slot: SlotType = SlotType.BENCH,
) -> RosterEntry:
    return RosterEntry(
        player=Player(
            player_id=player_id,
            full_name=f"Player {player_id}",
            position=position,
        ),
        slot_type=slot,
        value=Value(current=value),
    )


# --- enumerate_slates ---


def test_enumerate_slates_single_valid_combo():
    """1 QB + 1 RB + 1 WR, no TAXI → exactly one slate."""
    entries = [
        make_entry("qb1", "QB", 1000),
        make_entry("rb1", "RB", 800),
        make_entry("wr1", "WR", 700),
    ]
    slates = list(enumerate_slates(entries))
    assert len(slates) == 1
    s = slates[0]
    assert s.qb.player.player_id == "qb1"
    assert s.rb_te.player.player_id == "rb1"
    assert s.wr_te.player.player_id == "wr1"
    assert s.taxi == []
    assert s.protected_value == 2500


def test_enumerate_slates_no_qb_yields_empty():
    """No QB → no valid slate."""
    entries = [
        make_entry("rb1", "RB", 800),
        make_entry("wr1", "WR", 700),
    ]
    assert list(enumerate_slates(entries)) == []


def test_enumerate_slates_te_fills_rb_te_slot():
    """A TE is eligible for the RB/TE slot when no RB is present."""
    entries = [
        make_entry("qb1", "QB", 1000),
        make_entry("te1", "TE", 900),
        make_entry("wr1", "WR", 700),
    ]
    slates = list(enumerate_slates(entries))
    # te1 can fill RB/TE (wr1 fills WR/TE) — valid
    # te1 in WR/TE but no RB for RB/TE — invalid
    assert len(slates) == 1
    assert slates[0].rb_te.player.player_id == "te1"
    assert slates[0].wr_te.player.player_id == "wr1"


def test_enumerate_slates_two_tes_generate_two_orderings():
    """Two TEs: each can be in RB/TE or WR/TE → two distinct slates."""
    entries = [
        make_entry("qb1", "QB", 1000),
        make_entry("te1", "TE", 900),
        make_entry("te2", "TE", 800),
    ]
    slates = list(enumerate_slates(entries))
    assert len(slates) == 2
    player_pairs = {
        (s.rb_te.player.player_id, s.wr_te.player.player_id)
        for s in slates
    }
    assert ("te1", "te2") in player_pairs
    assert ("te2", "te1") in player_pairs


def test_enumerate_slates_taxi_included():
    """TAXI players appear in taxi combos; valued taxi slots included in protected_value."""
    entries = [
        make_entry("qb1", "QB", 3000),
        make_entry("rb1", "RB", 2000),
        make_entry("wr1", "WR", 1500),
        make_entry("t1", "QB", 300, SlotType.TAXI),
        make_entry("t2", "QB", 200, SlotType.TAXI),
        make_entry("t3", "QB", 100, SlotType.TAXI),
    ]
    slates = list(enumerate_slates(entries))
    assert any(len(s.taxi) > 0 for s in slates)
    max_slate = max(slates, key=lambda s: s.protected_value)
    # qb1(3000) + rb1(2000) + wr1(1500) + t1(300) + t2(200) + t3(100) = 7100
    assert max_slate.protected_value == 7100


def test_enumerate_slates_no_player_double_counted():
    """No player appears in more than one slot per slate."""
    entries = [
        make_entry("qb1", "QB", 1000),
        make_entry("te1", "TE", 900, SlotType.TAXI),  # TAXI TE: eligible for rb_te and taxi
        make_entry("wr1", "WR", 700),
    ]
    slates = list(enumerate_slates(entries))
    # te1 eligible for rb_te AND taxi_pool — but cannot be in both.
    # Only valid: qb=qb1, rb_te=te1, wr_te=wr1, taxi=[] (te1 chosen as starter, not taxi)
    assert len(slates) == 1
    assert slates[0].rb_te.player.player_id == "te1"
    assert slates[0].taxi == []
    for s in slates:
        ids_used = (
            [s.qb.player.player_id, s.rb_te.player.player_id, s.wr_te.player.player_id]
            + [t.player.player_id for t in s.taxi]
        )
        assert len(ids_used) == len(set(ids_used)), f"double-count in slate: {ids_used}"


def test_enumerate_slates_protected_value_none_treated_as_zero():
    """Entry with value=None contributes 0 to protected_value."""
    entries = [
        make_entry("qb1", "QB", None),
        make_entry("rb1", "RB", 800),
        make_entry("wr1", "WR", 700),
    ]
    slates = list(enumerate_slates(entries))
    assert slates[0].protected_value == 1500  # 0 + 800 + 700


# --- rank_slates ---


def test_rank_slates_returns_top_n_descending():
    """rank_slates returns at most n slates, sorted by protected_value descending."""
    entries = [
        make_entry("qb1", "QB", 1000),
        make_entry("qb2", "QB", 500),
        make_entry("rb1", "RB", 800),
        make_entry("wr1", "WR", 700),
    ]
    slates = rank_slates(entries, n=3)
    assert len(slates) <= 3
    assert slates[0].qb.player.player_id == "qb1"
    for a, b in zip(slates, slates[1:]):
        assert a.protected_value >= b.protected_value


def test_rank_slates_empty_entries_returns_empty():
    assert rank_slates([], n=5) == []


def test_rank_slates_no_qb_returns_empty():
    entries = [make_entry("rb1", "RB", 800), make_entry("wr1", "WR", 700)]
    assert rank_slates(entries, n=5) == []


def test_rank_slates_n_larger_than_available_returns_all():
    entries = [
        make_entry("qb1", "QB", 1000),
        make_entry("rb1", "RB", 800),
        make_entry("wr1", "WR", 700),
    ]
    slates = rank_slates(entries, n=10)
    assert len(slates) == 1


def test_rank_slates_deterministic_tiebreak():
    """Equal protected_value → ordered by sorted player_id tuple ascending."""
    # Two QBs with same value → two slates with equal protected_value
    # qb1 and qb2 both have value 1000; both produce slate with protected_value = 2500
    # tiebreak: sorted([qb_id, "rb1", "wr1"]); "qb1" < "qb2" lexicographically
    entries = [
        make_entry("qb1", "QB", 1000),
        make_entry("qb2", "QB", 1000),
        make_entry("rb1", "RB", 800),
        make_entry("wr1", "WR", 700),
    ]
    slates = rank_slates(entries, n=5)
    assert len(slates) == 2
    assert slates[0].protected_value == slates[1].protected_value == 2500
    # tiebreak: sorted(["qb1","rb1","wr1"]) < sorted(["qb2","rb1","wr1"])
    assert slates[0].qb.player.player_id == "qb1"
    assert slates[1].qb.player.player_id == "qb2"


# --- value_at_risk ---

from dynasty_mcp.reset_scoring import value_at_risk


def test_value_at_risk_unprotected_player_sum():
    """One unprotected player contributes their value to risk."""
    entries = [
        make_entry("qb1", "QB", 3000),
        make_entry("rb1", "RB", 2000),
        make_entry("wr1", "WR", 1500),
        make_entry("rb2", "RB", 500),  # not in rank-1 slate
    ]
    slate = rank_slates(entries, n=1)[0]
    assert value_at_risk(entries, slate) == 500


def test_value_at_risk_none_value_contributes_zero():
    """Entry with value=None in risk pool contributes 0."""
    entries = [
        make_entry("qb1", "QB", 3000),
        make_entry("rb1", "RB", 2000),
        make_entry("wr1", "WR", 1500),
        make_entry("rb2", "RB", None),  # unprotected, None value
    ]
    slate = rank_slates(entries, n=1)[0]
    assert value_at_risk(entries, slate) == 0


def test_value_at_risk_all_protected_is_zero():
    """Roster exactly fits one slate → nothing at risk."""
    entries = [
        make_entry("qb1", "QB", 1000),
        make_entry("rb1", "RB", 800),
        make_entry("wr1", "WR", 700),
    ]
    slate = rank_slates(entries, n=1)[0]
    assert value_at_risk(entries, slate) == 0


def test_value_at_risk_includes_taxi_not_in_slate():
    """TAXI players not chosen for protection count toward risk."""
    entries = [
        make_entry("qb1", "QB", 3000),
        make_entry("rb1", "RB", 2000),
        make_entry("wr1", "WR", 1500),
        make_entry("t1", "WR", 400, SlotType.TAXI),
        make_entry("t2", "WR", 300, SlotType.TAXI),
        make_entry("t3", "WR", 200, SlotType.TAXI),
        make_entry("t4", "WR", 100, SlotType.TAXI),  # 4th taxi — can't all be protected
    ]
    # rank-1 slate fills 3 taxi slots: t1+t2+t3=900; t4 is at risk
    slate = rank_slates(entries, n=1)[0]
    assert value_at_risk(entries, slate) == 100
