# Reset Trades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the reset-aware tools suite — add the `reset_trades` MCP tool (bilateral reset-probability-weighted trade finder) and the tool-level integration tests for the already-implemented `reset_optimizer`.

**Architecture:** Result models (TradeAsset, TradeProposal, ResetTradeFinderResult) land in `models.py`. `reset_trades.py` is self-contained: pick-pool helpers live alongside the tool function rather than being extracted — YAGNI, they're only used here. The tool reuses `reset_scoring` primitives (`asset_value_under_reset`, `pick_value_under_reset`, `rank_slates`) and private helpers from `tools/rosters.py` (`_resolve_roster`, `_value_map`, `_classify`, `_player_from_sleeper`).

**Tech Stack:** Python 3.12, Pydantic v2, FastMCP, respx, pytest-asyncio

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `src/dynasty_mcp/models.py` | Add `TradeAsset`, `TradeProposal`, `ResetTradeFinderResult` |
| Create | `tests/test_reset_optimizer.py` | Integration tests for already-implemented reset_optimizer tool |
| Create | `src/dynasty_mcp/tools/reset_trades.py` | reset_trades tool + pick-pool helpers |
| Create | `tests/test_reset_trades.py` | Integration tests for reset_trades |
| Modify | `src/dynasty_mcp/server.py` | Register `reset_trades` |
| Modify | `tests/test_server.py` | Add `reset_trades` to expected tools set |
| Modify | `tests/test_contract.py` | Add live smoke test for reset_trades |

---

## Task 1: Add result models to `models.py`

**Files:**
- Modify: `src/dynasty_mcp/models.py`

No test for pure data shapes; later tasks exercise them.

- [ ] **Step 1: Append models to `src/dynasty_mcp/models.py`**

Open `src/dynasty_mcp/models.py`. At the very end (after `ResetOptimizerResult`), add:

```python
class TradeAsset(BaseModel):
    kind: Literal["player", "pick"]
    asset_id: str
    display_name: str
    raw_value: int
    reset_adjusted_value: int
    protectable_on_receiver: bool


class TradeProposal(BaseModel):
    rank: int
    partner_roster_id: int
    partner_username: str
    my_send: list[TradeAsset]
    my_recv: list[TradeAsset]
    my_net_edge: int
    partner_net_edge: int
    rationale_flags: list[str]


class ResetTradeFinderResult(BaseModel):
    reset_probability: float
    proposals: list[TradeProposal]
    considered_partners: list[int]
    notes: list[str]
```

- [ ] **Step 2: Verify existing suite still passes**

```bash
python -m pytest --ignore=tests/test_contract.py -q 2>&1 | tail -5
```

Expected: same pass count as before, 0 failures.

- [ ] **Step 3: Commit**

```bash
git add src/dynasty_mcp/models.py
git commit -m "feat: add reset trades result models"
```

---

## Task 2: Integration tests for `reset_optimizer`

The tool is already implemented; these tests should pass immediately after being written.

**Files:**
- Create: `tests/test_reset_optimizer.py`

- [ ] **Step 1: Write tests**

Create `tests/test_reset_optimizer.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context
from dynasty_mcp.tools.reset_optimizer import reset_optimizer

FIX = Path(__file__).parent / "fixtures"
LEAGUE_ID = "1335327387256119296"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    cache.put_values_snapshot(load("fantasycalc_values.json"), fetched_at=datetime.now(timezone.utc))
    cache.put_players(load("sleeper_players.json"), fetched_at=datetime.now(timezone.utc))
    return build_test_context(cache=cache, username="dakeif", league_id=LEAGUE_ID)


def _seed(mock: respx.Router) -> None:
    mock.get(f"/league/{LEAGUE_ID}").respond(json=load("sleeper_league.json"))
    mock.get(f"/league/{LEAGUE_ID}/rosters").respond(json=load("sleeper_rosters.json"))
    mock.get(f"/league/{LEAGUE_ID}/users").respond(json=load("sleeper_users.json"))


@pytest.mark.asyncio
async def test_reset_optimizer_returns_five_options(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_optimizer(ctx)

    assert result.roster_id == 7
    assert len(result.options) == 5
    assert result.options == sorted(result.options, key=lambda o: o.protected_value, reverse=True)


@pytest.mark.asyncio
async def test_reset_optimizer_rank1_swaps_empty(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_optimizer(ctx)

    assert result.options[0].swaps_from_top == []


@pytest.mark.asyncio
async def test_reset_optimizer_value_at_risk_positive(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_optimizer(ctx)

    assert result.options[0].value_at_risk > 0


@pytest.mark.asyncio
async def test_reset_optimizer_team_int_matches_me(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result_me = await reset_optimizer(ctx, team="me")

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result_7 = await reset_optimizer(ctx, team=7)

    assert result_me.roster_id == result_7.roster_id == 7
    assert result_me.options[0].protected_value == result_7.options[0].protected_value


@pytest.mark.asyncio
async def test_reset_optimizer_result_serializable(ctx) -> None:
    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_optimizer(ctx)

    dumped = result.model_dump(mode="json")
    assert isinstance(dumped["options"], list)
    assert "protected" in dumped["options"][0]
    assert "swaps_from_top" in dumped["options"][0]
```

- [ ] **Step 2: Run — verify PASS (tool is already implemented)**

```bash
python -m pytest tests/test_reset_optimizer.py -v 2>&1 | tail -15
```

Expected: all 5 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_reset_optimizer.py
git commit -m "test: add integration tests for reset_optimizer tool"
```

---

## Task 3: Implement `reset_trades` (TDD)

**Files:**
- Create: `tests/test_reset_trades.py`
- Create: `src/dynasty_mcp/tools/reset_trades.py`

### Step 3a: Write failing tests

- [ ] **Step 1: Create `tests/test_reset_trades.py`**

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import respx

from dynasty_mcp.cache import Cache
from dynasty_mcp.context import build_test_context

FIX = Path(__file__).parent / "fixtures"
LEAGUE_ID = "1335327387256119296"


def load(name: str) -> object:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def ctx(tmp_path: Path):
    cache = Cache.open(tmp_path / "c.db")
    cache.put_values_snapshot(load("fantasycalc_values.json"), fetched_at=datetime.now(timezone.utc))
    cache.put_players(load("sleeper_players.json"), fetched_at=datetime.now(timezone.utc))
    return build_test_context(cache=cache, username="dakeif", league_id=LEAGUE_ID)


def _seed(mock: respx.Router) -> None:
    mock.get(f"/league/{LEAGUE_ID}").respond(json=load("sleeper_league.json"))
    mock.get(f"/league/{LEAGUE_ID}/rosters").respond(json=load("sleeper_rosters.json"))
    mock.get(f"/league/{LEAGUE_ID}/users").respond(json=load("sleeper_users.json"))
    mock.get(f"/league/{LEAGUE_ID}/traded_picks").respond(json=load("sleeper_traded_picks.json"))


@pytest.mark.asyncio
async def test_reset_trades_result_schema(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, min_edge=0, top_n=5)

    assert isinstance(result.proposals, list)
    assert isinstance(result.considered_partners, list)
    assert isinstance(result.notes, list)
    assert len(result.considered_partners) == 13  # 14 teams minus me


@pytest.mark.asyncio
async def test_reset_trades_partner_arg_narrows_partners(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, partner=1, min_edge=0, top_n=5)

    assert result.considered_partners == [1]


@pytest.mark.asyncio
async def test_reset_trades_high_min_edge_empties_proposals(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, partner=1, min_edge=9_999_999, top_n=5)

    assert result.proposals == []


@pytest.mark.asyncio
async def test_reset_trades_proposals_satisfy_mutual_gain_filter(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, partner=1, min_edge=0, top_n=20)

    for p in result.proposals:
        assert p.my_net_edge >= 0
        assert p.partner_net_edge >= 0


@pytest.mark.asyncio
async def test_reset_trades_proposals_sorted_by_my_net_edge(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, partner=1, min_edge=0, top_n=20)

    edges = [p.my_net_edge for p in result.proposals]
    assert edges == sorted(edges, reverse=True)


@pytest.mark.asyncio
async def test_reset_trades_result_serializable(ctx) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    with respx.mock(base_url="https://api.sleeper.app/v1") as sm:
        _seed(sm)
        result = await reset_trades(ctx, partner=1, min_edge=0, top_n=5)

    dumped = result.model_dump(mode="json")
    assert "proposals" in dumped
    assert "considered_partners" in dumped
    assert "notes" in dumped
```

- [ ] **Step 2: Run — verify FAIL**

```bash
python -m pytest tests/test_reset_trades.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'dynasty_mcp.tools.reset_trades'`

### Step 3b: Implement `reset_trades.py`

- [ ] **Step 3: Create `src/dynasty_mcp/tools/reset_trades.py`**

```python
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


# ---------------------------------------------------------------------------
# Internal asset representations
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Pick helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Slate helpers
# ---------------------------------------------------------------------------

def _slate_slot_map(slate) -> dict[str, str]:
    """Return {slot_name: player_id} for the three starter slots."""
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


# ---------------------------------------------------------------------------
# TradeAsset builder
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Rationale flag helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main tool
# ---------------------------------------------------------------------------

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

    # Identify "me"
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

    # Traded picks + pick pool
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

    # Determine counterparties
    if partner is not None:
        partner_roster_raw, _ = await _resolve_roster(ctx, ctx.league_id, partner)
        counterparty_roster_ids = [int(partner_roster_raw["roster_id"])]
    else:
        counterparty_roster_ids = [
            int(r["roster_id"]) for r in rosters_raw
            if int(r["roster_id"]) != my_roster_id
        ]

    # My base state
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

    # Enumerate proposals
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
                        # Build post-trade player entry lists
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

                        # Edge calculation
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

                        # Build output assets
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

                        # Rationale flags
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
```

- [ ] **Step 4: Run — verify PASS**

```bash
python -m pytest tests/test_reset_trades.py -v 2>&1 | tail -15
```

Expected: all 6 tests pass.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest --ignore=tests/test_contract.py -q 2>&1 | tail -5
```

Expected: all tests pass, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add tests/test_reset_trades.py src/dynasty_mcp/tools/reset_trades.py
git commit -m "feat: add reset_trades tool with pick-pool helpers"
```

---

## Task 4: Register `reset_trades` in `server.py`

**Files:**
- Modify: `src/dynasty_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Add import to `src/dynasty_mcp/server.py`**

After the existing `from dynasty_mcp.tools.reset_optimizer import reset_optimizer as tool_reset_optimizer` import, add:

```python
from dynasty_mcp.tools.reset_trades import reset_trades as tool_reset_trades
```

- [ ] **Step 2: Register the tool in `build_server`**

After the `reset_optimizer` tool block (before `return mcp`), add:

```python
    @mcp.tool()
    async def reset_trades(
        partner: str | int | None = None,
        reset_probability: float = 0.0,
        max_send: int = 2,
        max_recv: int = 2,
        min_edge: int = 500,
        top_n: int = 10,
    ) -> Any:
        """Find mutually beneficial trades, weighted by reset probability.

        Scans all 13 counterparties (or just `partner`) for 1-for-1 and 2-for-1
        trades where both sides gain at least `min_edge` in reset-adjusted value.
        Future-year picks are discounted by `reset_probability`.
        """
        return (
            await tool_reset_trades(
                ctx,
                partner=partner,
                reset_probability=reset_probability,
                max_send=max_send,
                max_recv=max_recv,
                min_edge=min_edge,
                top_n=top_n,
            )
        ).model_dump(mode="json")
```

- [ ] **Step 3: Add `reset_trades` to expected set in `tests/test_server.py`**

In `test_server_registers_expected_tools`, update the `expected` set to include `"reset_trades"`:

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
        "reset_trades",
    }
```

- [ ] **Step 4: Run — verify PASS**

```bash
python -m pytest tests/test_server.py -v 2>&1 | tail -10
```

Expected: `test_server_registers_expected_tools` passes.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest --ignore=tests/test_contract.py -q 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/dynasty_mcp/server.py tests/test_server.py
git commit -m "feat: register reset_trades in FastMCP server"
```

---

## Task 5: Live smoke test for `reset_trades`

**Files:**
- Modify: `tests/test_contract.py`

- [ ] **Step 1: Add smoke test to `tests/test_contract.py`**

After the existing `test_live_reset_optimizer_returns_options` function, append:

```python
@pytest.mark.asyncio
async def test_live_reset_trades_returns_result(tmp_path: Path) -> None:
    from dynasty_mcp.tools.reset_trades import reset_trades

    username = os.environ["SLEEPER_USERNAME"]
    league_id = os.environ["SLEEPER_LEAGUE_ID"]
    cache = Cache.open(tmp_path / "live.db")
    ctx = build_test_context(
        cache=cache, username=username, league_id=league_id, season=os.environ.get("SEASON", "2025")
    )
    result = await reset_trades(ctx, partner=1, min_edge=0, top_n=5)
    assert isinstance(result.proposals, list)
    assert result.considered_partners == [1]
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

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_contract.py
git commit -m "test: add live smoke test for reset_trades"
```

---

## Self-Review

### Spec coverage

| Spec requirement | Covered by |
|---|---|
| `TradeAsset`, `TradeProposal`, `ResetTradeFinderResult` models | Task 1 |
| `reset_optimizer` tool-level tests (fixture-based) | Task 2 |
| `reset_trades` MCP tool — bilateral, 1-for-1 and 2-for-1 | Task 3 |
| `partner=None` scans all 13 counterparties | Task 3 + test |
| `partner=<id>` narrows to one counterparty | Task 3 + test |
| Asset pool: players + picks (current + next season, rounds 1-4) | Task 3 |
| Pick value from FC name map; unmatched → 0 + notes | Task 3 |
| `pick_value_under_reset` applied to picks in edge calc | Task 3 |
| `asset_value_under_reset` applied to players in edge calc | Task 3 |
| Mutual-gain filter (`min_edge` on both sides) | Task 3 + test |
| `rationale_flags`: fills_my_*_protection | Task 3 |
| `rationale_flags`: i_surrender_unprotectable_depth | Task 3 |
| `rationale_flags`: future_pick_discounted_N% | Task 3 |
| `rationale_flags`: partner_rebuilds_taxi | Task 3 |
| Sort by `my_net_edge` desc, slice to `top_n` | Task 3 + test |
| `considered_partners` in result | Task 3 + test |
| `notes` for unmatched picks | Task 3 |
| Server registration + tool description | Task 4 |
| `test_server` updated | Task 4 |
| Live smoke test | Task 5 |

**Not in this plan (deferred):** `reset_probability` auto-estimator, league-scoring-adjusted values, 3-for-2 / multi-team trades, static pick-value fallback table.

### Placeholder scan

No TBD, TODO, or implement-later markers found.

### Type consistency

- `TeamSpec` imported from `dynasty_mcp.tools.rosters` — same as all other tools. ✓
- `_PlayerAsset` and `_PickAsset` are internal only; `TradeAsset`/`TradeProposal`/`ResetTradeFinderResult` are Pydantic models from `models.py`. ✓
- `_to_trade_asset` returns `TradeAsset`; used in both `my_send_assets` and `my_recv_assets` list comprehensions. ✓
- `rank_slates(entries, n=1)` → `list[ProtectionSlate]`; guarded by `if ..._list` before indexing. ✓
- `asset_value_under_reset(entry, entries, probability)` — all call sites pass `list[RosterEntry]` for second arg. ✓
- `pick_value_under_reset(season, round_, probability, current_season, base_value)` — all call sites match this signature. ✓
- `_resolve_roster` imported from `tools.rosters` — returns `(roster_raw, user)` tuple; only `roster_raw` used. ✓
