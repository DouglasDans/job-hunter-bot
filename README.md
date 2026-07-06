# Job Hunter Bot

A one-shot Python pipeline that aggregates job postings from multiple sources, filters them by
keyword/stack matching, researches the hiring company, and uses an LLM (Anthropic Haiku, with a
local Ollama fallback) to write a tailored analysis for each relevant job straight into a Notion
database.

Not a daemon — no in-memory state between runs. Meant to be triggered on a schedule (a systemd
timer is included) so a fresh batch of leads is waiting in Notion instead of a live dashboard to
babysit.

## Architecture

```
Phase 0 — Read profile/config from a Notion page
Phase 1 — Collect jobs: JobSpy (Indeed, LinkedIn guest, Google Jobs) + Gupy + InHire
Phase 2 — Dedup against URLs already in the Notion Vagas database
Phase 3 — Score by keyword/stack matching (pure Python, no LLM)
Phase 4 — Research the hiring company (DuckDuckGo, best-effort)
Phase 5 — Enrich via LLM: plan of action, gaps to study, culture signals, red flags,
          likely interview questions, company analysis, cultural fit, match score
Phase 6 — Push the enriched job to the Notion Vagas database
```

Keyword scoring is cheap and runs on every scraped job to cut noise before spending LLM tokens;
the LLM only sees jobs that already cleared the filter. See `CLAUDE.md` for the full rationale
behind each phase and the architectural decisions log.

## Setup

### 1. Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A Notion account (free tier works)
- Optional: [Ollama](https://ollama.com/) running locally, for zero-cost LLM enrichment instead
  of Anthropic

### 2. Clone & install

```bash
git clone https://github.com/DouglasDans/job-hunter-bot.git
cd job-hunter-bot
uv sync
```

### 3. Notion setup

Two public templates are provided — duplicate them into your own workspace and connect them to a
Notion integration. Full walkthrough: [docs/notion-setup.md](docs/notion-setup.md).

- [Perfil — Job Hunter Config (template)](https://cuddly-minute-3cc.notion.site/39527b83275c80679fe1f8140034e29a?v=49327b83275c83cebe0188864f0cd464)
- [Vagas — Job Hunter Config (template)](https://cuddly-minute-3cc.notion.site/39527b83275c8079b4c0fbd8823e6172?v=88127b83275c83789ee908292ed0d2c9)

### 4. Configure `.env`

```bash
cp .env.example .env
```

| Variable                      | Required | Notes                                                        |
| ----------------------------- | -------- | -------------------------------------------------------------- |
| `NOTION_TOKEN`                | yes      | from your Notion integration                                  |
| `NOTION_PROFILE_DATABASE_ID`  | yes      | Perfil database ID                                             |
| `NOTION_VAGAS_DATABASE_ID`    | yes      | Vagas database ID                                              |
| `ANTHROPIC_API_KEY`           | no       | if set, Haiku becomes primary LLM; Ollama becomes runtime fallback |
| `ANTHROPIC_MODEL`             | no       | default `claude-haiku-4-5-20251001`                            |
| `OLLAMA_MODEL`                | no       | default `qwen2.5:7b`                                            |
| `OLLAMA_BASE_URL`             | no       | default `http://localhost:11434`                               |

Without `ANTHROPIC_API_KEY`, the pipeline runs entirely on a local Ollama instance — no external
LLM cost.

### 5. Run once

```bash
uv run python -m src.main
```

### 6. Schedule with systemd (optional)

Unit files live in `systemd/`, set to run weekly on Fridays at 20:00:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/job-hunter.service systemd/job-hunter.timer ~/.config/systemd/user/
# if you didn't clone into ~/job-hunter-bot, edit WorkingDirectory in job-hunter.service first
systemctl --user daemon-reload
systemctl --user enable --now job-hunter.timer
journalctl --user -u job-hunter -f   # watch logs
```

## Cost

- Ollama only: free (local inference).
- With Anthropic Haiku as primary: roughly $4/month at a weekly run cadence — Haiku is only
  called for jobs that already passed the keyword/stack filter, not every scraped listing.

## Development

```bash
uv run pytest            # tests
uv run ruff check src/   # lint
uv run ruff format src/  # format
```

## License

MIT — see [LICENSE](LICENSE).
