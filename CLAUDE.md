# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Script Python de execução única que agrega vagas de múltiplas fontes, filtra por keyword matching, pesquisa informações externas sobre empresas e enriquece com IA (Anthropic Haiku) as vagas relevantes, gravando o resultado no Notion (DB "Vagas"). Disparado por systemd timer ~2x/dia — não daemon, sem estado em memória entre execuções.

## Stack

- Python 3.12+ com `uv` para gerenciamento de dependências
- `jobspy` — coleta multi-fonte (Indeed principal, LinkedIn guest secundário)
- `httpx` — cliente HTTP do coletor Gupy (API pública, sem autenticação)
- `notion-client` — SDK oficial Python para leitura do perfil e escrita no DB Vagas
- `pydantic` — validação e parsing de todos os dados do pipeline
- `python-dotenv` — tokens via `.env`
- `anthropic` SDK — Haiku como LLM primary (análise de vagas)
- `ddgs` — pesquisa web de empresa via DuckDuckGo (sem API key)
- Ollama REST API local (`http://localhost:11434`) — fallback do LLM
- systemd `--user` service + timer — orquestração

## Comandos essenciais

```bash
uv run python -m src.main        # execução manual completa do pipeline
uv run python scripts/e2e_llm.py # e2e rápido: uma vaga fake → LLM → Notion
uv run pytest                    # todos os testes
uv run pytest tests/test_scorer.py  # teste específico
uv run ruff check src/           # lint
uv run ruff format src/          # formatação
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
│   ├── config.py         # lê página de perfil do Notion → Profile (props + corpo da página)
│   ├── collectors/
│   │   ├── jobspy.py     # wrapper JobSpy (Indeed/LinkedIn) → list[Job]
│   │   └── gupy.py       # API pública Gupy → list[Job]
│   ├── scorer.py         # keyword matching → Job com score
│   ├── dedup.py          # busca URLs existentes no DB Vagas
│   ├── researcher.py     # pesquisa web (ddgs) → contexto sobre a empresa
│   ├── enricher.py       # LLM: monta prompt, valida output → EnrichedJob
│   ├── notifier.py       # cria página no DB Vagas com conteúdo rico em blocos Notion
│   ├── models.py         # todos os modelos Pydantic (Profile, Job, EnrichedJob)
│   └── llm/
│       ├── client.py     # LLMClient: interface base
│       ├── ollama.py     # OllamaClient
│       ├── anthropic.py  # AnthropicClient (primary)
│       └── fallback.py   # FallbackClient: primary → fallback em runtime
├── scripts/
│   └── e2e_llm.py        # teste e2e com vaga fake
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
         → Profile(keywords, location, stack_groups, bonus_stack,
                   seniority, modality, dealbreakers, score_threshold,
                   hours_old, about_me)
         → about_me: corpo livre da página de Perfil no Notion (texto corrido)
  ↓
Fase 1: Coleta vagas via JobSpy + Gupy
         → Indeed (principal) + LinkedIn guest (secundário, rate limit na pág. 10)
         → Gupy: API pública sem autenticação, uma chamada por keyword; resultados vêm
           ordenados por data desc, então o filtro de hours_old para na primeira vaga
           fora da janela em vez de paginar; falha de rede numa keyword loga WARNING e
           não derruba as outras fontes
  ↓
Fase 2: Dedup — busca URLs normalizadas no DB Vagas, descarta existentes
  ↓
Fase 3: Score por keyword matching (Python puro, sem IA)
         → stack_groups: candidato multi-stack (ex.: Frontend | Backend). Um grupo é
           "matched" se qualquer tecnologia do grupo aparece na vaga.
           score = 7 × grupos_matched/total_grupos + 3 × bonus_hits/len(bonus_stack)
         → matching word-boundary aware com sinônimos (node.js/nodejs/node, .net/dotnet,
           c#/csharp, etc.) — evita falso positivo tipo "java" casando em "javascript"
         → dealbreakers: termos de modalidade (presencial/on-site) só vetam via
           título+localização (nunca a descrição); demais dealbreakers vetam
           título+descrição, também word-boundary aware
         → veto de modalidade respeita o perfil: `is_remote=False` só veta se o
           perfil aceitar só "Remoto"; título/location com remoto/híbrido nunca veta
         → veto de senioridade por tokens do título (sr, iii, especialista, staff,
           lead, principal, senior/sênior) quando "Senior" não está no perfil;
           sinal positivo (Pleno/Junior) anotado em `ScoredJob.seniority_signal`
         → descarta score < profile.score_threshold
         → todo veto é logado em INFO (motivo + título + empresa)
  ↓
Fase 4: Pesquisa de empresa via DuckDuckGo (best-effort, falha silenciosa)
         → 2 queries × 3 resultados = até 6 snippets sobre a empresa
         → company_context: string passada ao LLM junto com a descrição da vaga
  ↓
Fase 5: Enriquecimento via LLM (Haiku primary, Ollama fallback)
         → system prompt: about_me do candidato + resumo técnico do perfil
         → user prompt: descrição da vaga + company_context
         → output Markdown validado com Pydantic:
           { plano_de_acao, o_que_estudar, sinais_de_cultura, red_flags,
             perguntas_provaveis, resumo_empresa, analise_empresa,
             fit_cultural, match_score }
         → match_score: 0.0–10.0, uma casa decimal (avaliação de compatibilidade real)
  ↓
Fase 6: Push pro Notion DB Vagas
         → propriedades estruturadas + corpo da página em blocos Notion
         → Score no Notion = match_score (não o score de keyword)
         → corpo parseado de Markdown → blocos Notion tipados
  ↓
Encerra
```

## Notion setup

IDs criados (usar no `.env`):
- **Perfil DB**: `8d3a581b39a748518552701ba09b3e23` → https://app.notion.com/p/8d3a581b39a748518552701ba09b3e23
- **Vagas DB**: `605ffabb4d76486c9996b0b33f28d7e2` → https://app.notion.com/p/605ffabb4d76486c9996b0b33f28d7e2

### Database Perfil (config)
Database com uma única linha (o perfil). Propriedades:

| Propriedade | Tipo Notion | Exemplo |
|---|---|---|
| keywords | Text | "React developer, frontend engineer" |
| location | Text | "Brazil" |
| stack_groups | Text | "React, Angular, Next.js \| Node.js, NestJS, Java, Spring, .NET, C#" |
| bonus_stack | Multi-select | PostgreSQL, Docker, AWS |
| seniority | Select | Senior / Pleno / Junior |
| modality | Select | Remoto / Híbrido / Presencial |
| dealbreakers | Text | "PHP, Delphi, gestão de equipe" |
| score_threshold | Number | 6.0 |
| hours_old | Number | 24 |

`stack_groups`: grupos separados por `|`, tecnologias dentro do grupo separadas por `,`. Modela um
candidato multi-stack (ex.: aceita Node **ou** Java **ou** .NET, desde que tenha React). Grupos
vazios após o parse (`"React | | Node"`) são descartados; se restar zero grupos, `Profile` falha a
validação (Pydantic `min_length=1`) — config quebrada deve travar, não deixar tudo passar.

**Corpo da página** (texto livre): usado como `about_me` no system prompt do LLM. Descreva seu background, experiências, valores e o que busca em uma empresa. Quanto mais detalhado, mais personalizada a análise.

### DB Vagas
| Propriedade | Tipo Notion | Observação |
|---|---|---|
| Nome | Title | |
| Empresa | Text | |
| URL | URL | |
| Fonte | Select (Indeed / LinkedIn / Greenhouse / Lever / Gupy) | |
| Status | Select (Não Inscrito / Inscrito / Aguardando / Etapas Pendentes / Finalizado) | default: Não Inscrito |
| Score | Number | match_score da IA (0–10), não o score de keyword |
| Stack detectada | Multi-select | |
| Senioridade | Select | |
| Modalidade | Select | |
| Localização | Text | |
| Data da vaga | Date | |
| Salário | Text | |

Corpo da página: 8 seções geradas pelo LLM em Markdown, convertidas para blocos Notion tipados. Emojis por convenção: ✅ em Sinais de Cultura, 🚩 para red flags críticos, 🟠 para red flags secundários.

## LLM — configuração

```env
NOTION_TOKEN=secret_...
NOTION_PROFILE_DATABASE_ID=8d3a581b39a748518552701ba09b3e23
NOTION_VAGAS_DATABASE_ID=605ffabb4d76486c9996b0b33f28d7e2

# Se ANTHROPIC_API_KEY estiver presente: Haiku primary, Ollama fallback em runtime
# Se ausente: só Ollama
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_BASE_URL=http://localhost:11434
```

## Seções do corpo da vaga no Notion

| Campo | Descrição |
|---|---|
| Plano de Ação | Passos concretos e personalizados baseados no perfil do candidato; quando há bom fit, inclui abordagem direta no LinkedIn (quem contatar + exemplo de mensagem) |
| O que Estudar | Lacunas específicas na stack antes de aplicar |
| Sinais de Cultura | Evidências positivas de cultura e ambiente de trabalho (✅ por item) |
| Red Flags | Alertas e aspectos negativos identificados (🚩 críticos, 🟠 secundários) |
| Perguntas Prováveis | Perguntas técnicas e comportamentais esperadas na entrevista |
| Resumo da Empresa | Contexto sobre produto e mercado |
| Análise da Empresa | Histórico, reputação e benefícios com base em dados externos |
| Fit Cultural | Avaliação de compatibilidade entre empresa e valores do candidato |

## Decisões arquiteturais

**JobSpy Python direto** — ts-jobspy tem maintainer único (632 downloads/semana). A biblioteca Python original tem vários maintainers e é muito mais estável.

**Scoring por keyword, não IA** — keyword matching filtra ruído antes de gastar tokens. IA só onde agrega valor real: o enriquecimento. O score de keyword não aparece no Notion — apenas o `match_score` gerado pela IA.

**Stack groups em vez de ratio sobre `required_stack`** — um candidato multi-stack (Node **ou**
Java **ou** .NET) não deveria ser penalizado por não citar as três. Cada grupo é matched se
qualquer tecnologia do grupo aparece na vaga; a nota é proporcional a grupos matched, não a itens
individuais. Alternativa descartada: gating só via LLM — mais caro em tokens e não resolve o
problema de custo/ruído que o keyword matching já resolve bem.

**Matcher word-boundary com sinônimos hardcoded no scorer** — regex com lookaround alfanumérico
(`(?<![a-z0-9])termo(?![a-z0-9])`) em vez de `\b` puro, porque `\b` falha em termos que começam ou
terminam com caractere não-alfanumérico (`.NET`, `C#`). Sinônimos (`node.js/nodejs/node`,
`.net/dotnet/asp.net`, `c#/csharp`, `react/reactjs`, `next.js/nextjs`, `spring/spring boot`,
`nest/nestjs`, `llm/llms`) são uma lista pequena e explícita — nada além disso, YAGNI.

**Veto de modalidade não olha a descrição** — vagas remotas frequentemente citam "trabalho
presencial" na seção de benefícios (auxílio mobilidade híbrido/presencial). Vetar por isso mataria
vagas boas. O veto de modalidade só olha título + localização + `is_remote`; a descrição nunca é
usada para decidir modalidade.

**`seniority_signal` como campo separado, não sobrescreve `job_level`** — o `job_level` bruto do
JobSpy (ex. "mid-senior level") é ruído para exibição. `seniority_signal` é uma anotação derivada
do título (Pleno/Junior/None) usada só para preencher "Senioridade" no Notion de forma mais limpa;
nunca influencia o veto, que já aconteceu antes dela ser calculada.

**match_score ≠ score de keyword** — o score de keyword (0–10) é usado só como filtro interno (threshold). O `match_score` que aparece no Notion é a avaliação da IA sobre compatibilidade real entre candidato e vaga, incorporando perfil, cultura e stack.

**about_me via corpo da página do Notion** — campo de texto livre na página do Perfil (não uma propriedade). Permite atualizar o contexto pessoal sem alterar o schema do DB.

**Pesquisa de empresa best-effort** — `research_company` usa `ddgs` (DuckDuckGo, sem API key). Se falhar (rede, rate limit), retorna `""` silenciosamente e o enriquecimento continua sem contexto externo.

**Haiku primary, Ollama fallback em runtime** — se a chamada ao Anthropic falhar, `FallbackClient` tenta o Ollama. A troca é automática e logada. O `ANTHROPIC_MODEL` é separado do `OLLAMA_MODEL` para evitar enviar modelo errado à API errada.

**Prefill `{` no Anthropic** — quando `response_schema` é fornecido, o `AnthropicClient` usa prefill de assistant com `{` para garantir JSON puro sem markdown wrapper. O `{` é re-prefixado na resposta antes do parse.

**Markdown → blocos Notion** — o LLM gera Markdown em cada campo. O `notifier` converte linha a linha: `## heading` → `heading_2`, `- item` → `bulleted_list_item`, `1. item` → `numbered_list_item`, `**bold**` → annotation bold, `---` → divider. Blocos são paginados em batches de 100 (limite da API).

**Abstração LLMClient** — Ollama local por padrão (gratuito). Anthropic Haiku quando configurado. Custo estimado com Haiku: ~$4/mês nesse volume.

**Sem login no LinkedIn** — ToS seção 8.2. LinkedIn via JobSpy usa guest API pública; rate limit a partir da página 10, tratado como fonte secundária.

**API REST do Notion, não MCP** — `notion-client` com token de integração interna. Query SQL via MCP exige plano Enterprise.

**notion-client v3: `databases.query()` foi removido** — query agora exige dois calls: `databases.retrieve()` para obter o `data_source_id`, depois `data_sources.query(data_source_id)`. O `.env` continua usando `database_id` (visível na URL do Notion); a resolução para `data_source_id` é feita internamente em `load_profile`.

**URL normalizada no dedup** — URLs do LinkedIn variam por query params. Strip de parâmetros antes de comparar.

**systemd --user, ~2x/dia** — frequência baixa mantém coleta discreta e reflete que vagas não mudam de hora em hora.

**`src/collectors/` como pacote** — ao adicionar a Gupy (Fase 2), `collector.py` foi renomeado para
`collectors/jobspy.py` para não ter um padrão solto convivendo com um pacote; a Fase 3 (InHire) usa
o mesmo pacote, evitando decidir a estrutura de novo a cada fonte nova.

**Gupy via `httpx`, API pública sem chave** — `GET employability-portal.gupy.io/api/v1/jobs?jobName=<termo>`
não exige autenticação. Resultados vêm ordenados por `publishedDate` desc, então o filtro de
`hours_old` para de processar a página assim que encontra a primeira vaga fora da janela, sem
precisar paginar `offset` além da primeira página na maioria dos casos. `careerPageName` é usado
como nome da empresa — validado com múltiplas keywords reais, sempre nome real (não slogan de
marketing). `httpx` virou dependência direta (antes só transitiva via `notion-client`) por ser mais
explícito que depender de uma lib que não está no `pyproject.toml`.

## Roadmap — stories

| # | Story | Status |
|---|---|---|
| 1 | Setup + leitura do perfil do Notion | ✅ |
| 2 | Coleta + scoring por keyword | ✅ |
| 3 | Dedup contra DB Vagas | ✅ |
| 4 | Enriquecimento via Ollama | ✅ |
| 5 | Push pro Notion DB Vagas | ✅ |
| 6 | Orquestração systemd | pendente |
| 7 | Haiku primary, Ollama runtime fallback | ✅ |
| 8 | Perfil pessoal via corpo da página do Notion (`about_me`) | ✅ |
| 9 | Pesquisa de empresa + análise de fit + match_score real | ✅ |

Melhorias pós-story-9 (assertividade e cobertura do funil) estão detalhadas em
`docs/improvement-plan.md`. Fase 1 (scorer/config/models — stack_groups, veto de modalidade e
senioridade, matcher word-boundary) e Fase 2 (coletor Gupy) estão implementadas e testadas. Falta
a Fase 3 (coletor InHire + Google Jobs via JobSpy) e a Fase 4 (distribuição no GitHub).

## Definition of Done do projeto

- `uv run python -m src.main` completa sem erro
- Vagas novas aparecem no DB Vagas com match_score, stack detectada e todas as 8 seções
- Vagas duplicadas são descartadas silenciosamente
- Vagas abaixo do threshold não chegam ao Notion
- systemd timer dispara e gera logs legíveis no journalctl
- Nenhum `print` de debug no código final

## Referências

- Notion spec: https://app.notion.com/p/38627b83275c80789dbbc529efd2553a
- JobSpy (Python): https://github.com/speedyapply/JobSpy
- notion-client Python: https://github.com/ramnes/notion-sdk-py
