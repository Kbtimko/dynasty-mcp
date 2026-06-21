# Project: dynasty-mcp

## Goal
Local MCP server giving Claude access to Keith's Sleeper dynasty FF league via 11 tools. In maintenance mode — active development moved to dynasty-app.

## Current Status
Feature-complete and deployed to Fly.io (`dynasty-mcp.fly.dev/mcp`). All 11 tools shipped including `reset_optimizer` and `reset_trades`. Awaiting dynasty-app Phase 1 verification on Vercel before shutting down the Fly.io instance.

## Blockers
- [ ] Fly.io instance still running (incurring cost) — destroy with `fly apps destroy dynasty-mcp` once dynasty-app is confirmed working on Vercel (identified: 2026-04-22)

## In Progress
- Nothing — maintenance mode

## Prioritized Backlog
<!-- Risk tiers: [auto] runner may build→test→PR unattended · [review] needs spec/plan approval · [human] you drive. See ~/projects/CLAUDE.md → Backlog Risk Tiers. -->
1. `[human]` Destroy Fly.io instance after dynasty-app Vercel smoke test passes _(irreversible: destroys a deployed service + depends on your live smoke-test sign-off)_
2. `[review]` League-scoring-adjusted values (deferred; candidate for dynasty-app Phase 2) _(deferred net-new modeling — needs a spec, likely lands in dynasty-app)_

## Completed
<!-- Tags below are retrospective/illustrative — runner skips done items regardless. -->
- `[review]` ~~All 11 tools (reset_optimizer, reset_trades, context, roster, etc.)~~ (2026-04-22)
- `[human]` ~~HTTP transport + Fly.io deploy (PR #3)~~ (2026-04-22)
- `[human]` ~~Bumped Fly.io VM to 512 MB (prevent OOM kills)~~ (2026-04-22)
- `[auto]` ~~ConfigError for unknown Sleeper username~~ (2026-04-22)
