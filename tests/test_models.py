from dynasty_mcp.models import (
    LeagueContext,
    Player,
    RosterEntry,
    RosterView,
    SlotType,
    Value,
)


def test_player_minimal() -> None:
    p = Player(player_id="4046", full_name="Patrick Mahomes", position="QB", team="KC")
    assert p.age is None
    assert p.status is None


def test_roster_entry_carries_slot_and_value() -> None:
    entry = RosterEntry(
        player=Player(player_id="1", full_name="X", position="WR", team="SF"),
        slot_type=SlotType.TAXI,
        value=Value(current=1200, delta_7d=100),
    )
    assert entry.slot_type == SlotType.TAXI
    assert entry.value.delta_7d == 100


def test_roster_view_totals() -> None:
    view = RosterView(
        roster_id=1,
        owner_username="alice",
        entries=[],
        total_value_active=0,
        total_value_taxi=0,
        total_value_ir=0,
    )
    assert view.roster_id == 1


def test_league_context_has_taxi_slots() -> None:
    ctx = LeagueContext(
        league_id="L",
        season="2026",
        current_week=7,
        season_phase="regular",
        num_teams=12,
        num_qbs=2,
        ppr=1.0,
        roster_slots={"QB": 1, "RB": 2, "WR": 3, "TE": 1, "FLEX": 2},
        taxi_slots=4,
        bench_slots=7,
        ir_slots=2,
        your_roster_id=3,
    )
    assert ctx.taxi_slots == 4
    assert ctx.num_qbs == 2
