# scripts/record_fixtures.py
"""Record live API responses to tests/fixtures/ for replay-based testing.

Usage:
    SLEEPER_USERNAME=... SLEEPER_LEAGUE_ID=... .venv/bin/python scripts/record_fixtures.py

Re-run quarterly, after NFL season transitions, or when API shapes change.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
SLEEPER = "https://api.sleeper.app/v1"
FANTASYCALC = "https://api.fantasycalc.com/values/current"


def save(name: str, data: object) -> None:
    path = FIXTURES / name
    path.write_text(json.dumps(data, indent=2, sort_keys=True))
    print(f"wrote {path}")


def main() -> None:
    username = os.environ.get("SLEEPER_USERNAME")
    league_id = os.environ.get("SLEEPER_LEAGUE_ID")
    if not username or not league_id:
        print("Set SLEEPER_USERNAME and SLEEPER_LEAGUE_ID", file=sys.stderr)
        sys.exit(2)

    season = os.environ.get("SEASON", "2025")
    week = os.environ.get("WEEK", "7")

    with httpx.Client(timeout=30) as c:
        state = c.get(f"{SLEEPER}/state/nfl").json()
        save("sleeper_state.json", state)

        user = c.get(f"{SLEEPER}/user/{username}").json()
        save("sleeper_user.json", user)

        leagues = c.get(
            f"{SLEEPER}/user/{user['user_id']}/leagues/nfl/{season}"
        ).json()
        save("sleeper_user_leagues.json", leagues)

        save("sleeper_league.json", c.get(f"{SLEEPER}/league/{league_id}").json())
        save("sleeper_rosters.json", c.get(f"{SLEEPER}/league/{league_id}/rosters").json())
        save("sleeper_users.json", c.get(f"{SLEEPER}/league/{league_id}/users").json())
        save(
            f"sleeper_matchups_week{week}.json",
            c.get(f"{SLEEPER}/league/{league_id}/matchups/{week}").json(),
        )
        save(
            f"sleeper_transactions_week{week}.json",
            c.get(f"{SLEEPER}/league/{league_id}/transactions/{week}").json(),
        )
        save(
            "sleeper_traded_picks.json",
            c.get(f"{SLEEPER}/league/{league_id}/traded_picks").json(),
        )
        drafts = c.get(f"{SLEEPER}/league/{league_id}/drafts").json()
        save("sleeper_drafts.json", drafts)
        if drafts:
            draft_id = drafts[0]["draft_id"]
            save("sleeper_draft.json", c.get(f"{SLEEPER}/draft/{draft_id}").json())
            save(
                "sleeper_draft_picks.json",
                c.get(f"{SLEEPER}/draft/{draft_id}/picks").json(),
            )
        save(
            "sleeper_trending_add.json",
            c.get(
                f"{SLEEPER}/players/nfl/trending/add",
                params={"lookback_hours": 24, "limit": 25},
            ).json(),
        )

        # Trim the full players dataset to players that appear in this league's
        # rosters, the trending list, and the draft — keeps the fixture small.
        rosters = json.loads((FIXTURES / "sleeper_rosters.json").read_text())
        trending = json.loads((FIXTURES / "sleeper_trending_add.json").read_text())
        draft_picks = json.loads((FIXTURES / "sleeper_draft_picks.json").read_text())
        keep_ids: set[str] = set()
        for r in rosters:
            keep_ids.update(r.get("players") or [])
            keep_ids.update(r.get("taxi") or [])
            keep_ids.update(r.get("reserve") or [])
        keep_ids.update(t["player_id"] for t in trending)
        keep_ids.update(p.get("player_id") for p in draft_picks if p.get("player_id"))
        all_players = c.get(f"{SLEEPER}/players/nfl").json()
        trimmed = {pid: all_players[pid] for pid in keep_ids if pid in all_players}
        save("sleeper_players.json", trimmed)

        # FantasyCalc — params derived from league later, but record one shape now.
        league = json.loads((FIXTURES / "sleeper_league.json").read_text())
        num_qbs = 2 if "SUPER_FLEX" in (league.get("roster_positions") or []) else 1
        num_teams = league.get("total_rosters", 12)
        ppr = float((league.get("scoring_settings") or {}).get("rec", 1.0))
        fc = c.get(
            FANTASYCALC,
            params={
                "isDynasty": "true",
                "numQbs": num_qbs,
                "numTeams": num_teams,
                "ppr": ppr,
            },
        ).json()
        save("fantasycalc_values.json", fc)


if __name__ == "__main__":
    main()
