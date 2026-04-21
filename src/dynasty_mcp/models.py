from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SlotType(str, Enum):
    ACTIVE = "active"
    BENCH = "bench"
    TAXI = "taxi"
    IR = "ir"


class Player(BaseModel):
    player_id: str
    full_name: str
    position: str
    team: str | None = None
    age: int | None = None
    status: str | None = None  # "Active", "IR", "Questionable", etc.


class Value(BaseModel):
    current: int | None
    delta_7d: int | None = None
    delta_30d: int | None = None


class RosterEntry(BaseModel):
    player: Player
    slot_type: SlotType
    value: Value
    starter: bool = False
    projection: float | None = None  # weekly points projection, set by get_matchup


class RosterView(BaseModel):
    roster_id: int
    owner_username: str
    owner_display_name: str | None = None
    entries: list[RosterEntry]
    total_value_active: int
    total_value_taxi: int
    total_value_ir: int


class LeagueContext(BaseModel):
    league_id: str
    season: str
    current_week: int
    season_phase: Literal["pre", "regular", "post", "offseason"]
    num_teams: int
    num_qbs: int  # 1 or 2 (superflex)
    ppr: float
    roster_slots: dict[str, int]
    taxi_slots: int
    bench_slots: int
    ir_slots: int
    your_roster_id: int


class StaleFlag(BaseModel):
    stale: bool = False
    as_of: str | None = None  # ISO-8601 UTC


class RosterSummary(BaseModel):
    roster_id: int
    owner_username: str
    total_value: int
    top_assets: list[str]  # player names


class TeamValueBreakdown(BaseModel):
    roster_id: int
    by_position: dict[str, int]
    by_age_cohort: dict[str, int]  # keys: under_25, 25_28, 29_plus, unknown
    taxi_stash_value: int
    ir_value: int
    active_value: int


class TrendingRow(BaseModel):
    player: Player
    count: int


class ProtectionSlot(str, Enum):
    QB = "qb"
    RB_TE = "rb_te"
    WR_TE = "wr_te"
    TAXI = "taxi"


class ProtectionSlate(BaseModel):
    qb: RosterEntry
    rb_te: RosterEntry
    wr_te: RosterEntry
    taxi: list[RosterEntry]  # len ≤ 3
    protected_value: int


class Swap(BaseModel):
    slot: ProtectionSlot
    from_player: str   # player_id in rank-1 slate
    to_player: str     # player_id in this slate
    value_delta: int   # (to.value - from.value); negative for rank ≥ 2


class SlateOption(BaseModel):
    rank: int
    protected: ProtectionSlate
    protected_value: int
    value_at_risk: int
    swaps_from_top: list[Swap]  # empty for rank 1


class ResetOptimizerResult(BaseModel):
    roster_id: int
    owner_username: str
    reset_probability: float
    total_roster_value: int
    options: list[SlateOption]
    taxi_pool_size: int
    notes: list[str]
