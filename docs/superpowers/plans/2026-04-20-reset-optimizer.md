# Reset Team Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `reset_optimizer` MCP tool that picks the optimal protection slate (1 QB + 1 RB/TE + 1 WR/TE + 3 TAXI) for any team and surfaces the top-5 alternatives with per-slot swap deltas.

**Architecture:** A pure-function scoring module (`reset_scoring.py`) holds all combinatorial logic with no I/O; the tool wrapper (`tools/reset_optimizer.py`) calls `get_roster` to build the entry list, delegates enumeration + ranking to the scoring module, and assembles the result model. This mirrors the existing `sources/` (pure) vs `tools/` (wiring) split.

**Tech Stack:** Python 3.12, Pydantic v2, FastMCP, respx (tests), pytest-asyncio

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `src/dynasty_mcp/models.py` | Add `ProtectionSlot`, `ProtectionSlate`, `Swap`, `SlateOption`, `ResetOptimizerResult` |
| Create | `src/dynasty_mcp/reset_scoring.py` | Pure functions: `enumerate_slates`, `rank_slates`, `value_at_risk`, `pick_value_under_reset`, `asset_value_under_reset` |
| Create | `src/dynasty_mcp/tools/reset_optimizer.py` | MCP tool wrapper |
| Create | `tests/test_reset_scoring.py` | Unit tests for all pure functions |
| Create | `tests/test_tools/test_reset_optimizer.py` | Integration tests for the optimizer tool |
| Modify | `src/dynasty_mcp/server.py` | Register `reset_optimizer` |
| Modify | `tests/test_server.py` | Add `reset_optimizer` to expected tools |
| Modify | `tests/test_contract.py` | Add live smoke test |

---

## Task 1: Add reset models to `models.py`

**Files:**
- Modify: `src/dynasty_mcp/models.py`

No test needed for pure data shapes; the tests in later tasks exercise them.

- [ ] **Step 1: Add models**

Open `src/dynasty_mcp/models.py`. After the existing imports and before `class SlotType`, add the following (add `Literal` to the existing `from typing import Literal` import if not already present):

```python
from enum import Enum
```

(Already present — `SlotType` uses it. Just confirm.)

Append at the bottom of `src/dynasty_mcp/models.py`:

```python
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
```

- [ ] **Step 2: Verify imports are clean**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -5
```

Expected: same pass count as before (no new failures).

- [ ] **Step 3: Commit**

```bash
git add src/dynasty_mcp/models.py
git commit -m "feat: add reset-optimizer result models"
```

---

## Task 2: TDD `enumerate_slates` + `rank_slates`

**Files:**
- Create: `tests/test_reset_scoring.py`
- Create: `src/dynasty_mcp/reset_scoring.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_reset_scoring.py`:

```python
from __future__ import annotations

import pytest

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
    # te1 can fill RB/TE (wr1 fills WR/TE) — but te1 can also fill WR/TE (no RB for RB/TE)
    # valid: (qb1, rb_te=te1, wr_te=wr1)
    # also: (qb1, rb_te=te1, wr_te=te1) — double-count, illegal
    # also: (qb1, rb_te=??, wr_te=te1) — no RB for rb_te slot
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
        make_entry("t1", "QB", 300, SlotType.TAXI),   # QB/TAXI
        make_entry("t2", "QB", 200, SlotType.TAXI),   # QB/TAXI
        make_entry("t3", "QB", 100, SlotType.TAXI),   # QB/TAXI
    ]
    slates = list(enumerate_slates(entries))
    # All slates should be present; check that some slates include taxi entries
    assert any(len(s.taxi) > 0 for s in slates)
    # The slate with qb=qb1 and all 3 TAXI slots filled should have protected_value = 3000+2000+1500+300+200+100
    max_slate = max(slates, key=lambda s: s.protected_value)
    assert max_slate.protected_value == 7100


def test_enumerate_slates_no_player_double_counted():
    """No player appears in more than one slot per slate."""
    entries = [
        make_entry("qb1", "QB", 1000),
        make_entry("te1", "TE", 900, SlotType.TAXI),   # TAXI TE: eligible for rb_te, wr_te, AND taxi
        make_entry("wr1", "WR", 700),
    ]
    slates = list(enumerate_slates(entries))
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
    assert slates[0].qb.player.player_id == "qb1"  # higher QB in top slot
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
    # Only 1 valid slate (no TAXI), n=10 should return just that 1
    slates = rank_slates(entries, n=10)
    assert len(slates) == 1


def test_rank_slates_deterministic_tiebreak():
    """Equal protected_value → order is deterministic across calls."""
    entries = [
        make_entry("qb1", "QB", 1000),
        make_entry("rb1", "RB", 800),
        make_entry("wr1", "WR", 700),
    ]
    run1 = rank_slates(entries, n=5)
    run2 = rank_slates(entries, n=5)
    assert [s.protected_value for s in run1] == [s.protected_value for s in run2]
    assert [s.qb.player.player_id for s in run1] == [s.qb.player.player_id for s in run2]
```

- [ ] **Step 2: Run — verify FAIL**

```bash
python -m pytest tests/test_reset_scoring.py -v 2>&1 | head -30
```

Expected: all tests fail with `ModuleNotFoundError: No module named 'dynasty_mcp.reset_scoring'`.

- [ ] **Step 3: Create `src/dynasty_mcp/reset_scoring.py` with `enumerate_slates` + `rank_slates`**

```python
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
```

- [ ] **Step 4: Run — verify PASS**

```bash
python -m pytest tests/test_reset_scoring.py -v 2>&1 | tail -20
```

Expected: all tests in `test_reset_scoring.py` pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_reset_scoring.py src/dynasty_mcp/reset_scoring.py
git commit -m "feat: add enumerate_slates and rank_slates to reset_scoring"
```

---

## Task 3: TDD `value_at_risk`

**Files:**
- Modify: `tests/test_reset_scoring.py` (append)
- Modify: `src/dynasty_mcp/reset_scoring.py` (append)

- [ ] **Step 1: Append failing tests to `tests/test_reset_scoring.py`**

Add at the bottom of `tests/test_reset_scoring.py`:

```python
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
```

- [ ] **Step 2: Run — verify FAIL**

```bash
python -m pytest tests/test_reset_scoring.py::test_value_at_risk_unprotected_player_sum -v 2>&1 | tail -10
```

Expected: `ImportError` or `AttributeError` — `value_at_risk` not defined yet.

- [ ] **Step 3: Append `value_at_risk` to `src/dynasty_mcp/reset_scoring.py`**

```python
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
```

- [ ] **Step 4: Run — verify PASS**

```bash
python -m pytest tests/test_reset_scoring.py -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_reset_scoring.py src/dynasty_mcp/reset_scoring.py
git commit -m "feat: add value_at_risk to reset_scoring"
```

---

## Task 4: TDD `pick_value_under_reset` + `asset_value_under_reset`

**Files:**
- Modify: `tests/test_reset_scoring.py` (append)
- Modify: `src/dynasty_mcp/reset_scoring.py` (append)

- [ ] **Step 1: Append failing tests to `tests/test_reset_scoring.py`**

```python
# --- pick_value_under_reset ---

from dynasty_mcp.reset_scoring import pick_value_under_reset


def test_pick_value_current_year_unaffected_by_probability():
    """Current-year picks keep full base_value regardless of reset probability."""
    assert pick_value_under_reset("2025", 1, probability=1.0, current_season="2025", base_value=3000) == 3000
    assert pick_value_under_reset("2025", 1, probability=0.5, current_season="2025", base_value=3000) == 3000
    assert pick_value_under_reset("2025", 1, probability=0.0, current_season="2025", base_value=3000) == 3000


def test_pick_value_future_year_discounted_by_probability():
    """Future picks: base_value * (1 - probability), integer truncated."""
    assert pick_value_under_reset("2026", 1, probability=0.0, current_season="2025", base_value=3000) == 3000
    assert pick_value_under_reset("2026", 1, probability=0.5, current_season="2025", base_value=3000) == 1500
    assert pick_value_under_reset("2026", 1, probability=1.0, current_season="2025", base_value=3000) == 0


def test_pick_value_truncates_to_int():
    """int() truncates (does not round)."""
    # 1000 * (1 - 0.3) = 700.0 exactly
    assert pick_value_under_reset("2026", 1, probability=0.3, current_season="2025", base_value=1000) == 700
    # 1000 * (1 - 0.333) = 667.0
    assert pick_value_under_reset("2026", 2, probability=0.333, current_season="2025", base_value=1000) == 667


# --- asset_value_under_reset ---

from dynasty_mcp.reset_scoring import asset_value_under_reset


def test_asset_value_unprotectable_player_at_p1_is_zero():
    """4th RB: contributes 0 to any slate, so protected_contribution=0 → reset_value=0 at p=1."""
    entries = [
        make_entry("qb1", "QB", 3000),
        make_entry("rb1", "RB", 2000),
        make_entry("wr1", "WR", 1800),
        make_entry("rb2", "RB", 500),  # won't be chosen for any starter/taxi slot
    ]
    val = asset_value_under_reset(entries[3], entries, probability=1.0)
    assert val == 0


def test_asset_value_unprotectable_player_at_p0_is_raw():
    """Same player at p=0: no reset discount, keeps raw value."""
    entries = [
        make_entry("qb1", "QB", 3000),
        make_entry("rb1", "RB", 2000),
        make_entry("wr1", "WR", 1800),
        make_entry("rb2", "RB", 500),
    ]
    val = asset_value_under_reset(entries[3], entries, probability=0.0)
    assert val == 500


def test_asset_value_marginal_taxi_contributes_its_own_value():
    """3rd TAXI slot: protected_contribution = its own value when it's the marginal taxi."""
    entries = [
        make_entry("qb1", "QB", 3000),
        make_entry("rb1", "RB", 2000),
        make_entry("wr1", "WR", 1800),
        make_entry("t1", "WR", 1000, SlotType.TAXI),
        make_entry("t2", "RB", 800, SlotType.TAXI),
        make_entry("t3", "WR", 600, SlotType.TAXI),  # fills 3rd slot exactly
    ]
    # best_with: 3000+2000+1800 + 1000+800+600 = 9200
    # best_without t3: 3000+2000+1800 + 1000+800 = 8600
    # protected_contribution = 600 = raw; at p=1: reset_value = 600
    val = asset_value_under_reset(entries[5], entries, probability=1.0)
    assert val == 600


def test_asset_value_no_valid_slate_without_entry():
    """Sole QB: best_without=0 (no valid slate), protected_contribution includes others' value."""
    entries = [
        make_entry("qb1", "QB", 1000),
        make_entry("rb1", "RB", 800),
        make_entry("wr1", "WR", 700),
    ]
    # best_with: 2500; best_without: 0 (no QB); protected_contribution = 2500
    # raw = 1000; at p=1: int(1.0 * 2500 + 0 * 1000) = 2500
    val = asset_value_under_reset(entries[0], entries, probability=1.0)
    assert val == 2500


def test_asset_value_interpolates_at_half_probability():
    """At p=0.5, result is midpoint of protected_contribution and raw."""
    entries = [
        make_entry("qb1", "QB", 3000),
        make_entry("rb1", "RB", 2000),
        make_entry("wr1", "WR", 1800),
        make_entry("rb2", "RB", 500),  # unprotectable
    ]
    # protected_contribution = 0, raw = 500
    # reset_value = int(0.5 * 0 + 0.5 * 500) = 250
    val = asset_value_under_reset(entries[3], entries, probability=0.5)
    assert val == 250
```

- [ ] **Step 2: Run — verify FAIL**

```bash
python -m pytest tests/test_reset_scoring.py::test_pick_value_current_year_unaffected_by_probability tests/test_reset_scoring.py::test_asset_value_unprotectable_player_at_p1_is_zero -v 2>&1 | tail -10
```

Expected: `ImportError` — functions not defined yet.

- [ ] **Step 3: Append implementations to `src/dynasty_mcp/reset_scoring.py`**

```python
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
```

- [ ] **Step 4: Run — verify PASS**

```bash
python -m pytest tests/test_reset_scoring.py -v 2>&1 | tail -25
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_reset_scoring.py src/dynasty_mcp/reset_scoring.py
git commit -m "feat: add pick_value_under_reset and asset_value_under_reset to reset_scoring"
```

---

## Task 5: TDD `reset_optimizer` tool

**Files:**
- Create: `tests/test_tools/test_reset_optimizer.py`
- Create: `src/dynasty_mcp/tools/reset_optimizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tools/test_reset_optimizer.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.reset_optimizer import reset_optimizer

FIX = Path(__file__).parent.parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    return build_test_context(cache=cache, username="dakeif", league_id="L1")


async def _seed(mock: respx.Router) -> None:
    mock.get("/league/L1").respond(json=load("sleeper_league.json"))
    mock.get("/league/L1/rosters").respond(json=load("sleeper_rosters.json"))
    mock.get("/league/L1/users").respond(json=load("sleeper_users.json"))
    mock.get("/players/nfl").respond(json=load("sleeper_players.json"))


@pytest.mark.asyncio
async def test_reset_optimizer_returns_five_options(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    assert result.roster_id == 7
    assert len(result.options) == 5
    assert result.options == sorted(result.options, key=lambda o: o.protected_value, reverse=True)


@pytest.mark.asyncio
async def test_reset_optimizer_rank1_rb_te_is_achane(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    # De'Von Achane (player_id "9226") is highest-value RB/TE on dakeif's roster
    assert result.options[0].protected.rb_te.player.player_id == "9226"


@pytest.mark.asyncio
async def test_reset_optimizer_value_at_risk_is_positive(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    assert result.options[0].value_at_risk > 0


@pytest.mark.asyncio
async def test_reset_optimizer_team_me_equals_team_7(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result_me = await reset_optimizer(ctx, team="me")

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result_7 = await reset_optimizer(ctx, team=7)

    assert result_me.roster_id == result_7.roster_id == 7


@pytest.mark.asyncio
async def test_reset_optimizer_rank1_swaps_empty(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    assert result.options[0].swaps_from_top == []


@pytest.mark.asyncio
async def test_reset_optimizer_lower_ranks_have_swaps(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    # At least one of ranks 2-5 should differ from rank 1 in some starter slot
    swapped_options = [o for o in result.options[1:] if o.swaps_from_top]
    assert len(swapped_options) >= 1


@pytest.mark.asyncio
async def test_reset_optimizer_result_is_serializable(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm, respx.mock(
        base_url="https://api.fantasycalc.com"
    ) as fm:
        await _seed(sm)
        fm.get("/values/current").respond(json=load("fantasycalc_values.json"))
        result = await reset_optimizer(ctx)

    dumped = result.model_dump(mode="json")
    assert isinstance(dumped["options"], list)
    assert "protected" in dumped["options"][0]
```

- [ ] **Step 2: Run — verify FAIL**

```bash
python -m pytest tests/test_tools/test_reset_optimizer.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'dynasty_mcp.tools.reset_optimizer'`.

- [ ] **Step 3: Create `src/dynasty_mcp/tools/reset_optimizer.py`**

```python
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
```

- [ ] **Step 4: Run — verify PASS**

```bash
python -m pytest tests/test_tools/test_reset_optimizer.py -v 2>&1 | tail -20
```

Expected: all 7 tests pass.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest --ignore=tests/test_contract.py -q 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/test_tools/test_reset_optimizer.py src/dynasty_mcp/tools/reset_optimizer.py
git commit -m "feat: add reset_optimizer tool"
```

---

## Task 6: Register `reset_optimizer` in `server.py` + update `test_server.py`

**Files:**
- Modify: `src/dynasty_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Add import and tool registration to `src/dynasty_mcp/server.py`**

After the existing imports (e.g., after `from dynasty_mcp.tools.waivers import ...`), add:

```python
from dynasty_mcp.tools.reset_optimizer import reset_optimizer as tool_reset_optimizer
```

Inside `build_server`, after the `refresh_cache` block and before `return mcp`, add:

```python
    @mcp.tool()
    async def reset_optimizer(
        team: str | int = "me",
        reset_probability: float = 1.0,
        top_n: int = 5,
    ) -> Any:
        """Compute the optimal reset-protection slate for a team.

        Returns top-N slates (default 5) ranked by protected_value with per-slot
        swap deltas and value_at_risk so you can evaluate trade-offs at a glance.
        """
        return (
            await tool_reset_optimizer(
                ctx,
                team=team,
                reset_probability=reset_probability,
                top_n=top_n,
            )
        ).model_dump(mode="json")
```

- [ ] **Step 2: Update `tests/test_server.py`**

Find the `expected` set in `test_server_registers_expected_tools` and add `"reset_optimizer"`:

```python
    expected = {
        "get_league_context",
        "get_roster",
        "list_rosters",
        "get_team_value_breakdown",
        "get_player_values",
        "get_matchup",
        "get_free_agents",
        "get_trending",
        "get_transactions",
        "get_draft",
        "refresh_cache",
        "reset_optimizer",
    }
```

- [ ] **Step 3: Run — verify PASS**

```bash
python -m pytest tests/test_server.py -v 2>&1 | tail -10
```

Expected: `test_server_registers_expected_tools` passes.

- [ ] **Step 4: Run full suite**

```bash
python -m pytest --ignore=tests/test_contract.py -q 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/server.py tests/test_server.py
git commit -m "feat: register reset_optimizer in FastMCP server"
```

---

## Task 7: Add live smoke test

**Files:**
- Modify: `tests/test_contract.py`

- [ ] **Step 1: Add live smoke test to `tests/test_contract.py`**

After the existing `test_live_my_roster_returns_players` function, append:

```python
@pytest.mark.asyncio
async def test_live_reset_optimizer_returns_options(tmp_path: Path) -> None:
    from dynasty_mcp.tools.reset_optimizer import reset_optimizer

    username = os.environ["SLEEPER_USERNAME"]
    league_id = os.environ["SLEEPER_LEAGUE_ID"]
    cache = Cache.open(tmp_path / "live.db")
    ctx = build_test_context(
        cache=cache, username=username, league_id=league_id, season=os.environ.get("SEASON", "2025")
    )
    result = await reset_optimizer(ctx)
    assert result.options, "expected at least one slate option"
    assert result.options[0].protected_value > 0
    assert result.options == sorted(result.options, key=lambda o: o.protected_value, reverse=True)
    # Confirm result serializes cleanly
    result.model_dump(mode="json")
```

- [ ] **Step 2: Verify live test is skipped in normal runs**

```bash
python -m pytest tests/test_contract.py -v 2>&1 | tail -10
```

Expected: all contract tests skipped (DYNASTY_LIVE not set).

- [ ] **Step 3: Run full suite one final time**

```bash
python -m pytest --ignore=tests/test_contract.py -q 2>&1 | tail -5
```

Expected: all tests pass, no warnings about unresolved imports.

- [ ] **Step 4: Commit**

```bash
git add tests/test_contract.py
git commit -m "test: add live smoke test for reset_optimizer"
```

---

## Self-Review

### Spec coverage

| Spec requirement | Covered by |
|---|---|
| `reset_scoring.py` — pure functions, no I/O | Tasks 2–4 |
| `enumerate_slates` — legal combos, TE in RB/TE or WR/TE | Task 2 |
| `rank_slates` — top-N, deterministic tiebreak | Task 2 |
| `value_at_risk` — unprotected asset sum | Task 3 |
| `pick_value_under_reset` — current-year unchanged, future discounted | Task 4 |
| `asset_value_under_reset` — marginal value formula | Task 4 |
| `reset_optimizer` MCP tool — top-5 slates, swap diffs, notes | Task 5 |
| `team="me"` default, `reset_probability` param, `top_n` | Task 5 |
| Server registration | Task 6 |
| Live smoke test | Task 7 |
| `taxi_pool_size` in result | Task 5 |
| Edge case notes (no TAXI, no value, no QB) | Task 5 |

**Not in this plan (deferred to item 4):** `reset_trades` tool, picks as assets, `TradeAsset`/`TradeProposal`/`ResetTradeFinderResult` models.

### Placeholder scan

No TBD, TODO, or implement-later placeholders found.

### Type consistency

- `TeamSpec` imported from `dynasty_mcp.tools.rosters` in `reset_optimizer.py` — same location as existing tools. ✓
- `ProtectionSlot`, `ProtectionSlate`, `Swap`, `SlateOption`, `ResetOptimizerResult` defined in `models.py` and imported consistently in `reset_scoring.py` and `reset_optimizer.py`. ✓
- `value_at_risk(entries, slate)` — `entries: list[RosterEntry]` (full view.entries including None-value), `slate: ProtectionSlate`. Used correctly in Task 5 (`value_at_risk(view.entries, slate)`). ✓
- `rank_slates` returns `list[ProtectionSlate]` with `n=1` — safe `[0]` access after `if best_with_slates` guard. ✓
