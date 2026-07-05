# Improvement Plan — Assertiveness & Coverage

> Status: approved 2026-07-05. Notion restructure done (see "Notion changes already applied").
> Execution order: Phase 1 → run the pipeline for real → calibrate → Phases 2/3 → Phase 4.

## Why

Audit findings (2026-07-05), traced with a real job the pipeline missed
([1277] Pessoa Desenvolvedora Fullstack .NET C#/React PL — Venturus, hosted on InHire):

1. **Dealbreaker false positive** — `presencial` is matched as a substring against the whole
   description. Remote jobs listing "Auxílio Mobilidade (trabalho híbrido ou presencial)" in the
   benefits section get vetoed. Silent killer of good jobs.
2. **Scoring model mismatch** — `required_stack` (React, TypeScript, Node.js) uses a ratio where
   *all* items are expected. The candidate profile is multi-stack (Node **or** Java **or** .NET,
   plus React). A perfect .NET+React job scored 2.3/10 and died below the threshold.
3. **Hybrid veto bug** — profile accepts `Híbrido`, but `scorer.py` vetoes any `is_remote == False`.
4. **Weak seniority detection** — only `senior`/`sênior`/`sr.` title tokens; misses `sr`, `III`,
   `especialista`, `staff`, `lead`, `principal`. No positive signal for `PL`/`Pleno`/`JR`/`Júnior`.
5. **Noisy search terms** — 13 keywords mixing search terms with filters (`dev`, `junior`,
   `desenvolvedora`) pulled unrelated jobs (Android, etc.). 26 scrapes per run.
6. **Missing sources** — InHire and Gupy were absent. Both have public, key-less APIs (verified
   via curl on 2026-07-05).

## Notion changes already applied

Profile DB (`Perfil — Job Hunter Config`, data source `c01ada18-24e1-4d2f-8ace-57c88a30bd26`):

- **Added** `stack_groups` (text): `React, Angular, Next.js | Node.js, NestJS, Express, Java, Spring, .NET, C#`
  — groups separated by `|`, technologies by comma.
- **Added** `inhire_tenants` (text): `venturus` — comma-separated InHire subdomains to poll.
- **Cleaned** `bonus_stack`: removed category pseudo-techs (Backend, Fullstack, Frontend) and
  group-owned techs (Java, Spring Boot, Node.js, Express). Now: PostgreSQL, Docker, AWS,
  TypeScript, Prisma, Next.js, LLM, Inteligência Artificial.
- **Cleaned** `keywords` (13 → 6 real search terms): `desenvolvedor fullstack, fullstack developer,
  react developer, node.js developer, desenvolvedor java, desenvolvedor .net`.
- **Kept** `required_stack` untouched — the current code still reads it. It is removed only when
  Phase 1 code lands (removing it earlier would make `required_ratio` default to 1.0 and let
  everything through).
- **Kept** `hours_old` in Notion (decision: it is collection config, but living in Notion lets it
  be tuned without touching the server).

## Phase 1 — Fix the funnel (scorer + config + models)

Highest impact, no new sources. Files: `src/scorer.py`, `src/config.py`, `src/models.py`, tests.

### Rules

1. **Stack groups scoring** replaces `required_stack` ratio:
   - `Profile.stack_groups: list[list[str]]` parsed from the Notion text property
     (`|` splits groups, `,` splits technologies).
   - A group is *matched* when at least one of its technologies appears in the job title+description.
   - `required score = 7 × matched_groups / total_groups` (a fullstack job matching both groups
     gets 7; a pure-backend job matching one of two groups gets 3.5 and relies on bonus).
   - `bonus score = 3 × bonus_hits / len(bonus_stack)` (unchanged).
   - Technology matching must be **word-boundary aware** with normalization/synonyms:
     `java` must NOT match `javascript`; `node.js`/`nodejs`/`node` are one tech; `.net`/`dotnet`;
     `c#`/`csharp`. Case-insensitive.
2. **Dealbreakers split by kind** (config stays a single Notion text property; the modality term
   set lives in code):
   - Modality terms (`presencial`, `on-site`, `on site`, `hibrido?`) only veto when the job does
     **not** declare itself remote/hybrid — matched against title + location + `is_remote`
     metadata, never against the description body (benefits sections mention "presencial").
   - All other dealbreakers (techs like PHP, WordPress, Delphi, COBOL) keep matching
     title+description, word-boundary aware.
3. **Modality veto respects the profile**: `is_remote == False` only vetoes when the profile
   accepts *only* `Remoto`. With `Híbrido` in the profile, hybrid jobs pass.
4. **Seniority**:
   - Veto title tokens: `senior`, `sênior`, `sr`, `sr.`, `iii`, `especialista`, `staff`, `lead`,
     `principal` (plus `job_level` values like `mid-senior level` when profile excludes Senior).
   - Positive detection for ranking/annotation: `pleno`, `pl`, `júnior`, `junior`, `jr` in title.
5. **Cleanup**: `Profile.required_stack` removed from models/config; `required_stack` property
   removed from the Notion DB at the end of this phase; CLAUDE.md updated.

### Resolved QA questions (Example Mapping session, 2026-07-05 — all approved by Douglas)

A QA agent mapped Phase 1 and raised 15 blocking questions. Approved resolutions:

1. **Word-boundary algorithm**: plain `\b` fails for `.NET` (starts with `.`) and `C#` (ends
   with `#`). Use alphanumeric lookarounds instead:
   `(?<![a-z0-9])<escaped term>(?![a-z0-9])` over lowercased text.
2. **Synonym dictionary** — small, explicit, hardcoded in scorer; nothing beyond:
   `node.js/nodejs/node`, `.net/dotnet/asp.net`, `c#/csharp`, `react/reactjs`,
   `next.js/nextjs`, `spring/spring boot`, `nest/nestjs`, `llm/llms`.
3. **Empty `stack_groups`** → hard validation error at profile-parse time (broken config must
   scream, not pass everything). Enforce via Pydantic `Field(min_length=1)` on
   `Profile.stack_groups`.
4. **Malformed groups** (`React | | Node`) → empty groups filtered out during parsing in
   `config.py`.
5. **Rounding**: applied once, on the sum `required + bonus`, not per component.
6. **`híbrido` is NOT a modality dealbreaker term.** Hardcoded modality term set:
   `presencial`, `on-site`, `on site` only.
7. **Unified modality veto — single function, this exact order**:
   - if `is_remote is True` OR title/location contains any of
     `remoto/remota/remote/híbrido/hibrido/hybrid/home office` (word-boundary) → job passes,
     no modality veto possible;
   - else veto if a modality term appears in title+location (only when the profile's
     dealbreakers include a modality-kind entry);
   - else veto if `is_remote is False` AND `set(profile.modality) == {"Remoto"}`.
8. **Dealbreaker kind classification by containment**: an entry is modality-kind if any
   hardcoded modality term is a substring of it (covers "trabalho presencial"). All other
   entries are generic and match title+description word-boundary aware.
9. **`profile.modality == []`** → no preference, never vetoes (same pattern as seniority).
10. **Seniority tokenization**: split title on non-alphanumeric (keeping `#`, `+` and accented
    chars), lowercase, exact token membership. `"Sr."` → `sr` ✓, `"SRE"` ≠ `sr` ✓,
    `"(Sr)"` → `sr` ✓. `"PL/SQL"` yields a false "Pleno" signal — accepted (annotation only,
    never vetoes).
11. **Veto wins over positive** when both appear ("Desenvolvedor Pleno Especialista" → veto).
12. **`staff`/`principal`/`lead` false-positive risk accepted**, mitigated by logging every
    veto with its reason (job title + rule) so the first real run can be calibrated.
13. **Intentional behavior reversals — existing tests to be rewritten, not worked around**:
    - `test_mid_senior_job_level_not_vetoed`: `job_level="mid-senior level"` now VETOES when
      the profile excludes Senior.
    - `test_is_remote_false_vetoes`: `is_remote=False` now PASSES when profile accepts Híbrido
      (rule 7); it only vetoes for a Remoto-only profile.
14. **Positive seniority annotation gets a model field**: `ScoredJob.seniority_signal:
    str | None` (values "Pleno"/"Junior"/None), propagated to `EnrichedJob`. The notifier
    prefers `seniority_signal` over raw `job_level` for the Notion "Senioridade" select
    (stops polluting it with "mid-senior level" etc.).
15. **The same word-boundary + synonym matcher applies to `bonus_stack`** (fixes the latent
    java/javascript bug in the bonus path too).

### Additional agreed refactors (ripple of removing `required_stack`)

- Rename `required_hits` → `stack_hits` on `ScoredJob`/`EnrichedJob` (semantics changed).
  Touches: `src/main.py:37`, `src/enricher.py` (`parse_markdown_output`), `src/notifier.py:94`
  (Stack detectada), `scripts/e2e_llm.py`, test fixtures.
- `src/enricher.py` system prompt: "Stack principal" line now renders stack_groups, e.g.
  `', '.join per group, groups joined by ' | '`.
- `src/main.py`: add `logging.basicConfig(level=logging.INFO)` so scorer veto-reason logs
  reach journalctl.
- Veto/discard logging in scorer at INFO level: modality / seniority / dealbreaker / below
  threshold, with job title and company.

### Acceptance reference case

The Venturus job [1277] — title
`"[1277] Pessoa Desenvolvedora Fullstack (.Net C# / React) Pl (Remoto)"`, description with
".NET C#" and "React", benefits text containing "trabalho híbrido ou presencial" — must pass
all vetoes, score ≥ 7.0 (both groups matched) and get `seniority_signal == "Pleno"`.

### Definition of Done (Phase 1)

- New tests written FIRST (TDD), covering every resolution above; full rewrite of
  `tests/test_scorer.py`, updates to `tests/test_config.py` and fixtures in
  `test_enricher.py` / `test_notifier.py` / `test_collector.py`.
- `uv run pytest` green, `uv run ruff check src/` clean.
- `required_stack` property deleted from the Notion Perfil DB **only after** the code lands
  (data source `c01ada18-24e1-4d2f-8ace-57c88a30bd26`); also remove the "legado" line from the
  profile page body.
- CLAUDE.md updated (Fase 3 description, Profile schema table, roadmap).

## Phase 2 — Gupy collector

Public global search API, no auth (verified):
`GET https://employability-portal.gupy.io/api/v1/jobs?jobName=<term>&limit=<n>&offset=<n>`
Returns per job: `name`, `description` (full text), `isRemoteWork`, `city`, `state`, `country`,
`publishedDate`, `applicationDeadline`, `jobUrl`, `careerPageName`, `careerPageUrl`.

- New `src/collectors/gupy.py` (reuses `Job` model; `source="gupy"`).
- Iterate profile keywords; respect `hours_old` by filtering `publishedDate`.
- Company name: inspect payload during implementation (`careerPageName` can be a marketing slogan —
  check for a cleaner company field before mapping).
- Fonte select option "Gupy" already exists in the Vagas DB.

## Phase 3 — InHire collector + Google Jobs

**InHire** (public, per-tenant, verified):
`GET https://api.inhire.app/job-posts/public/pages` with header `X-Tenant: <tenant>`
→ `jobsPage[]`: `jobId`, `displayName`, `workplaceType`, `location`, `status`.

- Tenants come from the new `inhire_tenants` profile property.
- Job description requires a second call per job — confirm the endpoint in the official docs
  (https://docs.inhire.com.br/api/obter-vaga/) during implementation.
- Notion API auto-creates the "InHire" Fonte option on first write.

**Google Jobs via JobSpy**: add `site_name=["google"]` pass with `google_search_term` (requires
the exact Google Jobs search syntax — one term per profile keyword + "vagas brasil"). Google
indexes ATS-hosted jobs (Gupy, InHire, Greenhouse, Lever), acting as a free meta-aggregator.

## Phase 4 — Distribution (GitHub)

- README.md (English) with: what it is, architecture diagram, Notion template setup
  (duplicable template page), `.env` reference, systemd install, cost notes (Haiku ~$4/mo).
- Review `.env.example` completeness.
- License (MIT) + repository metadata.
- Optional: `scripts/setup.py` or a documented checklist to validate Notion schema on first run.

## Decisions log

- **Stack groups over LLM-only gating** — Haiku judging every scraped job costs tokens and floods
  Notion; keyword groups keep the cheap filter but model a multi-stack candidate correctly.
- **`hours_old` stays in Notion** — it is collection config, not identity, but Notion-side tuning
  beats server access.
- **Modality dealbreaker term set hardcoded in scorer** — avoids a second Notion property; the
  Notion `dealbreakers` text stays a single list.
