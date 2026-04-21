# First Galactic Empire — League Context

## Basics

- **Format:** 14-team superflex, TE premium (0.5 bonus/reception for TEs → full 1.0 PPR)
- **Keith:** username `dakeif`, roster_id 7, league_id `1335327387256119296`
- **Roster:** QB, RB, RB, WR, WR, TE, FLEX, FLEX, SUPER_FLEX + 14 bench + 20 TAXI + 5 IR

## Scoring quirks vs. vanilla 0.5 PPR

These move player values significantly from FantasyCalc's defaults:

- **Passing:** 5 pts/TD (not 4), -2 INT, 1 pt/25 yds; 1.5 bonus for 400+ game, +2 for 40-yd TD
- **Rushing:** 1 pt/10 yds, **+0.5 per rushing 1st down**, +1 for 100–199 game, +2 for 200+, +2 for 40-yd TD
- **Receiving:** 1 pt/10 yds, 0.5 per reception (+0.5 TE bonus = **1.0/rec for TEs**), **+0.5 per receiving 1st down**, +1 for 100–199 game, +2 for 200+, +2 for 40-yd TD

**Implication:** TEs, high-volume possession WRs, workhorse RBs, and elite QBs are all underpriced by FantasyCalc's generic dynasty values. See TODO #5 (scoring-adjusted values) for the planned fix.

## Reset mechanics

Triggered when the **Empire pot is won** (back-to-back championships OR 2-of-3 championships + 1-seed in 2-of-3 years). Requires 7-of-14 YES votes after March 1.

**Protections per team:** 1 QB · 1 RB/TE · 1 WR/TE · 3 TAXI — everything else enters re-draft pool.

**Key reset rules:**
- All traded future picks are voided (current-year picks are unaffected)
- Re-draft format: snake or auction (league decides)
- `reset_probability` parameter on `reset_optimizer` and `reset_trades` tools lets you plan for partial-probability scenarios (default 1.0)

## TAXI rules

- Rookies only; max 3 full seasons on TAXI
- Locks at start of regular season; once activated to active roster, cannot return to TAXI
- TAXI trades must be TAXI-to-TAXI; notify commissioner within 48 hrs
- **TAXI stealing** (during rookie draft): trade a 1st to steal a player on TAXI ≥1 full season, or a 2nd for ≥2 full seasons; original team has 24 hrs to activate (protects but burns a TAXI slot)

## Transactions

- Trade deadline: Week 13
- Future-year pick trades require league-dues deposit (50% for 1st, 25% for 2nd)
- $50 FAAB, $1 min bid, Wed–Sun 11am Central

## Keith's core protectable assets (as of 2026-04-21)

| Player | Protection slot |
|---|---|
| De'Von Achane | RB/TE or TAXI |
| Colston Loveland | RB/TE or TAXI |
| Rashee Rice | WR/TE or TAXI |
| George Pickens | WR/TE or TAXI |
| Rome Odunze | WR/TE or TAXI |

**QB room is the weak spot** (Darnold / Fields / Geno Smith — none locks the QB protection slot cleanly). Full current roster: use `get_roster` live.
