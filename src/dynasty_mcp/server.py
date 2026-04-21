from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from dynasty_mcp.context import Context
from dynasty_mcp.tools.admin import refresh_cache as tool_refresh_cache
from dynasty_mcp.tools.draft import get_draft as tool_get_draft
from dynasty_mcp.tools.league import get_league_context as tool_get_league_context
from dynasty_mcp.tools.matchups import get_matchup as tool_get_matchup
from dynasty_mcp.tools.reset_optimizer import reset_optimizer as tool_reset_optimizer
from dynasty_mcp.tools.rosters import (
    get_roster as tool_get_roster,
    get_team_value_breakdown as tool_get_team_value_breakdown,
    list_rosters as tool_list_rosters,
)
from dynasty_mcp.tools.transactions import get_transactions as tool_get_transactions
from dynasty_mcp.tools.values import get_player_values as tool_get_player_values
from dynasty_mcp.tools.waivers import (
    get_free_agents as tool_get_free_agents,
    get_trending as tool_get_trending,
)


def build_server(ctx: Context) -> FastMCP:
    mcp = FastMCP("dynasty-mcp")

    @mcp.tool()
    async def get_league_context() -> Any:
        return (await tool_get_league_context(ctx)).model_dump(mode="json")

    @mcp.tool()
    async def get_roster(team: str | int = "me") -> Any:
        return (await tool_get_roster(ctx, team=team)).model_dump(mode="json")

    @mcp.tool()
    async def list_rosters() -> Any:
        return [r.model_dump(mode="json") for r in await tool_list_rosters(ctx)]

    @mcp.tool()
    async def get_team_value_breakdown(team: str | int = "me") -> Any:
        return (await tool_get_team_value_breakdown(ctx, team=team)).model_dump(mode="json")

    @mcp.tool()
    async def get_player_values(
        position: str | None = None,
        rookies_only: bool = False,
        limit: int = 50,
    ) -> Any:
        rows = await tool_get_player_values(
            ctx, position=position, rookies_only=rookies_only, limit=limit
        )
        return [r.model_dump(mode="json") for r in rows]

    @mcp.tool()
    async def get_matchup(week: int | None = None) -> Any:
        return (await tool_get_matchup(ctx, week=week)).model_dump(mode="json")

    @mcp.tool()
    async def get_free_agents(
        position: str | None = None,
        min_value: int = 0,
        limit: int = 25,
    ) -> Any:
        rows = await tool_get_free_agents(
            ctx, position=position, min_value=min_value, limit=limit
        )
        return [r.model_dump(mode="json") for r in rows]

    @mcp.tool()
    async def get_trending(
        window: Literal["24h", "7d"] = "24h",
        type: Literal["add", "drop"] = "add",
        limit: int = 25,
    ) -> Any:
        rows = await tool_get_trending(ctx, window=window, type=type, limit=limit)
        return [r.model_dump(mode="json") for r in rows]

    @mcp.tool()
    async def get_transactions(
        days: int = 7,
        type: Literal["trade", "waiver", "free_agent"] | None = None,
    ) -> Any:
        return await tool_get_transactions(ctx, days=days, type=type)

    @mcp.tool()
    async def get_draft(year: str | None = None) -> Any:
        return (await tool_get_draft(ctx, year=year)).model_dump(mode="json")

    @mcp.tool()
    async def refresh_cache(
        what: Literal["players", "values", "all"] = "all",
    ) -> Any:
        return (await tool_refresh_cache(ctx, what=what)).model_dump(mode="json")

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

    return mcp
