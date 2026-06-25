# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Script Python de execução única que agrega vagas de múltiplas fontes, filtra por keyword matching e enriquece com IA local (Ollama) as vagas relevantes, gravando o resultado no Notion (DB "Vagas"). Disparado por systemd timer ~2x/dia — não daemon, sem estado em memória entre execuções.

## Stack

- Python 3.12+ com `uv` para gerenciamento de dependências
- `jobspy` — coleta multi-fonte (Indeed principal, LinkedIn guest secundário)
- `notion-client` — SDK oficial Python para leitura do perfil e escrita no DB Vagas
- `pydantic` — validação e parsing de todos os dados do pipeline
- `python-dotenv` — token do Notion via `.env`
- Ollama REST API local (`http://localhost:11434`) — enriquecimento com Qwen2.5 7B ou Llama 3.1 8B
- systemd `--user` service + timer — orquestração

## Comandos essenciais

```bash
uv run python -m src.main   # execução manual completa do pipeline
uv run pytest               # todos os testes
uv run pytest tests/test_scorer.py  # teste específico
uv run ruff check src/      # lint
uv run ruff format src/     # formatação
```

Logs da execução agendada:
```bash
journalctl --user -u job-hunter -f
```

## Estrutura de pastas

```
job-hunter-bot/
├── src/
│   ├── main.py           # entry point — orquestra as fases em sequência
│   ├── config.py         # lê página de perfil do Notion → Profile
│   ├── collector.py      # wrapper JobSpy → list[Job]
│   ├── scorer.py         # keyword matching → Job com score
│   ├── dedup.py          # busca URLs existentes no DB Vagas
│   ├── enricher.py       # LLM: monta prompt, valida output → EnrichedJob
│   ├── notifier.py       # cria página no DB Vagas com conteúdo rico
│   ├── models.py         # todos os modelos Pydantic (Profile, Job, EnrichedJob)
│   └── llm/
│       ├── client.py     # LLMClient: interface base (troca Ollama ↔ Anthropic via .env)
│       ├── ollama.py     # OllamaClient
│       └── anthropic.py  # AnthropicClient (fallback futuro)
├── tests/
├── systemd/
│   ├── job-hunter.service
│   └── job-hunter.timer
├── .env.example
├── pyproject.toml
└── CLAUDE.md
```

## Arquitetura — fases de execução

O script é uma função pura que roda e morre. Cada execução percorre estas fases em sequência:

```
Fase 0: Lê perfil/config da página do Notion
         → Profile(keywords, location, required_stack, bonus_stack,
                   seniority, modality, dealbreakers, score_threshold, hours_old)
  ↓
Fase 1: Coleta vagas via JobSpy
         → Indeed (principal) + LinkedIn guest (secundário, rate limit na pág. 10)
         → usa keywords, location, hours_old do perfil
  ↓
Fase 2: Dedup — busca URLs normalizadas no DB Vagas, descarta existentes
  ↓
Fase 3: Score por keyword matching (Python puro, sem IA)
         → required_stack: peso 70% | bonus_stack: peso 30%
         → dealbreaker presente: veto imediato (score = 0)
         → descarta score < profile.score_threshold
  ↓
Fase 4: Enriquecimento via LLM (Ollama local)
         → por vaga: system prompt = perfil, user prompt = descrição da vaga
         → output validado com Pydantic: { plano_de_acao, o_que_estudar,
                                           sinais_de_cultura, red_flags,
                                           perguntas_provaveis, resumo_empresa }
  ↓
Fase 5: Push pro Notion DB Vagas
         → propriedades estruturadas + conteúdo rico da IA como blocos da página
  ↓
Encerra
```

## Notion setup

IDs criados (usar no `.env`):
- **Perfil DB**: `8d3a581b39a748518552701ba09b3e23` → https://app.notion.com/p/8d3a581b39a748518552701ba09b3e23
- **Vagas DB**: `605ffabb4d76486c9996b0b33f28d7e2` → https://app.notion.com/p/605ffabb4d76486c9996b0b33f28d7e2

Para conectar a integração: abrir cada database no Notion → `...` → **Connections** → adicionar a integração criada em notion.so/my-integrations.

### Database Perfil (config)
Database com uma única linha (o perfil). O script faz `query` e pega o primeiro resultado. Propriedades:

| Propriedade | Tipo Notion | Exemplo |
|---|---|---|
| keywords | Text | "React developer, frontend engineer" |
| location | Text | "Brazil" |
| required_stack | Multi-select | React, TypeScript, Node.js |
| bonus_stack | Multi-select | PostgreSQL, Docker, AWS |
| seniority | Select | Senior / Pleno / Junior |
| modality | Select | Remoto / Híbrido / Presencial |
| dealbreakers | Text | "PHP, Delphi, gestão de equipe" |
| score_threshold | Number | 6.0 |
| hours_old | Number | 24 |

### DB Vagas
| Propriedade | Tipo Notion |
|---|---|
| Nome | Title |
| Empresa | Text |
| URL | URL |
| Fonte | Select (Indeed / LinkedIn / Greenhouse / Lever / Gupy) |
| Status | Select (Inbox / Triagem / Aplicado / Descartado) |
| Score | Number |
| Stack detectada | Multi-select |
| Senioridade | Select |
| Modalidade | Select |
| Localização | Text |
| Data da vaga | Date |
| Salário | Text |

O conteúdo da página (body) é gerado pelo LLM: plano de ação, o que estudar, sinais de cultura, perguntas prováveis, resumo da empresa.

## LLM — troca de provider

Configurado via `.env`. Sem mudança de código:

```env
# Notion
NOTION_TOKEN=secret_...
NOTION_PROFILE_DATABASE_ID=8d3a581b39a748518552701ba09b3e23
NOTION_VAGAS_DATABASE_ID=605ffabb4d76486c9996b0b33f28d7e2

# LLM
LLM_PROVIDER=ollama          # ou "anthropic"
LLM_MODEL=qwen2.5:7b         # ou "claude-haiku-4-5-20251001"
OLLAMA_BASE_URL=http://localhost:11434
ANTHROPIC_API_KEY=           # só necessário se LLM_PROVIDER=anthropic
```

## Decisões arquiteturais

**JobSpy Python direto** — ts-jobspy tem maintainer único (632 downloads/semana). A biblioteca Python original tem vários maintainers e é muito mais estável.

**Scoring por keyword, não IA** — para 5-10 vagas/rodada onde o usuário revisa tudo no Notion de qualquer forma, keyword matching é suficiente para reduzir ruído. IA só onde agrega valor real: o enriquecimento.

**LLM apenas no enriquecimento** — IA não é filtro, é análise. Roda só nas vagas que passaram o score, gerando plano de ação, o que estudar, sinais de cultura e resumo da empresa.

**Abstração LLMClient** — Ollama local por padrão (gratuito, RX 9060 XT com ROCm 7.1). Anthropic Haiku como fallback via `.env`, sem mudança de código. Custo estimado com Haiku: ~$4/mês nesse volume.

**Sem login no LinkedIn** — ToS seção 8.2. LinkedIn via JobSpy usa guest API pública; rate limit a partir da página 10, tratado como fonte secundária.

**API REST do Notion, não MCP** — `notion-client` com token de integração interna. Query SQL via MCP exige plano Enterprise.

**notion-client v3: `databases.query()` foi removido** — query agora exige dois calls: `databases.retrieve()` para obter o `data_source_id`, depois `data_sources.query(data_source_id)`. O `.env` continua usando `database_id` (visível na URL do Notion); a resolução para `data_source_id` é feita internamente em `load_profile`.

**URL normalizada no dedup** — URLs do LinkedIn variam por query params. Strip de parâmetros antes de comparar.

**systemd --user, ~2x/dia** — frequência baixa mantém coleta discreta e reflete que vagas não mudam de hora em hora.

## Roadmap — stories

| # | Story | Critério de aceite |
|---|---|---|
| 1 | Setup + leitura do perfil do Notion | `uv run python -m src.main` imprime `Profile` lido sem erro |
| 2 | Coleta + scoring por keyword | Lista de vagas com score calculado no stdout |
| 3 | Dedup contra DB Vagas | Vagas já existentes descartadas, URLs normalizadas |
| 4 | Enriquecimento via Ollama | `EnrichedJob` válido impresso no stdout por vaga |
| 5 | Push pro Notion DB Vagas | Vaga aparece no Notion com propriedades + conteúdo rico |
| 6 | Orquestração systemd | Timer ativo, `journalctl --user -u job-hunter` mostra log |

## Definition of Done do projeto

- `uv run python -m src.main` completa sem erro
- Vagas novas aparecem no DB Vagas com score, stack detectada e plano de ação
- Vagas duplicadas são descartadas silenciosamente
- Vagas abaixo do threshold não chegam ao Notion
- systemd timer dispara e gera logs legíveis no journalctl
- Nenhum `print` de debug no código final

## Referências

- Notion spec: https://app.notion.com/p/38627b83275c80789dbbc529efd2553a
- JobSpy (Python): https://github.com/speedyapply/JobSpy
- notion-client Python: https://github.com/ramnes/notion-sdk-py
