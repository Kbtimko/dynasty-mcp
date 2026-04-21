# Reset-Aware Dynasty Tools: Design Spec

**Date:** 2026-04-20
**Status:** Approved for implementation planning
**Follows:** [2026-04-19-dynasty-mcp-design.md](2026-04-19-dynasty-mcp-design.md) (v1 primitives)

## Purpose

Add two thick, opinionated MCP tools to dynasty-mcp that reason about the league's semi-hard reset mechanics:

1. **`reset_optimizer`** — picks the optimal (1 QB, 1 RB/TE, 1 WR/TE, 3 TAXI) protection slate for a roster and surfaces top-5 alternatives with per-slot swap deltas.
2. **`reset_trades`** — reset-probability-weighted trade finder between "me" and one or all counterparties, discounting voided future picks and unprotectable depth, upweighting protectable starters and TAXI-eligible rookies.

These are the first thick tools in the codebase — prior primitives (`get_roster`, `get_player_values`, etc.) return raw data and leave composition to Claude. The reset math is too expensive to expect Claude to do by hand each call, so it lives server-side.

League context: 14-team Superflex TE-premium dynasty on Sleeper ("The First Galactic Empire"). Semi-hard reset protections per team = 1 QB + 1 RB/TE + 1 WR/TE + 3 TAXI; traded future-year picks are voided on reset.

## Scope

### In scope
- Pure scoring module (`reset_scoring.py`) with testable primitives.
- `reset_optimizer` MCP tool returning top-5 protection slates with swap highlights.
- `reset_trades` MCP tool — bilateral, 1-for-1 and 2-for-1 (either direction) trades, mutual-gain filter, rationale flags.
- Asset pool includes players AND rookie picks (current + future year, with reset-aware discount on future).

### Out of scope (v1 of these tools)
- 3-for-2 / higher-cardinality trades (caps at 2 per side).
- Multi-team trades.
- Auto-estimating `reset_probability` from league state.
- League-scoring-adjusted values (systematic corrections for TE-prem, 0.5 per 1st down, 5pt pass TD bias in FantasyCalc). Tracked as follow-up.
- Caching of optimizer/trade-finder output (both recompute on each call).

## Design decisions (locked)

| # | Decision | Rationale |
|---|---|---|
| Q1 | Use FantasyCalc values as-is. | Uniform source; league-specific scoring edges absorbed into Claude's narration. League-scoring-adjusted values deferred as a follow-up project. |
| Q2 | `reset_probability: float = 0.0..1.0` parameter on both tools. | Max transparency; Claude or user steers the analysis directly. |
| Q3 | Optimizer returns top-5 slates + per-slot swap deltas. | The top slate is rarely controversial; the interesting info is the delta between options 1 and 2. |
| Q4 | Trade finder: shop-me default (`partner=None`) with optional `partner: TeamSpec` knob. | Collapses "scan all 13 partners" and "deep-dive on one partner" into one tool. |
| Q5 | TAXI-eligible = currently on any team's TAXI squad (Sleeper `roster.taxi`). | Matches what reset actually protects; preserves status via TAXI-to-TAXI trade rule. |
| Arch | Approach 2: pure scoring module + two tool wrappers. | Mirrors existing `sources/` (pure) vs `tools/` (wiring) split; trade finder reuses optimizer math rather than duplicating. |

## Architecture

```
tools/reset_optimizer.py  ──┐
                            ├──▶  reset_scoring.py  ──▶  models (RosterEntry, Player, Value)
tools/reset_trades.py     ──┘
                 │
                 └─ use tools/rosters.py helpers for roster/user resolution + FC value maps
```

New files:
- `src/dynasty_mcp/reset_scoring.py` — pure functions, no I/O, no context.
- `src/dynasty_mcp/tools/reset_optimizer.py` — MCP tool wrapper.
- `src/dynasty_mcp/tools/reset_trades.py` — MCP tool wrapper.
- `tests/test_reset_scoring.py`, `tests/test_reset_optimizer.py`, `tests/test_reset_trades.py`.

Touched files:
- `src/dynasty_mcp/server.py` — register the two new tools.
- `src/dynasty_mcp/models.py` — add result models (see shapes below).
- `tests/test_live.py` — add one live smoke check per tool.

## Component 1 — `reset_scoring.py` (pure)

### Data shapes

```python
class ProtectionSlot(str, Enum):
    QB = "qb"
    RB_TE = "rb_te"
    WR_TE = "wr_te"
    TAXI = "taxi"

class ProtectionSlate(BaseModel):
    qb: RosterEntry
    rb_te: RosterEntry          # position in {RB, TE}
    wr_te: RosterEntry          # position in {WR, TE}
    taxi: list[RosterEntry]     # len ≤ 3, slot_type == TAXI
    protected_value: int        # sum of .value.current (None treated as 0)
```

### Public functions

1. `enumerate_slates(entries: list[RosterEntry]) -> Iterator[ProtectionSlate]`
   Yields every legal slate. A TE may fill RB/TE or WR/TE (or both, if the roster has 2 TEs). A player cannot be double-counted across slots within one slate. Search space is small (≤ a few hundred).

2. `rank_slates(entries: list[RosterEntry], *, n: int = 5) -> list[ProtectionSlate]`
   Top-N by `protected_value` descending. Deterministic tiebreak by sorted player_id tuple.

3. `value_at_risk(entries: list[RosterEntry], slate: ProtectionSlate) -> int`
   Sum of `entry.value.current` (None → 0) for every roster player NOT in the slate (including non-TAXI entries and unchosen TAXI).

4. `pick_value_under_reset(season: str, round_: int, probability: float, current_season: str, base_value: int) -> int`
   - Current-year pick (`season == current_season`): returns `base_value` regardless of probability (current-year picks are not voided).
   - Future-year pick (`season > current_season`): returns `base_value * (1 - probability)`.
   - Integer truncation via `int()`.

5. `asset_value_under_reset(entry: RosterEntry, owner_entries: list[RosterEntry], probability: float) -> int`
   Computes a player's reset-aware value on a given roster:
   - `best_with = rank_slates(owner_entries_including_entry, n=1)[0].protected_value`
   - `best_without = rank_slates(owner_entries_excluding_entry, n=1)[0].protected_value`
   - `protected_contribution = max(0, best_with - best_without)`
   - `raw = entry.value.current or 0`
   - `reset_value = int(probability * protected_contribution + (1 - probability) * raw)`
   - Key property: a player who'd be protected anyway keeps ≈ raw value; a player who wouldn't drops toward 0 as probability → 1.

### Invariants
- `rank_slates` with `n=0` or empty entries returns `[]`.
- `enumerate_slates` on a roster without a QB yields `[]` (QB is mandatory per rules).
- Entries with `value.current is None` are legal but contribute 0 to all value metrics.

## Component 2 — `tools/reset_optimizer.py`

### Tool signature
```python
async def reset_optimizer(
    ctx: Context,
    *,
    team: TeamSpec = "me",
    reset_probability: float = 1.0,    # default assumes reset happens
    top_n: int = 5,
) -> ResetOptimizerResult
```

Default `reset_probability=1.0` (not 0.0) because calling this tool means you're planning for a reset. The probability knob is primarily to support conditional "what if 60% chance" exploration.

### Result shape
```python
class Swap(BaseModel):
    slot: ProtectionSlot
    from_player: str     # player_id in rank-1 slate
    to_player: str       # player_id in this slate
    value_delta: int     # (to.value - from.value)

class SlateOption(BaseModel):
    rank: int            # 1..top_n
    protected: ProtectionSlate
    protected_value: int
    value_at_risk: int
    swaps_from_top: list[Swap]    # [] for rank 1

class ResetOptimizerResult(BaseModel):
    roster_id: int
    owner_username: str
    reset_probability: float
    total_roster_value: int
    options: list[SlateOption]
    taxi_pool_size: int
    notes: list[str]
```

### Algorithm
1. `view = await get_roster(ctx, team=team)` (reuses existing helper).
2. Filter `view.entries` to players with `value.current is not None`. Log any dropped entries to `notes` (e.g., "player X has no FantasyCalc value, skipped").
3. `slates = rank_slates(valued_entries, n=top_n)`.
4. For each slate, compute `value_at_risk` against the full (unfiltered) entries list, so the "quality hitting the re-draft pool" metric is consistent.
5. For rank ≥ 2, diff against rank 1: `swaps_from_top` lists each slot that changed, with `value_delta` (destination value − source value; negative for rank ≥ 2 by construction).
6. `taxi_pool_size = count of entries where slot_type == TAXI and value.current is not None`.
7. Emit `notes` for edge cases: roster has <3 TAXI → "3rd TAXI slot unused"; no TE → "RB/TE and WR/TE slots fall back to RB-only and WR-only"; QB-starved → "only one QB available; protection forced".

### Why probability doesn't affect slate ranking
The optimizer answers "which slate maximizes protected value if reset happens." Probability affects what you'd **pay** in trades — the trade finder's job. Keeping the optimizer probability-agnostic makes the two tools composable.

## Component 3 — `tools/reset_trades.py`

### Tool signature
```python
async def reset_trades(
    ctx: Context,
    *,
    partner: TeamSpec | None = None,        # None = scan all 13 counterparties
    reset_probability: float = 0.0,          # default: status-quo
    max_send: int = 2,
    max_recv: int = 2,
    min_edge: int = 500,
    top_n: int = 10,
) -> ResetTradeFinderResult
```

### Result shape
```python
class TradeAsset(BaseModel):
    kind: Literal["player", "pick"]
    asset_id: str                       # Sleeper player_id or "2027_1st_from_r7"
    display_name: str
    raw_value: int
    reset_adjusted_value: int
    protectable_on_receiver: bool       # False for picks

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

### Algorithm
1. Build rosters for `"me"` and each counterparty (or just `partner` if set).
2. Build asset pools:
   - **Players:** `view.entries` with `value.current is not None`.
   - **Picks:** merge `sleeper.get_traded_picks(league_id)` onto the default "each roster owns its own season/round picks" baseline. Match each pick's `display_name` (e.g. "2026 Mid 1st") to a FantasyCalc row for `base_value`; unmatched picks log a `notes` warning and default to 0.
3. Pre-compute `my_base_slate` and `their_base_slate` (rank-1 slates) for each side.
4. Prune each side's asset pool to top 15 by `raw_value`.
5. Enumerate `(send, recv)` subsets with `1 ≤ |send| ≤ max_send`, `1 ≤ |recv| ≤ max_recv`.
6. For each candidate:
   - Build post-trade entry lists for both sides.
   - Recompute rank-1 post-trade slates.
   - `my_incoming = Σ reset_adjusted_value(asset, post_trade_my_entries, probability)` for recv assets (picks via `pick_value_under_reset`).
   - `my_outgoing = Σ reset_adjusted_value(asset, my_base_entries, probability)` for send assets.
   - `my_net_edge = my_incoming - my_outgoing`.
   - Mirror for partner.
7. Keep if **both** `my_net_edge ≥ min_edge` AND `partner_net_edge ≥ min_edge`.
8. Tag `rationale_flags`:
   - `fills_my_{qb|rb_te|wr_te}_protection` — incoming asset changes my post-trade rank-1 slate at that slot.
   - `i_surrender_unprotectable_depth` — every outgoing player has `protected_contribution == 0` in my base slate.
   - `future_pick_discounted_{N}%` — at least one future-year pick present, with the applied discount.
   - `partner_rebuilds_taxi` — any asset on either side is currently on the counterparty's TAXI.
9. Sort by `my_net_edge` desc, slice to `top_n`.

### Picks
- Identity: `"{season}_{round}_from_r{original_roster_id}"` — disambiguates multi-pick rounds.
- Ownership lookup via `sleeper.get_traded_picks`; default owner = original roster when no trade record.
- Current-year picks bypass the reset discount entirely (rules: traded future picks don't carry over; current-year pick voided only if the draft format itself changes, which is a rule the tool doesn't model).

### Edge cases
- Partner with no edge-satisfying trades → empty `proposals`, `notes` explains.
- `reset_probability=0.0` → future picks undiscounted; behaves like a vanilla trade finder.
- `reset_probability=1.0` → future picks → 0, unprotectable depth → 0; only slate-altering trades and current-year-pick deals surface.

## Testing

### Unit tests — `tests/test_reset_scoring.py` (no I/O)
- `enumerate_slates`: correct count on canonical rosters; TE-in-RB/TE variant; TE-TE slate; missing TE; zero TAXI.
- `rank_slates`: top-1 = max; descending; deterministic tiebreak; `n > |enumerated|` returns all.
- `value_at_risk`: consistent with `total − protected`; `None` values contribute 0.
- `pick_value_under_reset`: current-year unchanged; future-year at probability 0/0.5/1.0.
- `asset_value_under_reset`: protected player stays at full raw (p=1.0); non-protected drops to 0 (p=1.0); marginal case (player replacing 3rd TAXI slot) contributes delta only.

### Tool tests — `tests/test_reset_optimizer.py`, `tests/test_reset_trades.py`
Use existing fixture pattern + `build_test_context`.
- `reset_optimizer`: against dakeif fixture — 5 options; rank-1 RB/TE includes Achane or Loveland; `value_at_risk > 0`; `team="me"` ≡ `team=7`.
- `reset_trades`: default proposals satisfy mutual-gain filter; `probability=1.0` surviving proposals either flip a slot or use current-year picks; `partner=<id>` narrows `considered_partners`; raising `min_edge` empties proposals.

### Live smoke — `tests/test_live.py` (DYNASTY_LIVE=1)
One call per tool against the real league; assertions limited to non-empty + schema validity.

### Coverage
- `reset_scoring.py`: 100% line coverage.
- Tools: each `rationale_flags` path at least once.

## Server wiring

Both tools registered in `server.py` alongside existing primitives:
- Names: `reset_optimizer`, `reset_trades`.
- Descriptions signal that these are thick/opinionated (first of their kind in the server).
- `model_dump(mode='json')` per existing pattern.

## Follow-ups (not in this spec)

1. **League-scoring-adjusted values (Q1-C).** Derive per-player value adjustments from Sleeper scoring settings + historical stats; swap behind `league_adjust: bool = False`. Own spec.
2. **Static pick-value fallback table.** If FantasyCalc pick-name matching fails frequently, add canonical `{round: value}` defaults.
3. **3-for-2 / multi-team trades.** Gate on demand; needs stronger pruning heuristics.
4. **`reset_probability` auto-estimator.** Only if league state cleanly signals reset-vote status.

## Risks / open questions

- **FantasyCalc pick-name stability.** Names like "2026 Mid 1st" are FantasyCalc's convention; if they change upstream, pick valuation silently degrades. Mitigated by `notes` warnings when a match fails.
- **Asset-pool prune at top-15.** Arbitrary; if it proves too tight for rebuilding teams with unusual depth, surface as `max_assets_per_side` param.
- **`min_edge=500` default.** FantasyCalc-unit; low-end starter weekly value. May need tuning once real output is inspected.
- **Symmetric mutual-gain filter.** Hides one-sided trades that might still be worth proposing. If that shape is wanted, add `require_partner_edge: bool = True` later.
