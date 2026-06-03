# AGENTS.md

> **English** · [한국어](AGENTS.ko.md)

The single set of rules every **agent (human or AI)** follows in this repository. Even
with zero prior context, this document + the **canonical examples** (MCP service =
`kakao` / Skill = `academic-discovery`) should be enough to implement a new service or
skill correctly.

## Mission

An open-source collection that bundles **capabilities verified against official API
contracts** into two formats.

- **MCP service** — one FastMCP server composes many services and exposes them as
  *runtime tools*.
- **Skill** — a file artifact that teaches Claude *how to use those tools and workflows*.

The two are not competitors but **two distribution formats over the same contract
backbone**. Design background: [docs/architecture.md](docs/architecture.md).

## The two deliverable formats

| | MCP service | Skill |
|---|---|---|
| What | exposes *what a tool is* at runtime | teaches an agent *how to use it* |
| Unit | one `arcsolve/services/<name>/` folder | one `skills/<name>/` folder |
| Delivery | served by a FastMCP server (stdio/HTTP) | installed into `~/.claude/skills/`, progressively loaded into context |
| Contract | API request/response pydantic models (`contract.py`) | `SKILL.md` frontmatter (the public promise) + the provenance of the body's instructions |

**Complementarity:** one domain can ship both formats — `kakao` MCP tools + a "how to
use Kakao messaging well" skill. Reuse happens at the **tool boundary**: a skill does not
import `contract.py`; it **orchestrates the tools of a running ArcSolve MCP server**
(rule 2-2). The verified contract stays the single source of truth on the MCP side.

## Golden rule: clone the canonical example

- For an **MCP service**, `arcsolve/services/kakao/` is the canonical answer.
- For a **Skill**, `skills/academic-discovery/` is the canonical answer — a
  **multi-service orchestration** that discovers and cross-checks papers across several
  scholarly sources (arXiv · Crossref · OpenAlex · PubMed · Semantic Scholar).
  *(A minimal single-service example is coming — candidate: `skills/wikipedia-lookup/`.)*

When the prose rules feel ambiguous, the canonical example code is the final word.

## Inputs and deliverables

**Input**: your target's block in [docs/providers.md](docs/providers.md) (official-doc
links, scope, plan). Each block declares `format: mcp | skill | both` to state which
format is the goal.

### If you're assigned an MCP service

Deliverable: one `arcsolve/services/<name>/` folder + your changelog fragment + your
**two tests** (contract, tools). **Touch nothing else.**

```
arcsolve/services/<name>/
├── contract.py     # Contract: endpoint constants + pydantic request/response models (no MCP/network dependency)
├── tools.py        # MCP tools: @mcp.tool inside register(mcp), reusing the shared http/oauth
├── __init__.py     # SERVICE = Service(...)  ← auto-discovered
└── README.md       # Fixed template (docs/adding-a-service.md)
tests/test_<name>_contract.py    # Contract-model validation (no network)
tests/test_<name>_tools.py       # Tool runtime validation (request assembly, response parsing, error mapping)
                                 #   — uses the FakeMCP/RecordingHTTP fixtures in tests/conftest.py, no network
changelog.d/<name>.md            # One-line change summary
```

### If you're assigned a Skill

Deliverable: one `skills/<name>/` folder + your changelog fragment + one test (skill).
**Touch nothing else.**

```
skills/<name>/
├── SKILL.md        # Contract: frontmatter (name·description·allowed-tools) + workflow-instruction body
├── scripts/        # (optional) pure helpers only — stdlib-only, never hit the upstream API directly (MCP tools do that)
├── references/     # (optional) reference docs for progressive loading
└── README.md       # Fixed template + "Contract sources" + "Required MCP tools" sections (docs/adding-a-skill.md)
tests/test_<name>_skill.py       # Static invariants: frontmatter, reference resolution, allowed-tools match real tool names, no network
evals/<name>/                    # Quality gate: eval (skill-creator harness) — location/format in docs/adding-a-skill.md
changelog.d/skill-<name>.md      # One-line change summary ('skill-' prefix to avoid name clashes with services)
```

`SKILL.md` frontmatter follows:
- `name`: same as the folder, lowercase and hyphenated.
- `description`: **third person, "what + when (trigger)"**, precisely. No overclaiming
  (this is the public promise = the contract).
- `allowed-tools`: the **ArcSolve MCP tool names** to orchestrate (e.g.
  `kakao_send_text_to_me`). The static test checks them against real tools.

## Rules

### 1. Contract fidelity (most important — common to both formats)
- **Every fact (endpoint, field, command, API behavior) must actually exist in the
  official docs.** Do not fill them from training knowledge.
- **If the docs are ambiguous, do not invent** — leave a
  `# TODO(provenance): <what is uncertain>` and report it.
- Contract source links go in the "Contract sources" section of the `README.md` (the
  provenance test checks this).
- **MCP service:** a **source comment/link** on every endpoint and field in
  `contract.py`. Models are pydantic; reflect length/required/enum constraints as documented.
- **Skill:** the `description` matches actual behavior (no overclaiming). Only the
  **factual parts** of the body (commands, tool names, parameters) are subject to
  provenance tracking. **Workflow/judgment** has no external source, so its quality is
  verified by **eval**, not provenance (rule 6).

### 2. Reuse the shared core (no reinventing — MCP service)
- HTTP: `arcsolve.http`'s `post_form` / `get_json` / `post_json` (+ the `bearer(token)`
  header helper). Do not spin up your own httpx session. If you need a call shape the
  core lacks, **extend the core** (not inside the service folder).
- OAuth: `arcsolve.oauth.OAuthClient` (authcode + PKCE + refresh + token store). A
  service that uses OAuth passes `make_auth_client` to `SERVICE` in `__init__.py`, so
  `arcsolve-mcp auth <name>` works without core changes.

### 2-1. Dependencies (avoid parallel conflicts)
- A service folder uses **only the standard library + the shared core**; a skill script
  uses **only the standard library** (a skill does not import `arcsolve` — rule 2-2). Do
  not add a new third-party dependency from a folder.
- If a heavy SDK is truly required, state it in the PR description → it is reflected in
  `pyproject.toml`/`uv.lock` **at the integration stage** (isolated via extras if needed).

### 2-2. Reuse happens at the tool boundary (Skill — the heart of ArcSolve)
- A skill **does not import `contract.py`.** The verified contract stays the single
  source of truth in the MCP service, and the skill **orchestrates the tools of a running
  ArcSolve MCP server** (a skill = instructions that wire tools together well + thin glue).
- State which MCP services/tools it depends on in the frontmatter `allowed-tools` and the
  README "Required MCP tools" section → the catalog surfaces them.
- API calls are **the MCP tool's job**. A skill script never hits the upstream API
  directly (that's the service's job).

### 3. Naming and exposure
- **MCP tool names** use a single service prefix: `<name>_<action>` (e.g.
  `kakao_send_text_to_me`).
- Declaring `SERVICE` in `arcsolve/services/<name>/__init__.py` is enough — the
  **registry auto-discovers** it.
- **Skill names** are the folder name = frontmatter `name`. A separate namespace from
  tool prefixes (a paired skill may intentionally share the domain name).
- Do not edit registry/catalog files (auto-discovered, auto-generated).

### 4. Don't confuse "the two OAuths" (MCP service)
- Upstream OAuth (server → upstream API, e.g. Kakao Login) is handled by `oauth.py`. MCP
  transport OAuth (the spec) is separate and unnecessary for local stdio. Details:
  [docs/architecture.md](docs/architecture.md).

### 5. Isolation — never touch (avoid parallel conflicts)
- `arcsolve/services/__init__.py` (service registry — auto-discovery)
- `skills/__init__.py` (skill registry — auto-discovery)
- `docs/services.md`, `docs/skills.md` (catalogs — auto-generated)
- `CHANGELOG.md` (the body — assembled from fragments)
- `pyproject.toml` / `uv.lock` (dependencies — integration stage owns these)
- another service's or skill's folder
- the shared core (`server/service/skill/http/oauth/catalog/changelog`) — no edits
  without good reason (a change that benefits everyone, like extending the core HTTP
  verbs, is allowed as a separate PR)

### 6. Quality gate (Skill — deterministic tests + eval)
- `test_<name>_skill.py` checks **static invariants only** (frontmatter required fields,
  reference resolution, `allowed-tools` match real tool names). No network, no model.
- A skill's real quality ("does it make Claude behave correctly") is verified by **eval**
  (skill-creator harness). Recognize it as a **different kind of assurance** than a
  service's deterministic unit tests.

## Definition of Done

### MCP service
- [ ] `contract.py`: endpoints = constants, pydantic models, **a source per field**, documented constraints reflected
- [ ] `tools.py`: `register(mcp)` + `@mcp.tool`, single-level prefix, shared `http`/`oauth`, error mapping
- [ ] `__init__.py`: `SERVICE = Service(name, register, docs_url, summary, make_auth_client?)` — **`docs_url` required**, `make_auth_client` set if OAuth
- [ ] `README.md`: template + "Contract sources" official-doc links (the provenance test checks this)
- [ ] `tests/test_<name>_contract.py`: contract-model validation, passes without network
- [ ] `tests/test_<name>_tools.py`: tool runtime validation — uses `conftest.py`'s FakeMCP/RecordingHTTP, passes without network
- [ ] `changelog.d/<name>.md`: change summary
- [ ] No new third-party dependency added in the service folder
- [ ] `uv run pytest -q` passes · `uv run ruff check .` passes
- [ ] No hallucinations: mark anything unconfirmed with `TODO(provenance)`

### Skill
- [ ] `SKILL.md`: frontmatter `name` (matches folder) + `description` (third person, "what + when", no overclaiming) + `allowed-tools` (MCP tool names to orchestrate) + workflow-instruction body
- [ ] **Factual parts** of the body (commands, tool names, parameters) have sources; mark unconfirmed with `TODO(provenance)`
- [ ] Does not import `contract.py` · if a script exists, stdlib-only pure helper (no direct upstream API calls)
- [ ] `README.md`: template + "Contract sources" + "Required MCP tools" sections (the provenance test checks this)
- [ ] `tests/test_<name>_skill.py`: static invariants (frontmatter, reference resolution, `allowed-tools` match real tool names), passes without network
- [ ] **eval passes**: quality verified with the skill-creator harness (rule 6)
- [ ] `changelog.d/skill-<name>.md`: change summary
- [ ] `uv run pytest -q` passes · `uv run ruff check .` passes

## Commands

```bash
uv run pytest -q              # tests
uv run ruff check .           # lint
# (integration stage owns these — individual agents do not run them)
uv run arcsolve-mcp catalog   # regenerate docs/services.md + docs/skills.md
uv run arcsolve-mcp changelog # assemble CHANGELOG.md
```

For adding a new service, see [docs/adding-a-service.md](docs/adding-a-service.md);
for adding a new skill, see [docs/adding-a-skill.md](docs/adding-a-skill.md).
