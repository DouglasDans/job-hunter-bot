# Notion Setup

This project reads its configuration from a **Perfil** database and writes results to a **Vagas**
database in your own Notion workspace. Two public templates are provided so you don't have to
build the schema from scratch.

## 1. Duplicate the templates

- [Perfil — Job Hunter Config (template)](https://cuddly-minute-3cc.notion.site/39527b83275c80679fe1f8140034e29a?v=49327b83275c83cebe0188864f0cd464)
- [Vagas — Job Hunter Config (template)](https://cuddly-minute-3cc.notion.site/39527b83275c8079b4c0fbd8823e6172?v=88127b83275c83789ee908292ed0d2c9)

Open each link and click **Duplicate** (top right) to copy it into your own workspace.

## 2. Create a Notion integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations) (Notion's developer
   portal).
2. Create a new internal connection, scoped to the workspace you duplicated the templates into.
3. Open its **Configuration** tab and copy the token — this is your `NOTION_TOKEN`.

## 3. Share both databases with the integration

For each of the two duplicated databases:

1. Open the database as a full page.
2. Click the **"•••"** menu (top right).
3. Click **Add connections** and select the integration you just created.

Without this step, the integration returns an "object not found" error even with a valid token —
Notion integrations only see pages/databases explicitly shared with them.

## 4. Get the database IDs

Open each database in the browser and copy the 32-character ID from the URL:

```
https://www.notion.so/<workspace>/<DATABASE_ID>?v=...
```

Set in `.env`:

- `NOTION_PROFILE_DATABASE_ID` → Perfil database ID
- `NOTION_VAGAS_DATABASE_ID` → Vagas database ID

## 5. Fill in your Perfil row

The Perfil database ships with one empty row. Open it and fill in:

| Property        | Type         | Example                                                              |
| --------------- | ------------ | --------------------------------------------------------------------- |
| keywords        | Text         | "desenvolvedor fullstack, react developer"                            |
| location        | Text         | "Brazil"                                                               |
| stack_groups    | Text         | "React, Angular, Next.js \| Node.js, NestJS, Java, Spring, .NET, C#" |
| bonus_stack     | Multi-select | PostgreSQL, Docker, AWS                                                |
| seniority       | Select       | Senior / Pleno / Junior                                               |
| modality        | Select       | Remoto / Híbrido / Presencial                                         |
| dealbreakers    | Text         | "PHP, Delphi, gestão de equipe"                                       |
| score_threshold | Number       | 6.0                                                                    |
| hours_old       | Number       | 24                                                                     |
| inhire_tenants  | Text         | "venturus"                                                            |

`stack_groups`: groups separated by `|`, technologies within a group separated by `,`. Models a
multi-stack candidate — e.g. accepts Node **or** Java **or** .NET, as long as it also has React.
An empty group (`"React | | Node"`) is dropped; if none remain, the profile fails validation on
purpose, since a broken config should stop the pipeline, not silently let everything through.

`inhire_tenants`: comma-separated InHire subdomains to poll (e.g. `"venturus, outra_empresa"`).
Leave blank to skip the InHire collector entirely.

Also write free text in the **page body** — this becomes `about_me`, injected into every LLM
prompt. Describe your background, experience, values and what you're looking for in a company;
the more detail, the more personalized the analysis.

## Done

Run `uv run python -m src.main` — the pipeline reads Perfil, collects/scores/enriches jobs, and
writes the results to Vagas.
