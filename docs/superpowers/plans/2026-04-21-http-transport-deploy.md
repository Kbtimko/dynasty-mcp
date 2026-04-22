# HTTP Transport + Fly.io Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch dynasty-mcp from stdio to optionally-HTTP transport, containerize it, deploy to Fly.io free tier, and register with claude.ai as a remote MCP server for always-on mobile access.

**Architecture:** Add `[server]` config section + env var overrides so the same binary runs as stdio (local Claude Code) or HTTP (Fly.io). Dockerfile bundles the app; Fly.io secrets inject Sleeper credentials. claude.ai registers the public endpoint as a remote MCP server — no frontend needed.

**Tech Stack:** Python 3.12, FastMCP 3.0+, uvicorn (bundled with FastMCP HTTP), Docker, Fly.io free tier

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `src/dynasty_mcp/config.py` | Modify | Add `transport`, `host`, `port` fields; env var fallbacks; optional config file |
| `src/dynasty_mcp/__main__.py` | Modify | Pass transport/host/port to `server.run()` |
| `tests/test_config.py` | Modify | New tests for server config fields and env var overrides |
| `tests/test_main.py` | Modify | Test HTTP transport wiring |
| `examples/config.toml` | Modify | Document new `[server]` section |
| `Dockerfile` | Create | Containerize the app for Fly.io |
| `fly.toml` | Create | Fly.io deployment config |
| `.dockerignore` | Create | Exclude dev files from image |

---

### Task 1: Extend Config with `[server]` section and env var overrides

**Files:**
- Modify: `src/dynasty_mcp/config.py`
- Modify: `tests/test_config.py`
- Modify: `examples/config.toml`

**Background:** `Config` is a frozen dataclass. `load_config()` reads a TOML file. We need to add three new fields (`transport`, `host`, `port`) parsed from a `[server]` TOML section, with env var overrides for all Sleeper credentials and server settings so Fly.io secrets work without bundling a config file. We also need the default config path to be optional (no file = use env vars only) while keeping the existing "explicit path must exist" behavior.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
import os


def test_server_defaults_when_section_absent(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "alice"\n')
    cfg = load_config(cfg_file)
    assert cfg.transport == "stdio"
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8000


def test_server_section_parsed(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    write_toml(
        cfg_file,
        """
        [sleeper]
        username = "alice"

        [server]
        transport = "http"
        host = "127.0.0.1"
        port = 9000
        """,
    )
    cfg = load_config(cfg_file)
    assert cfg.transport == "http"
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 9000


def test_env_var_overrides_transport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DYNASTY_TRANSPORT", "http")
    monkeypatch.setenv("DYNASTY_HOST", "10.0.0.1")
    monkeypatch.setenv("DYNASTY_PORT", "7777")
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "alice"\n')
    cfg = load_config(cfg_file)
    assert cfg.transport == "http"
    assert cfg.host == "10.0.0.1"
    assert cfg.port == 7777


def test_env_var_overrides_sleeper_username(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLEEPER_USERNAME", "envuser")
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, "[sleeper]\n")  # no username in file
    cfg = load_config(cfg_file)
    assert cfg.sleeper_username == "envuser"


def test_env_var_overrides_sleeper_league_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLEEPER_LEAGUE_ID", "999")
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "alice"\n')
    cfg = load_config(cfg_file)
    assert cfg.sleeper_league_id == "999"


def test_default_path_missing_uses_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("dynasty_mcp.config.DEFAULT_CONFIG_PATH", tmp_path / "missing.toml")
    monkeypatch.setenv("SLEEPER_USERNAME", "envuser")
    cfg = load_config()  # no path arg; file does not exist
    assert cfg.sleeper_username == "envuser"
    assert cfg.transport == "stdio"  # default


def test_invalid_dynasty_port_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DYNASTY_PORT", "not-a-number")
    cfg_file = tmp_path / "config.toml"
    write_toml(cfg_file, '[sleeper]\nusername = "alice"\n')
    with pytest.raises(ConfigError, match="server.port"):
        load_config(cfg_file)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd ~/projects/dynasty-mcp
.venv/bin/pytest tests/test_config.py -v -k "server or env_var or env_var_overrides or dynasty_port or default_path_missing"
```

Expected: FAIL — `Config` has no `transport` field yet.

- [ ] **Step 3: Update the `Config` dataclass**

Replace the `Config` class in `src/dynasty_mcp/config.py`:

```python
@dataclass(frozen=True)
class Config:
    sleeper_username: str
    sleeper_league_id: str | None
    values_source: str
    cache_path: Path
    players_refresh_days: int
    values_refresh_hours: int
    transport: str = "stdio"
    host: str = "0.0.0.0"
    port: int = 8000
```

- [ ] **Step 4: Add `import os` at the top of `config.py`**

Add after the existing imports:

```python
import os
```

- [ ] **Step 5: Rewrite `load_config()` to handle optional file and env vars**

Replace the full `load_config` function:

```python
def load_config(path: Path | None = None) -> Config:
    cfg_path = path or DEFAULT_CONFIG_PATH

    # Explicit path must exist. Default path is optional — env vars can substitute.
    if path is not None and not cfg_path.exists():
        raise ConfigError(f"Config file not found at {cfg_path}")

    raw: dict = {}
    if cfg_path.exists():
        with cfg_path.open("rb") as f:
            raw = tomllib.load(f)

    sleeper = raw.get("sleeper", {})
    username = os.environ.get("SLEEPER_USERNAME") or sleeper.get("username")
    if not username or not str(username).strip():
        raise ConfigError(
            "Missing required field: sleeper.username "
            "(set in config or SLEEPER_USERNAME env var)"
        )

    values = raw.get("values", {})
    cache = raw.get("cache", {})
    server = raw.get("server", {})

    cache_path_raw = cache.get("path")
    cache_path = Path(cache_path_raw).expanduser() if cache_path_raw else _default_cache_path()

    try:
        players_refresh_days = int(cache.get("players_refresh_days", 7))
        values_refresh_hours = int(cache.get("values_refresh_hours", 24))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid cache config value: {exc}") from exc

    transport = os.environ.get("DYNASTY_TRANSPORT") or server.get("transport", "stdio")
    host = os.environ.get("DYNASTY_HOST") or server.get("host", "0.0.0.0")
    try:
        port = int(os.environ.get("DYNASTY_PORT") or server.get("port", 8000))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid server.port: {exc}") from exc

    return Config(
        sleeper_username=str(username).strip(),
        sleeper_league_id=os.environ.get("SLEEPER_LEAGUE_ID") or sleeper.get("league_id"),
        values_source=values.get("source", "fantasycalc"),
        cache_path=cache_path,
        players_refresh_days=players_refresh_days,
        values_refresh_hours=values_refresh_hours,
        transport=transport,
        host=host,
        port=port,
    )
```

- [ ] **Step 6: Run the new tests to confirm they pass**

```bash
.venv/bin/pytest tests/test_config.py -v
```

Expected: All tests pass including the 7 new ones.

- [ ] **Step 7: Update `examples/config.toml` with the new section**

Add to the end of `examples/config.toml`:

```toml
# [server] section controls transport mode.
# Omit (or set transport = "stdio") for local Claude Code use.
# Set transport = "http" for deployed/remote use (e.g. Fly.io).
# All values can also be set via env vars: DYNASTY_TRANSPORT, DYNASTY_HOST, DYNASTY_PORT
# Sleeper credentials can be set via env vars too: SLEEPER_USERNAME, SLEEPER_LEAGUE_ID
[server]
# transport = "stdio"   # default — use for local Claude Code
# transport = "http"    # use for Fly.io / remote deployment
# host = "0.0.0.0"
# port = 8000
```

- [ ] **Step 8: Commit**

```bash
git add src/dynasty_mcp/config.py tests/test_config.py examples/config.toml
git commit -m "feat: add server transport config with env var overrides"
```

---

### Task 2: Wire transport settings in `__main__.py`

**Files:**
- Modify: `src/dynasty_mcp/__main__.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_main.py`:

```python
from unittest.mock import MagicMock, patch


def test_http_transport_calls_run_with_args(tmp_path: Path) -> None:
    """When transport=http, server.run() receives transport/host/port."""
    from dynasty_mcp.__main__ import main
    from dynasty_mcp.config import DEFAULT_CONFIG_PATH

    cfg_toml = '[sleeper]\nusername = "dakeif"\nleague_id = "123"\n[server]\ntransport = "http"\nhost = "0.0.0.0"\nport = 8000\n'
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(cfg_toml)

    mock_server = MagicMock()
    mock_state = {"season": "2025"}

    with (
        patch("dynasty_mcp.__main__.load_config", return_value=__import__("dynasty_mcp.config", fromlist=["Config"]).Config(
            sleeper_username="dakeif",
            sleeper_league_id="123",
            values_source="fantasycalc",
            cache_path=tmp_path / "cache.db",
            players_refresh_days=7,
            values_refresh_hours=24,
            transport="http",
            host="0.0.0.0",
            port=8000,
        )),
        patch("dynasty_mcp.__main__.Cache"),
        patch("dynasty_mcp.__main__.SleeperClient") as mock_sleeper_cls,
        patch("dynasty_mcp.__main__.FantasyCalcClient"),
        patch("dynasty_mcp.__main__.build_server", return_value=mock_server),
    ):
        mock_sleeper = mock_sleeper_cls.return_value
        mock_sleeper.get_state = MagicMock(return_value=mock_state)
        import asyncio
        with patch("asyncio.run", side_effect=lambda coro: mock_state if "get_state" in str(coro) else "123"):
            main()

    mock_server.run.assert_called_once_with(transport="http", host="0.0.0.0", port=8000)


def test_stdio_transport_calls_run_no_args(tmp_path: Path) -> None:
    """When transport=stdio, server.run() is called with no args."""
    from dynasty_mcp.__main__ import main

    mock_server = MagicMock()
    mock_state = {"season": "2025"}

    with (
        patch("dynasty_mcp.__main__.load_config", return_value=__import__("dynasty_mcp.config", fromlist=["Config"]).Config(
            sleeper_username="dakeif",
            sleeper_league_id="123",
            values_source="fantasycalc",
            cache_path=tmp_path / "cache.db",
            players_refresh_days=7,
            values_refresh_hours=24,
            transport="stdio",
            host="0.0.0.0",
            port=8000,
        )),
        patch("dynasty_mcp.__main__.Cache"),
        patch("dynasty_mcp.__main__.SleeperClient") as mock_sleeper_cls,
        patch("dynasty_mcp.__main__.FantasyCalcClient"),
        patch("dynasty_mcp.__main__.build_server", return_value=mock_server),
    ):
        mock_sleeper = mock_sleeper_cls.return_value
        with patch("asyncio.run", return_value=mock_state):
            main()

    mock_server.run.assert_called_once_with()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
.venv/bin/pytest tests/test_main.py -v -k "transport"
```

Expected: FAIL — `main()` always calls `server.run()` with no args.

- [ ] **Step 3: Update `main()` to pass transport settings**

Replace the `server.run()` call at the end of `main()` in `src/dynasty_mcp/__main__.py`:

```python
    server = build_server(ctx)
    if config.transport == "stdio":
        server.run()
    else:
        server.run(transport=config.transport, host=config.host, port=config.port)
```

- [ ] **Step 4: Run all tests**

```bash
.venv/bin/pytest -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dynasty_mcp/__main__.py tests/test_main.py
git commit -m "feat: wire transport/host/port from config to server.run()"
```

---

### Task 3: Dockerfile

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

The image only needs the package source and `pyproject.toml`. The config file is intentionally excluded — credentials come from Fly.io secrets (env vars) at runtime.

- [ ] **Step 1: Create `.dockerignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
tests/
docs/
examples/
*.md
.git/
.gitignore
```

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["dynasty-mcp"]
```

- [ ] **Step 3: Build and smoke-test the image locally**

```bash
docker build -t dynasty-mcp .
docker run --rm \
  -e SLEEPER_USERNAME=dakeif \
  -e SLEEPER_LEAGUE_ID=1335327387256119296 \
  -e DYNASTY_TRANSPORT=http \
  -e DYNASTY_PORT=8000 \
  -p 8000:8000 \
  dynasty-mcp
```

Expected: Server starts and logs `Running on http://0.0.0.0:8000` (or similar uvicorn output). Ctrl-C to stop.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "chore: add Dockerfile for Fly.io deployment"
```

---

### Task 4: fly.toml + Fly.io deployment

**Files:**
- Create: `fly.toml`

**Prerequisite:** Install the Fly CLI if not present: `brew install flyctl` then `fly auth login`.

- [ ] **Step 1: Create `fly.toml`**

```toml
app = "dynasty-mcp"
primary_region = "ord"

[build]

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0
  processes = ["app"]

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"
```

Note: `auto_stop_machines = true` keeps the free tier within limits — the machine spins down when idle and starts on request (cold start ~2–3 seconds).

- [ ] **Step 2: Launch the app on Fly.io (first time only)**

```bash
fly launch --no-deploy --name dynasty-mcp --region ord
```

When prompted, say **no** to creating a Postgres database and **no** to creating a Redis instance. Accept the generated `fly.toml` or use the one above.

- [ ] **Step 3: Set Fly.io secrets**

```bash
fly secrets set \
  SLEEPER_USERNAME=dakeif \
  SLEEPER_LEAGUE_ID=1335327387256119296 \
  DYNASTY_TRANSPORT=http \
  DYNASTY_PORT=8000
```

- [ ] **Step 4: Deploy**

```bash
fly deploy
```

Expected output ends with `Visit your newly deployed app at https://dynasty-mcp.fly.dev` (or similar).

- [ ] **Step 5: Verify the server is reachable**

```bash
curl https://dynasty-mcp.fly.dev/
```

FastMCP's HTTP transport serves the MCP protocol at `/mcp` by default. You can also check:

```bash
curl https://dynasty-mcp.fly.dev/mcp
```

Expected: A JSON response or an MCP protocol message (not a 404 or connection error).

- [ ] **Step 6: Commit `fly.toml`**

```bash
git add fly.toml
git commit -m "chore: add fly.toml for Fly.io deployment"
```

---

### Task 5: Register with claude.ai and smoke-test

This task is entirely manual — no code changes.

- [ ] **Step 1: Open claude.ai settings**

Go to [claude.ai](https://claude.ai) → Settings → Integrations (or "MCP Servers" / "Connections" — the label may vary).

- [ ] **Step 2: Add a new MCP server**

- Name: `dynasty-mcp`
- URL: `https://dynasty-mcp.fly.dev/mcp`
- Transport: Streamable HTTP (or HTTP, depending on the UI options)

Save the integration.

- [ ] **Step 3: Smoke-test all 12 tools from claude.ai on a mobile device**

Open a new claude.ai conversation on your phone. Try:

```
Use the dynasty-mcp tools to show me my current roster and total value.
```

Verify Claude calls `get_roster` and returns real data.

```
Run the reset optimizer for my team and show me the top 3 protection slates.
```

Verify Claude calls `reset_optimizer` and returns real slate options.

- [ ] **Step 4: Update NOTES.md**

Add a session note to `NOTES.md` confirming deployment is live and the Fly.io URL.

---

## Self-Review

**Spec coverage:**
- ✅ transport/host/port in Config → Task 1
- ✅ env var overrides for Fly.io secrets → Task 1
- ✅ server.run() wiring → Task 2
- ✅ Dockerfile → Task 3
- ✅ Fly.io deployment → Task 4
- ✅ claude.ai registration → Task 5

**No placeholders found.**

**Type consistency:** `Config.transport: str`, `Config.host: str`, `Config.port: int` — used consistently across Task 1 and Task 2.

**Scope note:** The SQLite cache will not persist across Fly.io deploys (ephemeral container filesystem). This is intentional — the cache is a performance optimization only; all data re-fetches automatically when stale. No action required.
