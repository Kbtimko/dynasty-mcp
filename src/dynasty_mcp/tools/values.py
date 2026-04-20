from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from dynasty_mcp.context import Context
from dynasty_mcp.models import Player, Value


class PlayerValueRow(BaseModel):
    player: Player
    value: Value


def _build_index(fc_rows: list[dict[str, Any]]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for row in fc_rows:
        sid = str((row.get("player") or {}).get("sleeperId") or "")
        if sid and row.get("value") is not None:
            idx[sid] = int(row["value"])
    return idx


def _older_snapshot(ctx: Context, window: timedelta) -> dict[str, int] | None:
    target = datetime.now(timezone.utc) - window
    row = ctx.cache.conn.execute(
        "SELECT data FROM values_snapshots WHERE fetched_at <= ? "
        "ORDER BY fetched_at DESC LIMIT 1",
        (target.isoformat(),),
    ).fetchone()
    if not row:
        return None
    import json as _json

    return _build_index(_json.loads(row[0]))


async def get_player_values(
    ctx: Context,
    *,
    position: str | None = None,
    rookies_only: bool = False,
    limit: int = 50,
) -> list[PlayerValueRow]:
    if not ctx.league_id:
        raise ValueError("league_id required")
    league = await ctx.sleeper.get_league(ctx.league_id)
    fc = await ctx.fantasycalc.get_current(league)
    players = await ctx.sleeper.get_players()
    now_idx = _build_index(fc)
    prior_idx = _older_snapshot(ctx, timedelta(days=7)) or {}

    rows: list[PlayerValueRow] = []
    for pid, val in sorted(now_idx.items(), key=lambda kv: kv[1], reverse=True):
        data = players.get(pid)
        if data is None:
            continue
        if position and data.get("position") != position:
            continue
        if rookies_only and int(data.get("years_exp") or 99) != 0:
            continue
        delta_7d = (val - prior_idx[pid]) if pid in prior_idx else None
        rows.append(
            PlayerValueRow(
                player=Player(
                    player_id=pid,
                    full_name=(
                        data.get("full_name")
                        or " ".join(
                            p for p in (data.get("first_name"), data.get("last_name")) if p
                        )
                        or pid
                    ),
                    position=data.get("position") or "UNK",
                    team=data.get("team"),
                    age=data.get("age"),
                    status=data.get("status"),
                ),
                value=Value(current=val, delta_7d=delta_7d),
            )
        )
        if len(rows) >= limit:
            break
    return rows
