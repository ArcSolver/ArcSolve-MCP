# ArcSolve-Kit

> **English** · [한국어](README.ko.md)

[![CI](https://github.com/ArcSolver/ArcSolve-Kit/actions/workflows/ci.yml/badge.svg)](https://github.com/ArcSolver/ArcSolve-Kit/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

> **Capabilities verified against official API contracts, bundled in two formats.**

- **MCP service** — one MCP server composes many services and exposes them as *runtime
  tools*. A service = **one folder = a contract + its tools**.
- **Skill** — a file artifact that teaches Claude *how to use those tools well*. A skill
  = **one folder = a `SKILL.md`**.

The verified contract (`contract.py`) stays the single source of truth on the MCP side,
and a skill orchestrates those tools on top of it.

## Why

Shipping a product, three things stay needlessly hard: (1) wiring up messaging/chat
— notifications and bots — across SNS platforms that each have their own API, auth,
and message format; (2) pulling in outside information to research a topic, different
for every source; and (3) managing both from **one consistent place**, which almost
no tool does. ArcSolve-Kit removes that friction by exposing public API **contracts**
as uniform MCP tools.

## Vision

MCP-ify public contracts so that **models** can reach many products through one
consistent interface — and so that **open-source agentic-workflow developers** can
assemble our MCPs like building blocks and ship the service they want, fast.

## Roadmap

1. **Multilingual** — tool descriptions, docs, and messages in multiple languages.
2. **More services** — keep widening beyond messaging, academic, and productivity.
3. **Consistent, contract-based growth** — every service follows the same shape
   (*one folder = contract + tools*). That uniformity is ideal for an **AI maintainer**
   to extend, so we grow the catalog with **Codex (ChatGPT) as the primary maintainer**.
   (Design: [docs/architecture.md](docs/architecture.md); agent rules: [AGENTS.md](AGENTS.md).)

## Structure

```
ArcSolve-Kit/
├── pyproject.toml
├── AGENTS.md                 # Shared working rules for every agent (single source of truth)
├── CHANGELOG.md              # Assembled from changelog.d/ fragments
├── changelog.d/              # Changelog fragments (one per service, no parallel conflicts)
├── arcsolve/                 # Shared framework
│   ├── server.py             #   Composes enabled services into one FastMCP
│   ├── service.py            #   Service = the uniform contract every service implements
│   ├── skill.py              #   Skill = the uniform contract for skills + skills/ auto-discovery
│   ├── http.py               #   Shared HTTP calls + error mapping
│   ├── oauth.py              #   Generic OAuth2 (authcode + refresh) + token store
│   ├── catalog.py            #   Registry → auto-generates docs/services.md + docs/skills.md
│   ├── changelog.py          #   changelog.d/ → assembles CHANGELOG.md
│   ├── __main__.py           #   Entry point (serve / list / skills / auth / catalog / changelog)
│   └── services/             # ★ One folder per service (flat, auto-discovered)
│       ├── __init__.py       #   Registry (auto-scans services/ — no manual edits)
│       └── kakao/
│           ├── contract.py   #   ← Contract: endpoints, scopes, request/response models
│           ├── tools.py      #   MCP tools (thin wrappers that call the contract)
│           └── README.md     #   Service guide (setup, limits, official-doc links)
├── skills/                   # ★ One folder per skill (auto-discovered, data tree)
│   └── academic-discovery/
│       ├── SKILL.md          #   frontmatter (name·description·allowed-tools) + workflow
│       └── README.md         #   Skill guide + contract sources + required MCP tools
├── docs/                     # Cross-cutting docs (fixed regardless of service/skill count)
│   ├── architecture.md
│   ├── adding-a-service.md
│   ├── adding-a-skill.md
│   ├── providers.md          #   Implementation manifest (bundle of official-doc links)
│   ├── services.md           #   Auto-generated catalog (MCP tools)
│   └── skills.md             #   Auto-generated catalog (skills)
└── tests/
```

Design principle: **physically separate the contract (`contract.py`) from the tools
(`tools.py`)** → services stay clearly delineated while the structure stays uniform,
and the code itself proves this is an "official-API-contract-based, self-built client."

## Quick start

```bash
# 1) Install
uv pip install -e ".[dev]"      # or: pip install -e ".[dev]"

# 2) Credentials (see .env.example)
cp .env.example .env            # fill in KAKAO_REST_API_KEY, etc.

# 3) One-time Kakao auth → store refresh_token
arcsolve-mcp auth kakao

# 4) Verify locally
arcsolve-mcp                    # run the stdio MCP server
```

Registering with an MCP host (e.g. Claude Desktop):

```json
{
  "mcpServers": {
    "arcsolve": {
      "command": "arcsolve-mcp",
      "args": ["serve", "kakao"],
      "env": {
        "KAKAO_REST_API_KEY": "...",
        "KAKAO_REFRESH_TOKEN": "..."
      }
    }
  }
}
```

## Use only the modules you want

It installs as one package, but you can **pick which services to expose**.

```bash
arcsolve-mcp list                 # see available services
arcsolve-mcp serve kakao          # expose only kakao
ARCSOLVE_SERVICES=kakao arcsolve-mcp   # select via env var (handy in a host's env)
arcsolve-mcp                      # all services if unspecified
```

To **embed an individual module in your own MCP server**, call its register function
directly:

```python
from fastmcp import FastMCP
from arcsolve.services.kakao import SERVICE

mcp = FastMCP("my-app")
SERVICE.register(mcp)   # add only the kakao tools to my server
```

## Add a new service (one folder)

1. `arcsolve/services/<name>/contract.py` — endpoint constants + pydantic request/response models
2. `arcsolve/services/<name>/tools.py` — define `@mcp.tool`s inside `register(mcp)`
3. `arcsolve/services/<name>/__init__.py` — declare `SERVICE = Service(...)`

**Do not touch the registry** — it auto-scans `services/`, so dropping in a folder
registers it (no parallel conflicts). Full procedure and rules:
[AGENTS.md](AGENTS.md) / [docs/adding-a-service.md](docs/adding-a-service.md).

## Skills

If MCP tools are "what's available," a **skill** teaches Claude "how to use it well." A
skill does not import `contract.py`; it **orchestrates the running ArcSolve MCP tools** —
the verified contract stays the single source of truth on the MCP side.

Example: [`academic-discovery`](skills/academic-discovery/README.md) — discovers and
cross-checks papers across arXiv · Crossref · OpenAlex · PubMed · Semantic Scholar
(coverage and citation triangulation that a single search won't surface).

```bash
arcsolve-mcp skills    # list available skills
```

Adding a new skill: [docs/adding-a-skill.md](docs/adding-a-skill.md).

## Docs

- [AGENTS.md](AGENTS.md) — shared working rules for every agent (human or AI), single source of truth
- [Architecture](docs/architecture.md) — contract/tools split, single composed host, "the two OAuths"
- [Adding a service](docs/adding-a-service.md) — 3 steps + the service README template
- [Adding a skill](docs/adding-a-skill.md) — SKILL.md + the skill README template
- [Implementation manifest](docs/providers.md) — bundle of official-doc links (input for parallel work)
- [Service catalog](docs/services.md) — tool list (auto-generated, `arcsolve-mcp catalog`)
- [Skill catalog](docs/skills.md) — skill list (auto-generated)
- [i18n](docs/i18n.md) — bilingual docs convention (English canonical, Korean translation)
- Per-service guides: `arcsolve/services/<name>/README.md` (e.g. [kakao](arcsolve/services/kakao/README.md))
- Per-skill guides: `skills/<name>/README.md` (e.g. [academic-discovery](skills/academic-discovery/README.md))

## Security

- Tokens are stored **in plaintext** at `~/.arcsolve/credentials.json` (file 0600 /
  directory 0700). Beware on shared machines.
- The authorization-code flow uses **PKCE (S256)** to protect public clients.
- Putting `*_REFRESH_TOKEN` directly in a host's env adds a plaintext-exposure path —
  prefer `auth` to use the token store when you can.

## License

[Apache-2.0](LICENSE) · how to contribute: [CONTRIBUTING.md](CONTRIBUTING.md)
