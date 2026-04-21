from __future__ import annotations

import math
from typing import Any, Literal

from dynasty_mcp.context import Context


async def get_transactions(
    ctx: Context,
    *,
    days: int = 7,
    type: Literal["trade", "waiver", "free_agent"] | None = None,
) -> list[dict[str, Any]]:
    if not ctx.league_id:
        raise ValueError("league_id required")
    state = await ctx.sleeper.get_state()
    current_week = int(state.get("week") or 1)
    weeks_back = max(1, math.ceil(days / 7))
    weeks = [
        w for w in range(current_week, current_week - weeks_back - 1, -1) if w >= 1
    ]

    out: list[dict[str, Any]] = []
    for w in weeks:
        batch = await ctx.sleeper.get_transactions(ctx.league_id, w)
        for tx in batch:
            if type and tx.get("type") != type:
                continue
            out.append(tx)
    return out
