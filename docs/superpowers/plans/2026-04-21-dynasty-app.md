# Dynasty App Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy Phase 1 of `dynasty-app` — a Next.js 16 web app that exposes Dynasty fantasy tools (Dashboard, Reset Optimizer, Reset Trades, Team Value Breakdown) with Supabase caching and Claude AI summaries.

**Architecture:** Next.js App Router Server Actions fetch Sleeper/FantasyCalc data, check/write a Supabase cache, run TypeScript-ported tool logic, call Claude for a 2–4 sentence summary, and render a structured data page with AI summary card at the top.

**Tech Stack:** Next.js 16 · React 19 · TypeScript · Tailwind 4 · `@supabase/supabase-js` · `@anthropic-ai/sdk` · Vitest

---

## File Map

```
~/projects/dynasty-app/
├── app/
│   ├── layout.tsx                  # Root layout — sidebar nav
│   ├── page.tsx                    # Dashboard
│   ├── reset-optimizer/page.tsx
│   ├── reset-trades/page.tsx
│   └── team-value/page.tsx
├── components/
│   ├── Nav.tsx                     # Sidebar nav links
│   ├── AiSummary.tsx               # AI summary card
│   └── RefreshButton.tsx           # Client component — appends ?t= to URL
├── lib/
│   ├── types.ts                    # All shared TypeScript types
│   ├── utils.ts                    # combinations() generator
│   ├── supabase.ts                 # Supabase singleton client
│   ├── cache.ts                    # Supabase-backed cache helpers
│   ├── sleeper.ts                  # Sleeper API client
│   ├── fantasycalc.ts              # FantasyCalc client + deriveParams
│   ├── context.ts                  # Ctx type + getCtx() from env vars
│   ├── ai.ts                       # generateSummary() via Anthropic SDK
│   ├── reset-scoring.ts            # Pure reset math (port of reset_scoring.py)
│   └── tools/
│       ├── rosters.ts              # getRoster, listRosters, getTeamValueBreakdown
│       ├── reset-optimizer.ts      # resetOptimizer
│       └── reset-trades.ts         # resetTrades + all helpers
├── lib/__tests__/
│   ├── reset-scoring.test.ts
│   ├── cache.test.ts
│   ├── sleeper.test.ts
│   └── fantasycalc.test.ts
├── supabase-schema.sql             # Run once in Supabase SQL editor
├── vitest.config.ts
├── vitest.setup.ts
└── .env.local                      # Never committed
```

---

## Task 1: Scaffold

**Files:**
- Create: `~/projects/dynasty-app/` (new repo)
- Create: `vitest.config.ts`, `vitest.setup.ts`, `.env.local`

- [ ] **Step 1: Create Next.js app**

```bash
cd ~/projects
npx create-next-app@latest dynasty-app \
  --typescript --tailwind --app --no-src-dir \
  --import-alias "@/*" --no-eslint
cd dynasty-app
```

- [ ] **Step 2: Install dependencies**

```bash
npm install @supabase/supabase-js @anthropic-ai/sdk
npm install -D vitest @vitejs/plugin-react jsdom \
  @testing-library/react @testing-library/jest-dom
```

- [ ] **Step 3: Write vitest.config.ts**

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    globals: true,
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
});
```

- [ ] **Step 4: Write vitest.setup.ts**

```typescript
// vitest.setup.ts
import '@testing-library/jest-dom';
```

- [ ] **Step 5: Add test script to package.json**

In `package.json`, add under `"scripts"`:
```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 6: Create .env.local**

```bash
cat > .env.local << 'EOF'
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
ANTHROPIC_API_KEY=your_anthropic_key
SLEEPER_USERNAME=dakeif
SLEEPER_LEAGUE_ID=1335327387256119296
EOF
```
Fill in actual values from Supabase dashboard and Anthropic console.

- [ ] **Step 7: Verify scaffold**

```bash
npm run dev
```
Expected: server starts on http://localhost:3000, default Next.js page loads.

- [ ] **Step 8: Init git + first commit**

```bash
git init
git add -A
git commit -m "chore: scaffold dynasty-app"
```

---

## Task 2: Types (`lib/types.ts`)

**Files:**
- Create: `lib/types.ts`

No tests needed — pure type definitions, verified by TypeScript compiler.

- [ ] **Step 1: Write lib/types.ts**

```typescript
// lib/types.ts

export type SlotType = 'active' | 'bench' | 'taxi' | 'ir';
export type ProtectionSlot = 'qb' | 'rb_te' | 'wr_te' | 'taxi';
export type SeasonPhase = 'pre' | 'regular' | 'post' | 'offseason';

export interface Player {
  playerId: string;
  fullName: string;
  position: string;
  team?: string;
  age?: number;
  status?: string;
}

export interface Value {
  current: number | null;
  delta7d?: number;
  delta30d?: number;
}

export interface RosterEntry {
  player: Player;
  slotType: SlotType;
  value: Value;
  starter: boolean;
  projection?: number;
}

export interface RosterView {
  rosterId: number;
  ownerUsername: string;
  ownerDisplayName?: string;
  entries: RosterEntry[];
  totalValueActive: number;
  totalValueTaxi: number;
  totalValueIr: number;
}

export interface RosterSummary {
  rosterId: number;
  ownerUsername: string;
  totalValue: number;
  topAssets: string[];
}

export interface TeamValueBreakdown {
  rosterId: number;
  byPosition: Record<string, number>;
  byAgeCohort: { under_25: number; '25_28': number; '29_plus': number; unknown: number };
  taxiStashValue: number;
  irValue: number;
  activeValue: number;
}

export interface ProtectionSlate {
  qb: RosterEntry;
  rbTe: RosterEntry;
  wrTe: RosterEntry;
  taxi: RosterEntry[];
  protectedValue: number;
}

export interface Swap {
  slot: ProtectionSlot;
  fromPlayer: string;
  toPlayer: string;
  valueDelta: number;
}

export interface SlateOption {
  rank: number;
  protected: ProtectionSlate;
  protectedValue: number;
  valueAtRisk: number;
  swapsFromTop: Swap[];
}

export interface ResetOptimizerResult {
  rosterId: number;
  ownerUsername: string;
  resetProbability: number;
  totalRosterValue: number;
  options: SlateOption[];
  taxiPoolSize: number;
  notes: string[];
}

export interface TradeAsset {
  kind: 'player' | 'pick';
  assetId: string;
  displayName: string;
  rawValue: number;
  resetAdjustedValue: number;
  protectableOnReceiver: boolean;
}

export interface TradeProposal {
  rank: number;
  partnerRosterId: number;
  partnerUsername: string;
  mySend: TradeAsset[];
  myRecv: TradeAsset[];
  myNetEdge: number;
  partnerNetEdge: number;
  rationaleFlags: string[];
}

export interface ResetTradeFinderResult {
  resetProbability: number;
  proposals: TradeProposal[];
  consideredPartners: number[];
  notes: string[];
}
```

- [ ] **Step 2: Typecheck**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add lib/types.ts
git commit -m "feat: add TypeScript types (port of models.py)"
```

---

## Task 3: Supabase schema + cache (`lib/supabase.ts`, `lib/cache.ts`)

**Files:**
- Create: `supabase-schema.sql`
- Create: `lib/supabase.ts`
- Create: `lib/cache.ts`
- Create: `lib/__tests__/cache.test.ts`

- [ ] **Step 1: Write supabase-schema.sql**

```sql
-- supabase-schema.sql
-- Run once in the Supabase SQL editor for the dynasty-app project.

create table if not exists players (
  id integer primary key default 1 check (id = 1),
  data jsonb not null,
  updated_at timestamptz not null
);

create table if not exists values_snapshots (
  id bigserial primary key,
  data jsonb not null,
  updated_at timestamptz not null
);

create table if not exists league_snapshot (
  id bigserial primary key,
  league_id text not null,
  week integer not null,
  data jsonb not null,
  updated_at timestamptz not null,
  unique (league_id, week)
);

create table if not exists http_cache (
  url text primary key,
  body text not null,
  updated_at timestamptz not null
);
```

Run this in the Supabase SQL editor before proceeding.

- [ ] **Step 2: Write lib/supabase.ts**

```typescript
// lib/supabase.ts
import { createClient } from '@supabase/supabase-js';

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);
```

- [ ] **Step 3: Write failing test**

```typescript
// lib/__tests__/cache.test.ts
import { vi, describe, it, expect, beforeEach } from 'vitest';

const mockSingle = vi.fn();
const mockEq = vi.fn(() => ({ single: mockSingle }));
const mockSelect = vi.fn(() => ({ eq: mockEq }));
const mockUpsert = vi.fn();
const mockInsert = vi.fn();
const mockOrder = vi.fn();
const mockLimit = vi.fn();

vi.mock('@/lib/supabase', () => ({
  supabase: {
    from: vi.fn((table: string) => {
      if (table === 'players') return { select: mockSelect, upsert: mockUpsert };
      if (table === 'values_snapshots') return { insert: mockInsert, select: { order: mockOrder } };
      return {};
    }),
  },
}));

import { getPlayers, putPlayers, isPlayersStale, getLatestValues, putValuesSnapshot, isValuesStale } from '@/lib/cache';

describe('getPlayers', () => {
  beforeEach(() => vi.clearAllMocks());

  it('returns null when no row exists', async () => {
    mockSingle.mockResolvedValue({ data: null, error: null });
    const result = await getPlayers();
    expect(result).toEqual({ data: null, updatedAt: null });
  });

  it('returns parsed data and date when row exists', async () => {
    mockSingle.mockResolvedValue({
      data: { data: { '123': { full_name: 'Test' } }, updated_at: '2026-04-21T00:00:00Z' },
      error: null,
    });
    const result = await getPlayers();
    expect(result.data).toEqual({ '123': { full_name: 'Test' } });
    expect(result.updatedAt).toBeInstanceOf(Date);
  });
});

describe('isPlayersStale', () => {
  it('returns true when updatedAt is null', () => {
    expect(isPlayersStale(null)).toBe(true);
  });

  it('returns false when updated less than refreshDays ago', () => {
    expect(isPlayersStale(new Date(), 1)).toBe(false);
  });

  it('returns true when updated more than refreshDays ago', () => {
    const old = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000);
    expect(isPlayersStale(old, 1)).toBe(true);
  });
});
```

- [ ] **Step 4: Run test to confirm it fails**

```bash
npm test -- lib/__tests__/cache.test.ts
```
Expected: FAIL — `Cannot find module '@/lib/cache'`

- [ ] **Step 5: Write lib/cache.ts**

```typescript
// lib/cache.ts
import { supabase } from './supabase';

export async function getPlayers(): Promise<{ data: Record<string, unknown> | null; updatedAt: Date | null }> {
  const { data: row } = await supabase
    .from('players')
    .select('data, updated_at')
    .eq('id', 1)
    .single();
  if (!row) return { data: null, updatedAt: null };
  return { data: row.data as Record<string, unknown>, updatedAt: new Date(row.updated_at) };
}

export async function putPlayers(data: Record<string, unknown>): Promise<void> {
  await supabase.from('players').upsert({ id: 1, data, updated_at: new Date().toISOString() });
}

export function isPlayersStale(updatedAt: Date | null, refreshDays = 1): boolean {
  if (!updatedAt) return true;
  return Date.now() - updatedAt.getTime() > refreshDays * 24 * 60 * 60 * 1000;
}

export async function getLatestValues(): Promise<{ data: unknown[] | null; updatedAt: Date | null }> {
  const { data: rows } = await supabase
    .from('values_snapshots')
    .select('data, updated_at')
    .order('id', { ascending: false })
    .limit(1);
  if (!rows?.length) return { data: null, updatedAt: null };
  return { data: rows[0].data as unknown[], updatedAt: new Date(rows[0].updated_at) };
}

export async function putValuesSnapshot(data: unknown[]): Promise<void> {
  await supabase.from('values_snapshots').insert({ data, updated_at: new Date().toISOString() });
}

export function isValuesStale(updatedAt: Date | null, refreshHours = 6): boolean {
  if (!updatedAt) return true;
  return Date.now() - updatedAt.getTime() > refreshHours * 60 * 60 * 1000;
}
```

- [ ] **Step 6: Run tests and confirm pass**

```bash
npm test -- lib/__tests__/cache.test.ts
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add supabase-schema.sql lib/supabase.ts lib/cache.ts lib/__tests__/cache.test.ts
git commit -m "feat: add Supabase cache layer"
```

---

## Task 4: Sleeper client (`lib/sleeper.ts`)

**Files:**
- Create: `lib/sleeper.ts`
- Create: `lib/__tests__/sleeper.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// lib/__tests__/sleeper.test.ts
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { getState, getUser, getLeague, getRosters, getLeagueUsers, getPlayers as sleeperGetPlayers } from '@/lib/sleeper';
import * as cache from '@/lib/cache';

vi.mock('@/lib/cache');

describe('getState', () => {
  beforeEach(() => vi.clearAllMocks());

  it('returns json on 200', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ week: 7, season: '2025' }),
    } as unknown as Response);

    const result = await getState();
    expect(result).toEqual({ week: 7, season: '2025' });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/state/nfl'),
      expect.any(Object)
    );
  });

  it('retries once on 503 then succeeds', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 503 } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ week: 7 }),
      } as unknown as Response);

    const result = await getState();
    expect(result).toEqual({ week: 7 });
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('throws on non-transient 404', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 } as unknown as Response);
    await expect(getState()).rejects.toThrow('404');
  });
});

describe('sleeperGetPlayers (cache-aware)', () => {
  it('returns cache when fresh', async () => {
    vi.mocked(cache.getPlayers).mockResolvedValue({
      data: { '123': { full_name: 'Test' } },
      updatedAt: new Date(),
    });
    vi.mocked(cache.isPlayersStale).mockReturnValue(false);

    const result = await sleeperGetPlayers();
    expect(result['123']).toEqual({ full_name: 'Test' });
    expect(fetch).not.toHaveBeenCalled();
  });

  it('fetches and caches when stale', async () => {
    vi.mocked(cache.getPlayers).mockResolvedValue({ data: null, updatedAt: null });
    vi.mocked(cache.isPlayersStale).mockReturnValue(true);
    vi.mocked(cache.putPlayers).mockResolvedValue(undefined);
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ '456': { full_name: 'Fresh' } }),
    } as unknown as Response);

    const result = await sleeperGetPlayers();
    expect(result['456']).toEqual({ full_name: 'Fresh' });
    expect(cache.putPlayers).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
npm test -- lib/__tests__/sleeper.test.ts
```
Expected: FAIL — `Cannot find module '@/lib/sleeper'`

- [ ] **Step 3: Write lib/sleeper.ts**

```typescript
// lib/sleeper.ts
import { getPlayers as cacheGetPlayers, isPlayersStale, putPlayers } from './cache';

const BASE = 'https://api.sleeper.app/v1';
const TRANSIENT = new Set([408, 429, 500, 502, 503, 504]);

async function sleeperFetch<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(BASE + path);
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));

  const doFetch = () => fetch(url.toString(), { cache: 'no-store' });
  let res = await doFetch();
  if (!res.ok && TRANSIENT.has(res.status)) {
    await new Promise(r => setTimeout(r, 1000));
    res = await doFetch();
  }
  if (!res.ok) throw new Error(`Sleeper ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export const getState = () => sleeperFetch<Record<string, unknown>>('/state/nfl');
export const getUser = (usernameOrId: string) => sleeperFetch<Record<string, unknown>>(`/user/${usernameOrId}`);
export const getUserLeagues = (userId: string, season: string) => sleeperFetch<unknown[]>(`/user/${userId}/leagues/nfl/${season}`);
export const getLeague = (leagueId: string) => sleeperFetch<Record<string, unknown>>(`/league/${leagueId}`);
export const getRosters = (leagueId: string) => sleeperFetch<Record<string, unknown>[]>(`/league/${leagueId}/rosters`);
export const getLeagueUsers = (leagueId: string) => sleeperFetch<Record<string, unknown>[]>(`/league/${leagueId}/users`);
export const getMatchups = (leagueId: string, week: number) => sleeperFetch<unknown[]>(`/league/${leagueId}/matchups/${week}`);
export const getTransactions = (leagueId: string, week: number) => sleeperFetch<unknown[]>(`/league/${leagueId}/transactions/${week}`);
export const getTradedPicks = (leagueId: string) => sleeperFetch<Record<string, unknown>[]>(`/league/${leagueId}/traded_picks`);
export const getDrafts = (leagueId: string) => sleeperFetch<unknown[]>(`/league/${leagueId}/drafts`);
export const getDraft = (draftId: string) => sleeperFetch<Record<string, unknown>>(`/draft/${draftId}`);
export const getDraftPicks = (draftId: string) => sleeperFetch<unknown[]>(`/draft/${draftId}/picks`);
export const getTrending = (kind: string, lookbackHours = 24, limit = 25) =>
  sleeperFetch<Record<string, unknown>[]>(`/players/nfl/trending/${kind}`, {
    lookback_hours: String(lookbackHours),
    limit: String(limit),
  });

export async function getPlayers(force = false): Promise<Record<string, unknown>> {
  const { data: cached, updatedAt } = await cacheGetPlayers();
  if (cached && !force && !isPlayersStale(updatedAt)) return cached;
  try {
    const data = await sleeperFetch<Record<string, unknown>>('/players/nfl');
    await putPlayers(data);
    return data;
  } catch {
    if (cached) return cached;
    throw new Error('Sleeper /players/nfl failed and no cache available');
  }
}
```

- [ ] **Step 4: Run tests and confirm pass**

```bash
npm test -- lib/__tests__/sleeper.test.ts
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/sleeper.ts lib/__tests__/sleeper.test.ts
git commit -m "feat: add Sleeper API client"
```

---

## Task 5: FantasyCalc client (`lib/fantasycalc.ts`)

**Files:**
- Create: `lib/fantasycalc.ts`
- Create: `lib/__tests__/fantasycalc.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// lib/__tests__/fantasycalc.test.ts
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { deriveParams, getFantasyCalcValues } from '@/lib/fantasycalc';
import * as cache from '@/lib/cache';

vi.mock('@/lib/cache');

describe('deriveParams', () => {
  it('detects superflex from SUPER_FLEX in roster_positions', () => {
    const league = { roster_positions: ['QB', 'SUPER_FLEX', 'RB', 'WR'], total_rosters: 14, scoring_settings: { rec: 0.5 } };
    expect(deriveParams(league)).toEqual({ isDynasty: 'true', numQbs: 2, numTeams: 14, ppr: 0.5 });
  });

  it('defaults to 1 QB when no SUPER_FLEX', () => {
    const league = { roster_positions: ['QB', 'RB', 'WR'], total_rosters: 12, scoring_settings: { rec: 1.0 } };
    expect(deriveParams(league)).toMatchObject({ numQbs: 1 });
  });
});

describe('getFantasyCalcValues', () => {
  beforeEach(() => vi.clearAllMocks());

  it('returns cache when fresh', async () => {
    vi.mocked(cache.getLatestValues).mockResolvedValue({ data: [{ value: 1000 }], updatedAt: new Date() });
    vi.mocked(cache.isValuesStale).mockReturnValue(false);

    const result = await getFantasyCalcValues({ roster_positions: [], total_rosters: 12, scoring_settings: { rec: 0.5 } });
    expect(result).toEqual([{ value: 1000 }]);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('fetches and caches when stale', async () => {
    vi.mocked(cache.getLatestValues).mockResolvedValue({ data: null, updatedAt: null });
    vi.mocked(cache.isValuesStale).mockReturnValue(true);
    vi.mocked(cache.putValuesSnapshot).mockResolvedValue(undefined);
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve([{ player: { sleeperId: '123' }, value: 5000 }]),
    } as unknown as Response);

    const result = await getFantasyCalcValues({ roster_positions: ['QB', 'SUPER_FLEX'], total_rosters: 14, scoring_settings: { rec: 0.5 } });
    expect(result[0]).toMatchObject({ value: 5000 });
    expect(cache.putValuesSnapshot).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
npm test -- lib/__tests__/fantasycalc.test.ts
```
Expected: FAIL.

- [ ] **Step 3: Write lib/fantasycalc.ts**

```typescript
// lib/fantasycalc.ts
import { getLatestValues, isValuesStale, putValuesSnapshot } from './cache';

const BASE = 'https://api.fantasycalc.com';

export function deriveParams(league: Record<string, unknown>): Record<string, string | number> {
  const positions = (league.roster_positions as string[]) ?? [];
  const numQbs = positions.includes('SUPER_FLEX') ? 2 : 1;
  const numTeams = (league.total_rosters as number) ?? 12;
  const scoring = (league.scoring_settings as Record<string, number>) ?? {};
  const ppr = scoring.rec ?? 1.0;
  return { isDynasty: 'true', numQbs, numTeams, ppr };
}

export async function getFantasyCalcValues(
  league: Record<string, unknown>,
  force = false
): Promise<Record<string, unknown>[]> {
  const { data: cached, updatedAt } = await getLatestValues();
  if (cached && !force && !isValuesStale(updatedAt)) return cached as Record<string, unknown>[];

  const params = deriveParams(league);
  const url = new URL(`${BASE}/values/current`);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
  const res = await fetch(url.toString(), { cache: 'no-store' });
  if (!res.ok) throw new Error(`FantasyCalc /values/current: ${res.status}`);
  const data = await res.json() as Record<string, unknown>[];
  await putValuesSnapshot(data);
  return data;
}
```

- [ ] **Step 4: Run tests and confirm pass**

```bash
npm test -- lib/__tests__/fantasycalc.test.ts
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/fantasycalc.ts lib/__tests__/fantasycalc.test.ts
git commit -m "feat: add FantasyCalc client"
```

---

## Task 6: Combinations util + reset scoring (`lib/utils.ts`, `lib/reset-scoring.ts`)

**Files:**
- Create: `lib/utils.ts`
- Create: `lib/reset-scoring.ts`
- Create: `lib/__tests__/reset-scoring.test.ts`

- [ ] **Step 1: Write failing tests**

```typescript
// lib/__tests__/reset-scoring.test.ts
import { describe, it, expect } from 'vitest';
import { rankSlates, valueAtRisk, pickValueUnderReset, assetValueUnderReset } from '@/lib/reset-scoring';
import type { RosterEntry } from '@/lib/types';

function entry(playerId: string, position: string, value: number, slotType: RosterEntry['slotType'] = 'active'): RosterEntry {
  return { player: { playerId, fullName: playerId, position, team: 'KC' }, slotType, value: { current: value }, starter: true };
}

const QB1 = entry('QB1', 'QB', 8000);
const RB1 = entry('RB1', 'RB', 6000);
const WR1 = entry('WR1', 'WR', 7000);
const TE1 = entry('TE1', 'TE', 4000);
const TAXI1 = entry('T1', 'WR', 2000, 'taxi');
const TAXI2 = entry('T2', 'RB', 1500, 'taxi');

describe('rankSlates', () => {
  it('returns empty array when n=0', () => {
    expect(rankSlates([QB1, RB1, WR1], 0)).toEqual([]);
  });

  it('returns empty when no QBs', () => {
    expect(rankSlates([RB1, WR1, TE1])).toEqual([]);
  });

  it('rank-1 slate protects highest value combo', () => {
    const slates = rankSlates([QB1, RB1, WR1, TE1, TAXI1, TAXI2], 1);
    expect(slates).toHaveLength(1);
    // QB1(8000) + WR1(7000) in WR/TE slot + RB1(6000) + TAXI1+TAXI2 = best combo
    expect(slates[0].protectedValue).toBe(8000 + 7000 + 6000 + 2000 + 1500);
  });

  it('returns at most n slates', () => {
    const slates = rankSlates([QB1, RB1, WR1, TE1], 3);
    expect(slates.length).toBeLessThanOrEqual(3);
  });

  it('no player appears in two slots', () => {
    for (const slate of rankSlates([QB1, RB1, WR1, TE1, TAXI1], 5)) {
      const ids = [
        slate.qb.player.playerId,
        slate.rbTe.player.playerId,
        slate.wrTe.player.playerId,
        ...slate.taxi.map(t => t.player.playerId),
      ];
      expect(new Set(ids).size).toBe(ids.length);
    }
  });

  it('TE can fill the WR/TE slot', () => {
    const slates = rankSlates([QB1, RB1, TE1]);
    expect(slates.length).toBeGreaterThan(0);
    const withTe = slates.some(s => s.wrTe.player.playerId === 'TE1');
    expect(withTe).toBe(true);
  });
});

describe('valueAtRisk', () => {
  it('sums value of all unprotected entries', () => {
    const all = [QB1, RB1, WR1, TE1];
    const slate = rankSlates(all, 1)[0];
    const risk = valueAtRisk(all, slate);
    expect(risk).toBe(all.reduce((s, e) => s + (e.value.current ?? 0), 0) - slate.protectedValue);
  });
});

describe('pickValueUnderReset', () => {
  it('current-year pick is not discounted', () => {
    expect(pickValueUnderReset('2025', 1, 1.0, '2025', 1000)).toBe(1000);
  });

  it('future pick at 100% probability = 0', () => {
    expect(pickValueUnderReset('2026', 1, 1.0, '2025', 1000)).toBe(0);
  });

  it('future pick at 0% probability = base value', () => {
    expect(pickValueUnderReset('2026', 1, 0.0, '2025', 1000)).toBe(1000);
  });

  it('future pick at 50% probability = floor(base * 0.5)', () => {
    expect(pickValueUnderReset('2026', 1, 0.5, '2025', 1001)).toBe(500);
  });
});

describe('assetValueUnderReset', () => {
  it('at probability=0 returns raw value', () => {
    const entries = [QB1, RB1, WR1, TE1];
    expect(assetValueUnderReset(WR1, entries, 0)).toBe(7000);
  });

  it('at probability=1 returns protected contribution', () => {
    const entries = [QB1, RB1, WR1];
    const result = assetValueUnderReset(QB1, entries, 1.0);
    // QB1 is essential for any slate; removing it makes best_without=0
    expect(result).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
npm test -- lib/__tests__/reset-scoring.test.ts
```
Expected: FAIL.

- [ ] **Step 3: Write lib/utils.ts**

```typescript
// lib/utils.ts
export function* combinations<T>(arr: T[], k: number): Generator<T[]> {
  if (k === 0) { yield []; return; }
  if (k > arr.length) return;
  const [first, ...rest] = arr;
  for (const combo of combinations(rest, k - 1)) yield [first, ...combo];
  yield* combinations(rest, k);
}
```

- [ ] **Step 4: Write lib/reset-scoring.ts**

```typescript
// lib/reset-scoring.ts
import { combinations } from './utils';
import type { ProtectionSlate, RosterEntry } from './types';

function* enumerateSlates(entries: RosterEntry[]): Generator<ProtectionSlate> {
  const qbs = entries.filter(e => e.player.position === 'QB');
  if (!qbs.length) return;
  const rbTePool = entries.filter(e => ['RB', 'TE'].includes(e.player.position));
  const wrTePool = entries.filter(e => ['WR', 'TE'].includes(e.player.position));
  const taxiPool = entries.filter(e => e.slotType === 'taxi');

  for (const qb of qbs) {
    for (const rbTe of rbTePool) {
      if (rbTe.player.playerId === qb.player.playerId) continue;
      for (const wrTe of wrTePool) {
        const pid = wrTe.player.playerId;
        if (pid === qb.player.playerId || pid === rbTe.player.playerId) continue;
        const chosen = new Set([qb.player.playerId, rbTe.player.playerId, pid]);
        const remaining = taxiPool.filter(t => !chosen.has(t.player.playerId));
        const maxTaxi = Math.min(3, remaining.length);
        for (let n = 0; n <= maxTaxi; n++) {
          for (const taxi of combinations(remaining, n)) {
            const protectedValue =
              (qb.value.current ?? 0) +
              (rbTe.value.current ?? 0) +
              (wrTe.value.current ?? 0) +
              taxi.reduce((s, t) => s + (t.value.current ?? 0), 0);
            yield { qb, rbTe, wrTe, taxi, protectedValue };
          }
        }
      }
    }
  }
}

function comparePids(a: string[], b: string[]): number {
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if (i >= a.length) return -1;
    if (i >= b.length) return 1;
    const c = a[i].localeCompare(b[i]);
    if (c !== 0) return c;
  }
  return 0;
}

export function rankSlates(entries: RosterEntry[], n = 5): ProtectionSlate[] {
  if (n <= 0) return [];
  const all = [...enumerateSlates(entries)];
  all.sort((a, b) => {
    if (b.protectedValue !== a.protectedValue) return b.protectedValue - a.protectedValue;
    return comparePids(
      [a.qb.player.playerId, a.rbTe.player.playerId, a.wrTe.player.playerId, ...a.taxi.map(t => t.player.playerId)].sort(),
      [b.qb.player.playerId, b.rbTe.player.playerId, b.wrTe.player.playerId, ...b.taxi.map(t => t.player.playerId)].sort()
    );
  });
  return all.slice(0, n);
}

export function valueAtRisk(entries: RosterEntry[], slate: ProtectionSlate): number {
  const ids = new Set([
    slate.qb.player.playerId,
    slate.rbTe.player.playerId,
    slate.wrTe.player.playerId,
    ...slate.taxi.map(t => t.player.playerId),
  ]);
  return entries.filter(e => !ids.has(e.player.playerId)).reduce((s, e) => s + (e.value.current ?? 0), 0);
}

export function pickValueUnderReset(
  season: string, _round: number, probability: number, currentSeason: string, baseValue: number
): number {
  if (season === currentSeason) return baseValue;
  return Math.floor(baseValue * (1 - probability));
}

export function assetValueUnderReset(
  entry: RosterEntry, ownerEntries: RosterEntry[], probability: number
): number {
  const without = ownerEntries.filter(e => e.player.playerId !== entry.player.playerId);
  const bestWith = rankSlates(ownerEntries, 1)[0]?.protectedValue ?? 0;
  const bestWithout = rankSlates(without, 1)[0]?.protectedValue ?? 0;
  const contribution = Math.max(0, bestWith - bestWithout);
  const raw = entry.value.current ?? 0;
  return Math.floor(probability * contribution + (1 - probability) * raw);
}
```

- [ ] **Step 5: Run tests and confirm pass**

```bash
npm test -- lib/__tests__/reset-scoring.test.ts
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add lib/utils.ts lib/reset-scoring.ts lib/__tests__/reset-scoring.test.ts
git commit -m "feat: add combinations utility and reset-scoring port"
```

---

## Task 7: Context + Roster tool (`lib/context.ts`, `lib/tools/rosters.ts`)

**Files:**
- Create: `lib/context.ts`
- Create: `lib/tools/rosters.ts`

No unit tests for rosters.ts — its behavior is covered by the integration tests in Task 12 (Dashboard). The roster helpers are thin wrappers over already-tested Sleeper/FantasyCalc clients.

- [ ] **Step 1: Write lib/context.ts**

```typescript
// lib/context.ts
export interface Ctx {
  leagueId: string;
  username: string;
  season: string;
}

export function getCtx(): Ctx {
  return {
    leagueId: process.env.SLEEPER_LEAGUE_ID!,
    username: process.env.SLEEPER_USERNAME!,
    season: new Date().getFullYear().toString(),
  };
}
```

- [ ] **Step 2: Write lib/tools/rosters.ts**

```typescript
// lib/tools/rosters.ts
import * as sleeper from '../sleeper';
import { getFantasyCalcValues } from '../fantasycalc';
import type { Ctx } from '../context';
import type { Player, RosterEntry, RosterSummary, RosterView, SlotType, TeamValueBreakdown, Value } from '../types';

export type TeamSpec = 'me' | number | string;

export function classifySlot(playerId: string, roster: Record<string, unknown>): SlotType {
  if ((roster.taxi as string[] | null)?.includes(playerId)) return 'taxi';
  if ((roster.reserve as string[] | null)?.includes(playerId)) return 'ir';
  if ((roster.starters as string[] | null)?.includes(playerId)) return 'active';
  return 'bench';
}

export function playerFromSleeper(pid: string, data: Record<string, unknown>): Player {
  const fullName = (data.full_name as string) ||
    [data.first_name, data.last_name].filter(Boolean).join(' ') || pid;
  return {
    playerId: pid,
    fullName,
    position: (data.position as string) ?? 'UNK',
    team: data.team as string | undefined,
    age: data.age as number | undefined,
    status: data.status as string | undefined,
  };
}

export function valueMap(fcValues: Record<string, unknown>[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const row of fcValues) {
    const player = row.player as Record<string, unknown> | undefined;
    const sid = String(player?.sleeperId ?? '');
    const val = row.value as number | undefined;
    if (sid && val != null) out[sid] = Math.floor(val);
  }
  return out;
}

async function resolveRoster(
  ctx: Ctx,
  rosters: Record<string, unknown>[],
  users: Record<string, unknown>[],
  team: TeamSpec
): Promise<[Record<string, unknown>, Record<string, unknown>]> {
  const nameOf = (u: Record<string, unknown>) =>
    ((u.username as string) || (u.display_name as string) || '').toLowerCase();
  const userById = (uid: string) => users.find(u => u.user_id === uid) ?? {};

  if (team === 'me') {
    const me = users.find(u => nameOf(u) === ctx.username.toLowerCase());
    if (!me) throw new Error(`username ${ctx.username} not in league`);
    const roster = rosters.find(r => r.owner_id === me.user_id);
    if (!roster) throw new Error(`no roster for ${ctx.username}`);
    return [roster, me];
  }
  if (typeof team === 'number') {
    const roster = rosters.find(r => Number(r.roster_id) === team);
    if (!roster) throw new Error(`unknown roster_id=${team}`);
    return [roster, userById(roster.owner_id as string)];
  }
  const u = users.find(u => nameOf(u) === (team as string).toLowerCase());
  if (!u) throw new Error(`unknown username=${team}`);
  const roster = rosters.find(r => r.owner_id === u.user_id);
  if (!roster) throw new Error(`no roster for username=${team}`);
  return [roster, u];
}

export async function getRoster(ctx: Ctx, team: TeamSpec = 'me'): Promise<RosterView> {
  const [league, rosters, users, playersData, fcValues] = await Promise.all([
    sleeper.getLeague(ctx.leagueId),
    sleeper.getRosters(ctx.leagueId),
    sleeper.getLeagueUsers(ctx.leagueId),
    sleeper.getPlayers(),
    sleeper.getLeague(ctx.leagueId).then(lg => getFantasyCalcValues(lg)),
  ]);
  const values = valueMap(fcValues);
  const [roster, owner] = await resolveRoster(ctx, rosters, users, team);
  const pids = (roster.players as string[]) ?? [];
  const starters = new Set((roster.starters as string[]) ?? []);

  let totalActive = 0, totalTaxi = 0, totalIr = 0;
  const entries: RosterEntry[] = pids.map(pid => {
    const slot = classifySlot(pid, roster);
    const val = values[pid] ?? null;
    const entry: RosterEntry = {
      player: playerFromSleeper(pid, (playersData[pid] as Record<string, unknown>) ?? {}),
      slotType: slot,
      value: { current: val } satisfies Value,
      starter: starters.has(pid),
    };
    if (val != null) {
      if (slot === 'active' || slot === 'bench') totalActive += val;
      else if (slot === 'taxi') totalTaxi += val;
      else if (slot === 'ir') totalIr += val;
    }
    return entry;
  });

  return {
    rosterId: Number(roster.roster_id),
    ownerUsername: (owner.username as string) || (owner.display_name as string) || '',
    ownerDisplayName: owner.display_name as string | undefined,
    entries,
    totalValueActive: totalActive,
    totalValueTaxi: totalTaxi,
    totalValueIr: totalIr,
  };
}

export async function listRosters(ctx: Ctx): Promise<RosterSummary[]> {
  const [league, rosters, users, playersData, fcValues] = await Promise.all([
    sleeper.getLeague(ctx.leagueId),
    sleeper.getRosters(ctx.leagueId),
    sleeper.getLeagueUsers(ctx.leagueId),
    sleeper.getPlayers(),
    sleeper.getLeague(ctx.leagueId).then(lg => getFantasyCalcValues(lg)),
  ]);
  const values = valueMap(fcValues);
  const byUser = Object.fromEntries(users.map(u => [u.user_id as string, u]));
  return rosters.map(r => {
    const pids = (r.players as string[]) ?? [];
    const total = pids.reduce((s, pid) => s + (values[pid] ?? 0), 0);
    const top = pids
      .slice()
      .sort((a, b) => (values[b] ?? 0) - (values[a] ?? 0))
      .slice(0, 5)
      .map(pid => playerFromSleeper(pid, (playersData[pid] as Record<string, unknown>) ?? {}).fullName);
    const owner = byUser[r.owner_id as string] ?? {};
    return {
      rosterId: Number(r.roster_id),
      ownerUsername: (owner.username as string) || (owner.display_name as string) || '',
      totalValue: total,
      topAssets: top,
    };
  });
}

function ageCohort(age?: number): string {
  if (age == null) return 'unknown';
  if (age < 25) return 'under_25';
  if (age <= 28) return '25_28';
  return '29_plus';
}

export async function getTeamValueBreakdown(ctx: Ctx, team: TeamSpec = 'me'): Promise<TeamValueBreakdown> {
  const view = await getRoster(ctx, team);
  const byPosition: Record<string, number> = {};
  const byAgeCohort = { under_25: 0, '25_28': 0, '29_plus': 0, unknown: 0 };
  for (const e of view.entries) {
    const val = e.value.current ?? 0;
    byPosition[e.player.position] = (byPosition[e.player.position] ?? 0) + val;
    const cohort = ageCohort(e.player.age) as keyof typeof byAgeCohort;
    byAgeCohort[cohort] += val;
  }
  return {
    rosterId: view.rosterId,
    byPosition,
    byAgeCohort,
    taxiStashValue: view.totalValueTaxi,
    irValue: view.totalValueIr,
    activeValue: view.totalValueActive,
  };
}
```

- [ ] **Step 3: Typecheck**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add lib/context.ts lib/tools/rosters.ts
git commit -m "feat: add context helper and roster tools"
```

---

## Task 8: Reset optimizer tool (`lib/tools/reset-optimizer.ts`)

**Files:**
- Create: `lib/tools/reset-optimizer.ts`

- [ ] **Step 1: Write lib/tools/reset-optimizer.ts**

```typescript
// lib/tools/reset-optimizer.ts
import { rankSlates, valueAtRisk } from '../reset-scoring';
import { getRoster } from './rosters';
import type { Ctx } from '../context';
import type { TeamSpec } from './rosters';
import type { ProtectionSlot, ResetOptimizerResult, SlateOption, Swap } from '../types';

export async function resetOptimizer(
  ctx: Ctx,
  team: TeamSpec = 'me',
  resetProbability = 1.0,
  topN = 5
): Promise<ResetOptimizerResult> {
  const view = await getRoster(ctx, team);
  const notes: string[] = [];

  const valued = view.entries.filter(e => {
    if (e.value.current == null) {
      notes.push(`${e.player.fullName} has no FantasyCalc value, skipped`);
      return false;
    }
    return true;
  });

  const slates = rankSlates(valued, topN);
  const totalValue = view.entries.reduce((s, e) => s + (e.value.current ?? 0), 0);
  const taxiPoolSize = valued.filter(e => e.slotType === 'taxi').length;

  if (!slates.length) {
    notes.push('No valid protection slates found (roster has no QB?).');
    return { rosterId: view.rosterId, ownerUsername: view.ownerUsername, resetProbability, totalRosterValue: totalValue, options: [], taxiPoolSize, notes };
  }

  const rank1 = slates[0];
  if (rank1.taxi.length < 3) {
    notes.push(`${3 - rank1.taxi.length} TAXI protection slot(s) unused — fewer than 3 valued TAXI players.`);
  }

  const options: SlateOption[] = slates.map((slate, idx) => {
    const swaps: Swap[] = [];
    if (idx > 0) {
      const fixed: [ProtectionSlot, string, string, number][] = [
        ['qb', rank1.qb.player.playerId, slate.qb.player.playerId, (slate.qb.value.current ?? 0) - (rank1.qb.value.current ?? 0)],
        ['rb_te', rank1.rbTe.player.playerId, slate.rbTe.player.playerId, (slate.rbTe.value.current ?? 0) - (rank1.rbTe.value.current ?? 0)],
        ['wr_te', rank1.wrTe.player.playerId, slate.wrTe.player.playerId, (slate.wrTe.value.current ?? 0) - (rank1.wrTe.value.current ?? 0)],
      ];
      for (const [slot, from, to, delta] of fixed) {
        if (from !== to) swaps.push({ slot, fromPlayer: from, toPlayer: to, valueDelta: delta });
      }
      const r1TaxiIds = new Set(rank1.taxi.map(t => t.player.playerId));
      const sTaxiIds = new Set(slate.taxi.map(t => t.player.playerId));
      if (r1TaxiIds.size !== sTaxiIds.size || [...r1TaxiIds].some(id => !sTaxiIds.has(id))) {
        const r1Map = Object.fromEntries(rank1.taxi.map(t => [t.player.playerId, t]));
        const sMap = Object.fromEntries(slate.taxi.map(t => [t.player.playerId, t]));
        const removed = [...r1TaxiIds].filter(id => !sTaxiIds.has(id)).sort();
        const added = [...sTaxiIds].filter(id => !r1TaxiIds.has(id)).sort();
        const len = Math.max(removed.length, added.length);
        for (let i = 0; i < len; i++) {
          const from = removed[i] ?? '';
          const to = added[i] ?? '';
          swaps.push({ slot: 'taxi', fromPlayer: from, toPlayer: to, valueDelta: (to ? (sMap[to].value.current ?? 0) : 0) - (from ? (r1Map[from].value.current ?? 0) : 0) });
        }
      }
    }
    return { rank: idx + 1, protected: slate, protectedValue: slate.protectedValue, valueAtRisk: valueAtRisk(view.entries, slate), swapsFromTop: swaps };
  });

  return { rosterId: view.rosterId, ownerUsername: view.ownerUsername, resetProbability, totalRosterValue: totalValue, options, taxiPoolSize, notes };
}
```

- [ ] **Step 2: Typecheck**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add lib/tools/reset-optimizer.ts
git commit -m "feat: add reset optimizer tool"
```

---

## Task 9: Reset trades tool (`lib/tools/reset-trades.ts`)

**Files:**
- Create: `lib/tools/reset-trades.ts`

- [ ] **Step 1: Write lib/tools/reset-trades.ts**

```typescript
// lib/tools/reset-trades.ts
import * as sleeper from '../sleeper';
import { getFantasyCalcValues } from '../fantasycalc';
import { rankSlates, assetValueUnderReset, pickValueUnderReset } from '../reset-scoring';
import { classifySlot, playerFromSleeper, valueMap } from './rosters';
import type { Ctx } from '../context';
import type { RosterEntry, ResetTradeFinderResult, TradeAsset, TradeProposal } from '../types';
import { combinations } from '../utils';

interface PlayerAsset { kind: 'player'; entry: RosterEntry; ownerId: number }
interface PickAsset { kind: 'pick'; assetId: string; displayName: string; season: string; round: number; baseValue: number; ownerId: number }
type Asset = PlayerAsset | PickAsset;

function pickDisplayName(season: string, round: number): string {
  if (round === 1) return `${season} Mid 1st`;
  const ord: Record<number, string> = { 2: '2nd', 3: '3rd', 4: '4th', 5: '5th' };
  return `${season} ${ord[round] ?? `${round}th`}`;
}

function buildPickValueMap(fcValues: Record<string, unknown>[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const row of fcValues) {
    const p = row.player as Record<string, unknown> | undefined;
    if (!p?.sleeperId && p?.name && row.value != null) {
      out[p.name as string] = Math.floor(row.value as number);
    }
  }
  return out;
}

function buildPickPool(
  rosterIds: number[], tradedPicks: Record<string, unknown>[],
  seasons: string[], rounds: number[], pickValueMap: Record<string, number>
): PickAsset[] {
  const picks: Record<string, PickAsset> = {};
  for (const rid of rosterIds) {
    for (const season of seasons) {
      for (const round of rounds) {
        const assetId = `${season}_${round}_from_r${rid}`;
        const displayName = pickDisplayName(season, round);
        picks[assetId] = { kind: 'pick', assetId, displayName, season, round, baseValue: pickValueMap[displayName] ?? 0, ownerId: rid };
      }
    }
  }
  for (const tp of tradedPicks) {
    const { roster_id: rid, round, season, owner_id: newOwner } = tp as Record<string, unknown>;
    if (rid == null || round == null || !season || newOwner == null) continue;
    const assetId = `${season}_${round}_from_r${rid}`;
    if (assetId in picks) {
      picks[assetId] = { ...picks[assetId], ownerId: Number(newOwner) };
    }
  }
  return Object.values(picks);
}

function assetRawValue(a: Asset): number {
  return a.kind === 'player' ? (a.entry.value.current ?? 0) : a.baseValue;
}

function assetOutgoingValue(a: Asset, senderEntries: RosterEntry[], probability: number, currentSeason: string): number {
  if (a.kind === 'player') return assetValueUnderReset(a.entry, senderEntries, probability);
  return pickValueUnderReset(a.season, a.round, probability, currentSeason, a.baseValue);
}

function assetIncomingValue(a: Asset, receiverPost: RosterEntry[], probability: number, currentSeason: string): number {
  if (a.kind === 'player') return assetValueUnderReset(a.entry, receiverPost, probability);
  return pickValueUnderReset(a.season, a.round, probability, currentSeason, a.baseValue);
}

function slateSlotMap(slate: ReturnType<typeof rankSlates>[0] | undefined): Record<string, string> {
  if (!slate) return {};
  return { qb: slate.qb.player.playerId, rb_te: slate.rbTe.player.playerId, wr_te: slate.wrTe.player.playerId };
}

function slateAllIds(slate: ReturnType<typeof rankSlates>[0] | undefined): Set<string> {
  if (!slate) return new Set();
  return new Set([slate.qb.player.playerId, slate.rbTe.player.playerId, slate.wrTe.player.playerId, ...slate.taxi.map(t => t.player.playerId)]);
}

function toTradeAsset(a: Asset, receiverPost: RosterEntry[], receiverPostSlateIds: Set<string>, probability: number, currentSeason: string): TradeAsset {
  if (a.kind === 'player') {
    return { kind: 'player', assetId: a.entry.player.playerId, displayName: a.entry.player.fullName, rawValue: a.entry.value.current ?? 0, resetAdjustedValue: assetValueUnderReset(a.entry, receiverPost, probability), protectableOnReceiver: receiverPostSlateIds.has(a.entry.player.playerId) };
  }
  return { kind: 'pick', assetId: a.assetId, displayName: a.displayName, rawValue: a.baseValue, resetAdjustedValue: pickValueUnderReset(a.season, a.round, probability, currentSeason, a.baseValue), protectableOnReceiver: false };
}

export async function resetTrades(
  ctx: Ctx,
  partner: 'me' | number | string | null = null,
  resetProbability = 0.0,
  maxSend = 2, maxRecv = 2, minEdge = 500, topN = 10
): Promise<ResetTradeFinderResult> {
  const [league, rosters, users, playersData, fcValues, tradedPicksRaw] = await Promise.all([
    sleeper.getLeague(ctx.leagueId),
    sleeper.getRosters(ctx.leagueId),
    sleeper.getLeagueUsers(ctx.leagueId),
    sleeper.getPlayers(),
    sleeper.getLeague(ctx.leagueId).then(lg => getFantasyCalcValues(lg)),
    sleeper.getTradedPicks(ctx.leagueId),
  ]);

  const values = valueMap(fcValues);
  const pickValueMap = buildPickValueMap(fcValues);
  const notes: string[] = [];
  const byUserId = Object.fromEntries(users.map(u => [u.user_id as string, u]));

  const meUser = users.find(u => ((u.username as string) || (u.display_name as string) || '').toLowerCase() === ctx.username.toLowerCase());
  if (!meUser) throw new Error(`username ${ctx.username} not in league`);
  const meRosterRaw = rosters.find(r => r.owner_id === meUser.user_id);
  if (!meRosterRaw) throw new Error(`no roster for ${ctx.username}`);
  const myRosterId = Number(meRosterRaw.roster_id);

  const buildEntries = (r: Record<string, unknown>): RosterEntry[] =>
    ((r.players as string[]) ?? []).map(pid => ({
      player: playerFromSleeper(pid, (playersData[pid] as Record<string, unknown>) ?? {}),
      slotType: classifySlot(pid, r),
      value: { current: values[pid] ?? null },
      starter: ((r.starters as string[]) ?? []).includes(pid),
    })).filter(e => e.value.current != null);

  const allRosterIds = rosters.map(r => Number(r.roster_id));
  const currentYear = ctx.season;
  const nextYear = String(Number(currentYear) + 1);
  const allPicks = buildPickPool(allRosterIds, tradedPicksRaw, [currentYear, nextYear], [1, 2, 3, 4], pickValueMap);
  const unmatched = allPicks.filter(p => p.baseValue === 0).length;
  if (unmatched) notes.push(`${unmatched} picks have no FantasyCalc value match; treated as 0.`);

  let counterpartyIds: number[];
  if (partner != null) {
    const partnerRoster = partner === 'me' ? meRosterRaw :
      typeof partner === 'number' ? rosters.find(r => Number(r.roster_id) === partner) :
      (() => { const u = users.find(u => ((u.username as string) || '').toLowerCase() === (partner as string).toLowerCase()); return u ? rosters.find(r => r.owner_id === u.user_id) : undefined; })();
    if (!partnerRoster) throw new Error(`partner not found: ${partner}`);
    counterpartyIds = [Number(partnerRoster.roster_id)];
  } else {
    counterpartyIds = allRosterIds.filter(id => id !== myRosterId);
  }

  const myEntries = buildEntries(meRosterRaw);
  const myPicks = allPicks.filter(p => p.ownerId === myRosterId);
  const myBaseSlate = rankSlates(myEntries, 1)[0];
  const myBaseSlotMap = slateSlotMap(myBaseSlate);

  const myPool: Asset[] = [
    ...myEntries.map(e => ({ kind: 'player' as const, entry: e, ownerId: myRosterId })),
    ...myPicks,
  ].sort((a, b) => assetRawValue(b) - assetRawValue(a)).slice(0, 15);

  const allProposals: TradeProposal[] = [];

  for (const theirRosterId of counterpartyIds) {
    const theirRaw = rosters.find(r => Number(r.roster_id) === theirRosterId)!;
    const theirUser = byUserId[theirRaw.owner_id as string] ?? {};
    const theirUsername = (theirUser.username as string) || (theirUser.display_name as string) || '';
    const theirEntries = buildEntries(theirRaw);
    const theirPicks = allPicks.filter(p => p.ownerId === theirRosterId);
    const theirPool: Asset[] = [
      ...theirEntries.map(e => ({ kind: 'player' as const, entry: e, ownerId: theirRosterId })),
      ...theirPicks,
    ].sort((a, b) => assetRawValue(b) - assetRawValue(a)).slice(0, 15);

    const myOutMap = new Map(myPool.map(a => [a, assetOutgoingValue(a, myEntries, resetProbability, currentYear)]));
    const theirOutMap = new Map(theirPool.map(a => [a, assetOutgoingValue(a, theirEntries, resetProbability, currentYear)]));

    for (let ss = 1; ss <= maxSend; ss++) {
      for (let rs = 1; rs <= maxRecv; rs++) {
        for (const send of combinations(myPool, ss)) {
          for (const recv of combinations(theirPool, rs)) {
            const sendPids = new Set(send.filter(a => a.kind === 'player').map(a => (a as PlayerAsset).entry.player.playerId));
            const recvPids = new Set(recv.filter(a => a.kind === 'player').map(a => (a as PlayerAsset).entry.player.playerId));
            const myPost = [...myEntries.filter(e => !sendPids.has(e.player.playerId)), ...recv.filter(a => a.kind === 'player').map(a => (a as PlayerAsset).entry)];
            const theirPost = [...theirEntries.filter(e => !recvPids.has(e.player.playerId)), ...send.filter(a => a.kind === 'player').map(a => (a as PlayerAsset).entry)];

            const myOut = send.reduce((s, a) => s + (myOutMap.get(a) ?? 0), 0);
            const myIn = recv.reduce((s, a) => s + assetIncomingValue(a, myPost, resetProbability, currentYear), 0);
            const theirOut = recv.reduce((s, a) => s + (theirOutMap.get(a) ?? 0), 0);
            const theirIn = send.reduce((s, a) => s + assetIncomingValue(a, theirPost, resetProbability, currentYear), 0);

            if (myIn - myOut < minEdge || theirIn - theirOut < minEdge) continue;

            const myPostSlate = rankSlates(myPost, 1)[0];
            const myPostSlateIds = slateAllIds(myPostSlate);
            const myPostSlotMap = slateSlotMap(myPostSlate);
            const theirPostSlate = rankSlates(theirPost, 1)[0];
            const theirPostSlateIds = slateAllIds(theirPostSlate);

            const flags: string[] = [];
            for (const slot of ['qb', 'rb_te', 'wr_te'] as const) {
              if (myBaseSlotMap[slot] !== myPostSlotMap[slot]) flags.push(`fills_my_${slot}_protection`);
            }
            const sendPlayers = send.filter(a => a.kind === 'player') as PlayerAsset[];
            if (sendPlayers.length && sendPlayers.every(a => assetValueUnderReset(a.entry, myEntries, 1.0) === 0)) {
              flags.push('i_surrender_unprotectable_depth');
            }
            const futurePicks = [...send, ...recv].filter(a => a.kind === 'pick' && (a as PickAsset).season > currentYear);
            if (futurePicks.length && resetProbability > 0) flags.push(`future_pick_discounted_${Math.round(resetProbability * 100)}%`);
            if (recv.some(a => a.kind === 'player' && (a as PlayerAsset).entry.slotType === 'taxi')) flags.push('partner_rebuilds_taxi');

            allProposals.push({
              rank: 0,
              partnerRosterId: theirRosterId,
              partnerUsername: theirUsername,
              mySend: send.map(a => toTradeAsset(a, theirPost, theirPostSlateIds, resetProbability, currentYear)),
              myRecv: recv.map(a => toTradeAsset(a, myPost, myPostSlateIds, resetProbability, currentYear)),
              myNetEdge: myIn - myOut,
              partnerNetEdge: theirIn - theirOut,
              rationaleFlags: flags,
            });
          }
        }
      }
    }
  }

  allProposals.sort((a, b) => b.myNetEdge - a.myNetEdge);
  const top = allProposals.slice(0, topN).map((p, i) => ({ ...p, rank: i + 1 }));
  return { resetProbability, proposals: top, consideredPartners: counterpartyIds, notes };
}
```

- [ ] **Step 2: Typecheck**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add lib/tools/reset-trades.ts
git commit -m "feat: add reset trades tool"
```

---

## Task 10: AI helper (`lib/ai.ts`)

**Files:**
- Create: `lib/ai.ts`

- [ ] **Step 1: Write lib/ai.ts**

```typescript
// lib/ai.ts
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

const LEAGUE_CTX = `You are a dynasty fantasy football advisor for a 14-team superflex dynasty league. Key scoring: 0.5 PPR with 0.5 per-first-down bonus; TEs get full 1.0 PPR. Reset mechanics: each team protects 1 QB, 1 RB/TE, 1 WR/TE, and up to 3 TAXI players. Future picks are voided in a reset. Be specific, concise (2–4 sentences), and actionable. Do not use bullet points.`;

const SYSTEM_PROMPTS: Record<string, string> = {
  dashboard: `${LEAGUE_CTX} You are given a team's roster value, rank among all 14 teams, and top 5 players. Summarize the team's dynasty outlook and biggest strength or weakness.`,
  'reset-optimizer': `${LEAGUE_CTX} You are given the top reset protection slates with values. Recommend the best protection choice and briefly explain the key trade-off vs. the #2 option.`,
  'reset-trades': `${LEAGUE_CTX} You are given mutually beneficial trade proposals ranked by net edge. Identify the top trade opportunity and its strategic rationale in the context of the reset.`,
  'team-value': `${LEAGUE_CTX} You are given a team's dynasty value broken down by position and age cohort. Analyze the biggest positional strength and weakness, and comment on the age profile.`,
};

export async function generateSummary(
  tool: keyof typeof SYSTEM_PROMPTS,
  data: unknown,
  model: 'claude-sonnet-4-6' | 'claude-haiku-4-5-20251001' = 'claude-haiku-4-5-20251001'
): Promise<string> {
  const msg = await client.messages.create({
    model,
    max_tokens: 300,
    system: SYSTEM_PROMPTS[tool],
    messages: [{ role: 'user', content: JSON.stringify(data, null, 2) }],
  });
  const block = msg.content[0];
  return block.type === 'text' ? block.text : '';
}
```

- [ ] **Step 2: Typecheck**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add lib/ai.ts
git commit -m "feat: add AI summary helper"
```

---

## Task 11: Shared layout + components

**Files:**
- Modify: `app/layout.tsx`
- Create: `components/Nav.tsx`
- Create: `components/AiSummary.tsx`
- Create: `components/RefreshButton.tsx`

- [ ] **Step 1: Write components/Nav.tsx**

```tsx
// components/Nav.tsx
import Link from 'next/link';

const links = [
  { href: '/', label: 'Dashboard' },
  { href: '/reset-optimizer', label: 'Reset Optimizer' },
  { href: '/reset-trades', label: 'Reset Trades' },
  { href: '/team-value', label: 'Team Value' },
];

export function Nav() {
  return (
    <nav className="w-52 shrink-0 border-r border-white/10 min-h-screen p-4">
      <p className="text-xs font-bold uppercase tracking-widest text-white/40 mb-4">Dynasty</p>
      <ul className="space-y-1">
        {links.map(l => (
          <li key={l.href}>
            <Link href={l.href} className="block px-3 py-2 rounded text-sm text-white/70 hover:bg-white/5 hover:text-white transition-colors">
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
```

- [ ] **Step 2: Write components/AiSummary.tsx**

```tsx
// components/AiSummary.tsx
interface Props { summary: string }

export function AiSummary({ summary }: Props) {
  return (
    <div className="border border-indigo-500/30 border-l-2 border-l-indigo-500 rounded-lg p-4 mb-6 bg-indigo-950/20">
      <p className="text-xs font-semibold uppercase tracking-widest text-indigo-400 mb-2">AI Summary</p>
      <p className="text-sm text-white/80 leading-relaxed">{summary}</p>
    </div>
  );
}
```

- [ ] **Step 3: Write components/RefreshButton.tsx**

```tsx
// components/RefreshButton.tsx
'use client';
import { useRouter } from 'next/navigation';

export function RefreshButton() {
  const router = useRouter();
  return (
    <button
      onClick={() => router.push('?' + new URLSearchParams({ t: String(Date.now()) }))}
      className="text-xs px-3 py-1.5 rounded border border-white/20 text-white/60 hover:text-white hover:border-white/40 transition-colors"
    >
      ↻ Refresh data
    </button>
  );
}
```

- [ ] **Step 4: Update app/layout.tsx**

```tsx
// app/layout.tsx
import type { Metadata } from 'next';
import './globals.css';
import { Nav } from '@/components/Nav';

export const metadata: Metadata = { title: 'Dynasty App' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0e0e1a] text-white min-h-screen">
        <div className="flex">
          <Nav />
          <main className="flex-1 p-6 max-w-5xl">{children}</main>
        </div>
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Verify dev server**

```bash
npm run dev
```
Expected: http://localhost:3000 shows sidebar nav with 4 links, dark background.

- [ ] **Step 6: Commit**

```bash
git add app/layout.tsx components/Nav.tsx components/AiSummary.tsx components/RefreshButton.tsx
git commit -m "feat: add shared layout, nav, and shared components"
```

---

## Task 12: Dashboard page

**Files:**
- Modify: `app/page.tsx`

- [ ] **Step 1: Write app/page.tsx**

```tsx
// app/page.tsx
import { getCtx } from '@/lib/context';
import { getRoster, listRosters } from '@/lib/tools/rosters';
import { generateSummary } from '@/lib/ai';
import { AiSummary } from '@/components/AiSummary';
import { RefreshButton } from '@/components/RefreshButton';

export default async function DashboardPage({ searchParams }: { searchParams: Promise<{ t?: string }> }) {
  await searchParams; // force dynamic rendering
  const ctx = getCtx();
  const [view, allRosters] = await Promise.all([getRoster(ctx), listRosters(ctx)]);

  const totalValue = view.totalValueActive + view.totalValueTaxi + view.totalValueIr;
  const sorted = [...allRosters].sort((a, b) => b.totalValue - a.totalValue);
  const rank = sorted.findIndex(r => r.rosterId === view.rosterId) + 1;
  const topFive = view.entries
    .filter(e => e.value.current)
    .sort((a, b) => (b.value.current ?? 0) - (a.value.current ?? 0))
    .slice(0, 5);

  const summaryData = {
    ownerUsername: view.ownerUsername,
    totalValue,
    rank,
    numTeams: allRosters.length,
    topPlayers: topFive.map(e => ({ name: e.player.fullName, position: e.player.position, value: e.value.current })),
  };
  const summary = await generateSummary('dashboard', summaryData, 'claude-sonnet-4-6');

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">{view.ownerUsername} — Dashboard</h1>
        <RefreshButton />
      </div>
      <AiSummary summary={summary} />
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white/5 rounded-lg p-4">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-1">Total Value</p>
          <p className="text-2xl font-bold">{totalValue.toLocaleString()}</p>
        </div>
        <div className="bg-white/5 rounded-lg p-4">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-1">League Rank</p>
          <p className="text-2xl font-bold">#{rank} <span className="text-sm font-normal text-white/40">of {allRosters.length}</span></p>
        </div>
        <div className="bg-white/5 rounded-lg p-4">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-1">Active / TAXI / IR</p>
          <p className="text-sm font-medium">{view.totalValueActive.toLocaleString()} / {view.totalValueTaxi.toLocaleString()} / {view.totalValueIr.toLocaleString()}</p>
        </div>
      </div>
      <h2 className="text-sm font-semibold text-white/60 uppercase tracking-widest mb-3">Top Assets</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-white/30 uppercase tracking-widest border-b border-white/10">
            <th className="text-left py-2 px-3">Player</th>
            <th className="text-left py-2 px-3">Pos</th>
            <th className="text-left py-2 px-3">Team</th>
            <th className="text-left py-2 px-3">Slot</th>
            <th className="text-right py-2 px-3">Value</th>
          </tr>
        </thead>
        <tbody>
          {topFive.map(e => (
            <tr key={e.player.playerId} className="border-b border-white/5 hover:bg-white/5">
              <td className="py-2 px-3">{e.player.fullName}</td>
              <td className="py-2 px-3 text-white/60">{e.player.position}</td>
              <td className="py-2 px-3 text-white/60">{e.player.team ?? '—'}</td>
              <td className="py-2 px-3 text-white/60 capitalize">{e.slotType}</td>
              <td className="py-2 px-3 text-right font-medium">{e.value.current?.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Navigate to http://localhost:3000. Confirm:
- Team name appears in heading
- AI summary card shows
- 3 stat cards (total value, rank, breakdown) show
- Top assets table populates with real player names

- [ ] **Step 3: Commit**

```bash
git add app/page.tsx
git commit -m "feat: add Dashboard page"
```

---

## Task 13: Reset Optimizer page

**Files:**
- Create: `app/reset-optimizer/page.tsx`

- [ ] **Step 1: Write app/reset-optimizer/page.tsx**

```tsx
// app/reset-optimizer/page.tsx
import { getCtx } from '@/lib/context';
import { resetOptimizer } from '@/lib/tools/reset-optimizer';
import { generateSummary } from '@/lib/ai';
import { AiSummary } from '@/components/AiSummary';
import { RefreshButton } from '@/components/RefreshButton';

export default async function ResetOptimizerPage({ searchParams }: { searchParams: Promise<{ t?: string }> }) {
  await searchParams;
  const ctx = getCtx();
  const result = await resetOptimizer(ctx, 'me', 1.0, 5);
  const summary = await generateSummary('reset-optimizer', result, 'claude-sonnet-4-6');

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Reset Optimizer</h1>
        <RefreshButton />
      </div>
      {result.notes.length > 0 && (
        <div className="mb-4 text-xs text-yellow-400/70 space-y-1">
          {result.notes.map((n, i) => <p key={i}>⚠ {n}</p>)}
        </div>
      )}
      <AiSummary summary={summary} />
      <div className="flex gap-4 text-xs text-white/40 mb-6">
        <span>Total roster value: <strong className="text-white">{result.totalRosterValue.toLocaleString()}</strong></span>
        <span>TAXI players valued: <strong className="text-white">{result.taxiPoolSize}</strong></span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-white/30 uppercase tracking-widest border-b border-white/10">
            <th className="text-left py-2 px-3">#</th>
            <th className="text-left py-2 px-3">QB Slot</th>
            <th className="text-left py-2 px-3">RB/TE Slot</th>
            <th className="text-left py-2 px-3">WR/TE Slot</th>
            <th className="text-left py-2 px-3">TAXI (up to 3)</th>
            <th className="text-right py-2 px-3">Protected</th>
            <th className="text-right py-2 px-3">At Risk</th>
          </tr>
        </thead>
        <tbody>
          {result.options.map(opt => (
            <tr key={opt.rank} className={`border-b border-white/5 hover:bg-white/5 ${opt.rank === 1 ? 'bg-indigo-950/30' : ''}`}>
              <td className="py-2 px-3 font-semibold text-indigo-400">{opt.rank}</td>
              <td className="py-2 px-3">{opt.protected.qb.player.fullName}</td>
              <td className="py-2 px-3">{opt.protected.rbTe.player.fullName}</td>
              <td className="py-2 px-3">{opt.protected.wrTe.player.fullName}</td>
              <td className="py-2 px-3 text-white/60 text-xs">{opt.protected.taxi.map(t => t.player.fullName).join(' · ') || '—'}</td>
              <td className="py-2 px-3 text-right text-green-400 font-medium">{opt.protectedValue.toLocaleString()}</td>
              <td className="py-2 px-3 text-right text-red-400">{opt.valueAtRisk.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.options[0]?.swapsFromTop.length === 0 && result.options.length > 1 && (
        <details className="mt-4 text-xs text-white/50">
          <summary className="cursor-pointer hover:text-white/70">Swap deltas vs. #1 slate</summary>
          <div className="mt-2 space-y-1 pl-3">
            {result.options.slice(1).flatMap(opt =>
              opt.swapsFromTop.map((s, i) => (
                <p key={`${opt.rank}-${i}`}>
                  Slate #{opt.rank} · {s.slot}: {s.fromPlayer} → {s.toPlayer} ({s.valueDelta >= 0 ? '+' : ''}{s.valueDelta.toLocaleString()})
                </p>
              ))
            )}
          </div>
        </details>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Navigate to http://localhost:3000/reset-optimizer. Confirm:
- AI summary card appears with specific player names
- Slates table shows top-5 rows
- Rank #1 row is highlighted
- Protected and At Risk values are populated

- [ ] **Step 3: Commit**

```bash
git add app/reset-optimizer/page.tsx
git commit -m "feat: add Reset Optimizer page"
```

---

## Task 14: Reset Trades page

**Files:**
- Create: `app/reset-trades/page.tsx`

- [ ] **Step 1: Write app/reset-trades/page.tsx**

```tsx
// app/reset-trades/page.tsx
import { getCtx } from '@/lib/context';
import { resetTrades } from '@/lib/tools/reset-trades';
import { generateSummary } from '@/lib/ai';
import { AiSummary } from '@/components/AiSummary';
import { RefreshButton } from '@/components/RefreshButton';

export default async function ResetTradesPage({ searchParams }: { searchParams: Promise<{ t?: string; prob?: string }> }) {
  const params = await searchParams;
  const prob = Math.max(0, Math.min(1, parseFloat(params.prob ?? '0')));
  const ctx = getCtx();
  const result = await resetTrades(ctx, null, prob, 2, 2, 500, 10);
  const summary = await generateSummary('reset-trades', { resetProbability: prob, topProposals: result.proposals.slice(0, 3) }, 'claude-sonnet-4-6');

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Reset Trades</h1>
        <RefreshButton />
      </div>
      <form className="mb-6 flex items-center gap-3" action="/reset-trades">
        <label className="text-sm text-white/60">Reset probability</label>
        <select name="prob" defaultValue={String(prob)} className="bg-white/10 border border-white/20 rounded px-2 py-1 text-sm text-white">
          {[0, 0.25, 0.5, 0.75, 1.0].map(v => <option key={v} value={String(v)}>{Math.round(v * 100)}%</option>)}
        </select>
        <button type="submit" className="px-3 py-1 text-sm rounded bg-indigo-600 hover:bg-indigo-500 text-white">Apply</button>
      </form>
      {result.notes.length > 0 && (
        <div className="mb-4 text-xs text-yellow-400/70 space-y-1">
          {result.notes.map((n, i) => <p key={i}>⚠ {n}</p>)}
        </div>
      )}
      <AiSummary summary={summary} />
      <div className="space-y-4">
        {result.proposals.length === 0 ? (
          <p className="text-white/40 text-sm">No mutually beneficial trades found at min_edge=500.</p>
        ) : result.proposals.map(p => (
          <div key={p.rank} className="border border-white/10 rounded-lg p-4">
            <div className="flex justify-between items-start mb-3">
              <span className="text-indigo-400 font-semibold text-sm">#{p.rank} · vs {p.partnerUsername}</span>
              <div className="text-xs text-white/40 space-x-3">
                <span className="text-green-400">You +{p.myNetEdge.toLocaleString()}</span>
                <span>Partner +{p.partnerNetEdge.toLocaleString()}</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-xs text-white/30 uppercase tracking-widest mb-1">You send</p>
                {p.mySend.map(a => <p key={a.assetId} className="text-red-300">{a.displayName} ({a.resetAdjustedValue.toLocaleString()})</p>)}
              </div>
              <div>
                <p className="text-xs text-white/30 uppercase tracking-widest mb-1">You receive</p>
                {p.myRecv.map(a => <p key={a.assetId} className="text-green-300">{a.displayName} ({a.resetAdjustedValue.toLocaleString()}){a.protectableOnReceiver ? ' ✓' : ''}</p>)}
              </div>
            </div>
            {p.rationaleFlags.length > 0 && (
              <div className="mt-2 flex gap-2 flex-wrap">
                {p.rationaleFlags.map(f => <span key={f} className="text-xs px-2 py-0.5 rounded bg-white/5 text-white/40">{f}</span>)}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Navigate to http://localhost:3000/reset-trades. Confirm:
- AI summary card appears
- Trade proposals appear (or "no trades found" message)
- Reset probability selector works
- Each proposal shows send/receive assets with values

- [ ] **Step 3: Commit**

```bash
git add app/reset-trades/page.tsx
git commit -m "feat: add Reset Trades page"
```

---

## Task 15: Team Value Breakdown page

**Files:**
- Create: `app/team-value/page.tsx`

- [ ] **Step 1: Write app/team-value/page.tsx**

```tsx
// app/team-value/page.tsx
import { getCtx } from '@/lib/context';
import { getTeamValueBreakdown, listRosters } from '@/lib/tools/rosters';
import { generateSummary } from '@/lib/ai';
import { AiSummary } from '@/components/AiSummary';
import { RefreshButton } from '@/components/RefreshButton';

export default async function TeamValuePage({ searchParams }: { searchParams: Promise<{ t?: string }> }) {
  await searchParams;
  const ctx = getCtx();
  const [breakdown, allRosters] = await Promise.all([getTeamValueBreakdown(ctx), listRosters(ctx)]);

  const sorted = [...allRosters].sort((a, b) => b.totalValue - a.totalValue);
  const myRoster = allRosters.find(r => r.rosterId === breakdown.rosterId);
  const rank = sorted.findIndex(r => r.rosterId === breakdown.rosterId) + 1;
  const totalValue = breakdown.activeValue + breakdown.taxiStashValue + breakdown.irValue;

  const summaryData = { ownerUsername: myRoster?.ownerUsername, rank, totalValue, byPosition: breakdown.byPosition, byAgeCohort: breakdown.byAgeCohort };
  const summary = await generateSummary('team-value', summaryData, 'claude-sonnet-4-6');

  const positions = Object.entries(breakdown.byPosition).sort(([, a], [, b]) => b - a);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Team Value Breakdown</h1>
        <RefreshButton />
      </div>
      <AiSummary summary={summary} />
      <div className="grid grid-cols-2 gap-6">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-white/40 mb-3">By Position</h2>
          <div className="space-y-2">
            {positions.map(([pos, val]) => {
              const pct = totalValue > 0 ? Math.round((val / totalValue) * 100) : 0;
              return (
                <div key={pos}>
                  <div className="flex justify-between text-sm mb-1">
                    <span>{pos}</span>
                    <span className="text-white/60">{val.toLocaleString()} ({pct}%)</span>
                  </div>
                  <div className="h-1.5 bg-white/10 rounded-full">
                    <div className="h-1.5 bg-indigo-500 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-white/40 mb-3">By Age</h2>
          <div className="space-y-2">
            {Object.entries(breakdown.byAgeCohort).map(([cohort, val]) => {
              const pct = totalValue > 0 ? Math.round((val / totalValue) * 100) : 0;
              return (
                <div key={cohort}>
                  <div className="flex justify-between text-sm mb-1">
                    <span>{cohort.replace('_', ' ')}</span>
                    <span className="text-white/60">{val.toLocaleString()} ({pct}%)</span>
                  </div>
                  <div className="h-1.5 bg-white/10 rounded-full">
                    <div className="h-1.5 bg-indigo-500 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div className="mt-6 grid grid-cols-3 gap-4">
        {[['Active/Bench', breakdown.activeValue], ['TAXI Stash', breakdown.taxiStashValue], ['IR', breakdown.irValue]].map(([label, val]) => (
          <div key={label as string} className="bg-white/5 rounded-lg p-3">
            <p className="text-xs text-white/40 uppercase tracking-widest mb-1">{label}</p>
            <p className="font-semibold">{(val as number).toLocaleString()}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Navigate to http://localhost:3000/team-value. Confirm:
- AI summary card appears with position/age analysis
- Position breakdown bar chart renders correctly
- Age cohort breakdown renders correctly
- Active/TAXI/IR stats appear

- [ ] **Step 3: Commit**

```bash
git add app/team-value/page.tsx
git commit -m "feat: add Team Value Breakdown page"
```

---

## Task 16: Full test run + deploy to Vercel

**Files:** No new files.

- [ ] **Step 1: Run full test suite**

```bash
npm test
```
Expected: all tests pass (cache, sleeper, fantasycalc, reset-scoring).

- [ ] **Step 2: Typecheck entire project**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Verify all four pages locally**

Start `npm run dev` and visit:
- http://localhost:3000 — dashboard loads with AI summary + stats
- http://localhost:3000/reset-optimizer — slates table with AI recommendation
- http://localhost:3000/reset-trades — proposals or "no trades" message
- http://localhost:3000/team-value — position + age breakdown

- [ ] **Step 4: Deploy to Vercel**

```bash
npx vercel
```
Follow prompts: link to a new project, use defaults. Then set env vars in Vercel dashboard (Project Settings → Environment Variables):
- `NEXT_PUBLIC_SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ANTHROPIC_API_KEY`
- `SLEEPER_USERNAME`
- `SLEEPER_LEAGUE_ID`

Then deploy with env vars:
```bash
npx vercel --prod
```
Expected: deployment URL printed. Open it and verify all four pages load.

- [ ] **Step 5: Shut down Fly.io (once hosted app is verified)**

```bash
fly apps destroy dynasty-mcp
```
Only run this after confirming the Vercel app is fully functional.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: Phase 1 complete — all pages verified on Vercel"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Next.js 16 + React 19 + Tailwind 4 + Supabase + Anthropic SDK (Tasks 1–2)
- ✅ Supabase schema replacing SQLite (Task 3)
- ✅ Sleeper client with cache-aware getPlayers (Task 4)
- ✅ FantasyCalc client with deriveParams (Task 5)
- ✅ Pure reset-scoring math port (Task 6)
- ✅ Context + roster/value tools (Task 7)
- ✅ Reset optimizer tool (Task 8)
- ✅ Reset trades tool (Task 9)
- ✅ AI summary helper with per-tool system prompts (Task 10)
- ✅ Shared layout + nav + components (Task 11)
- ✅ Dashboard page (Task 12)
- ✅ Reset Optimizer page (Task 13)
- ✅ Reset Trades page (Task 14)
- ✅ Team Value Breakdown page (Task 15)
- ✅ Deploy to Vercel + shut down Fly.io (Task 16)
- ✅ Sonnet for Phase 1 tools (Tasks 12–15), Haiku as default
- ✅ Config via env vars, no auth

**Type consistency check:** All TypeScript types use camelCase consistently (`playerId`, `slotType`, `protectedValue`, `rbTe`, `wrTe`). The `combinations` function used in both `reset-scoring.ts` and `reset-trades.ts` is imported from the same `lib/utils.ts`. The `Ctx` interface from `lib/context.ts` is the same shape used in all tool functions. No mismatches found.

**No placeholders found.**
