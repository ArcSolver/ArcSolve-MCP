# Architecture

> **English** · [한국어](architecture.ko.md)

ArcSolve-Kit is a collection that **bundles the public APIs of popular services into
MCP tools**. One FastMCP server composes and exposes many services, and each service
is **one folder**.

## Three layers

```
Host (server.py)         A single FastMCP composing many services. Owns transport (stdio/HTTP).
   └─ Service (services/<name>)   The unit that attaches tools via register(mcp). Service = one folder.
        ├─ contract.py     The upstream API's "truth" (endpoints, scopes, request/response models). No MCP dependency.
        └─ tools.py        Thin MCP tools that call the contract.
Shared (http.py / oauth.py)  HTTP calls + OAuth shared by every service.
```

## Core principle: separating contract from tools

- **`contract.py` = "what the API is".** Pure constants + pydantic models. It knows
  nothing about the network or MCP. This file is the evidence that this is a
  "self-built client based on the official contract," and the basis for license cleanliness.
- **`tools.py` = "how that is exposed as tools".** Inside `register(mcp)` it defines
  `@mcp.tool`s and connects them as
  `tool args → contract model → shared HTTP → contract response → tool result` — a thin layer.

Thanks to this split, services stay clearly delineated while the structure stays
uniform, and the point where a contract changes is concentrated in one file.

## A single composed host

`server.py` iterates over the services auto-discovered by the registry
(`services/__init__.py`) and calls each service's `register(mcp)` to attach its tools
to **one server**. The user runs a single command and exposes only the services they
want. Each service is also independently testable.

Tool names use a **single service prefix** only (`kakao_send_text_to_me`). Shorter
names exposed to the model are better, so we do not go multi-level like
`arcsolve.kakao.*`.

### Expose only the modules you want

`build_server(services)` or `select_services()` picks what to expose
(priority: argument > `ARCSOLVE_SERVICES` env var > all). The CLI is `arcsolve serve kakao`.
To attach just one module to someone else's server, call `SERVICE.register(mcp)` directly.

The registry uses **lazy, isolated loading**:
- `available()` scans folders without importing → the list survives even if one service is broken.
- `select_services(names)` **imports only the selected ones** → individual use does not pull in the other services/dependencies.
- Imports are isolated per service with `try/except` → one unfinished/broken service does not kill the whole (tests, catalog, server).

> **Dependency rule:** a service folder uses only the standard library + the shared
> core. If a heavy SDK is needed, isolate it via optional extras in `pyproject.toml`
> (`arcsolve[heavy]`), and **add the dependency at the integration stage** (parallel
> edits to `pyproject.toml`/`uv.lock` by service agents would conflict).

## Don't confuse "the two OAuths"

| | What | Where |
|---|---|---|
| **Upstream OAuth** | the server authenticating *to the upstream API on the user's behalf* (e.g. Kakao Login → `talk_message`) | `oauth.py` + the service's `contract.py` |
| **MCP transport OAuth** | client↔server authentication (the spec's OAuth 2.1, **only for HTTP transport**) | **unnecessary** for local stdio |

The MVP uses local stdio + upstream OAuth only. Transport auth is added only when
moving to remote deployment.

## Tracking the MCP spec

- We **do not implement the protocol ourselves.** We ride on FastMCP and delegate
  spec-tracking to it (currently stable `2025-11-25`; the SDK also absorbs the next RC
  `2026-07-28` stateless-core transition).
- Transport is fixed to two: **stdio (default) + Streamable HTTP**. We do not invent new transports.
- Long-running work (Tasks) and server-rendered UI (MCP Apps) are currently unused,
  because most public API calls are synchronous req/res. The `thin tool → contract call`
  shape makes it easy to wrap in a Task later.

## Skills — the second distribution format

Where an MCP service exposes *what a tool is* at runtime, a **skill** is a file artifact
that teaches Claude *how to use those tools* (`skills/<name>/SKILL.md`). It is installed
not into a server but into `~/.claude/skills/`, and progressively loaded into context.

- **Reuse at the tool boundary.** A skill does not import `contract.py`; it orchestrates
  the running ArcSolve MCP tools. The verified contract stays the single source of truth
  on the MCP side, and the skill is the workflow on top of it.
- **Auto-discovery.** `arcsolve/skill.py` scans the repo-root `skills/` and builds a
  `Skill` from each `SKILL.md` frontmatter (the same data-scan philosophy as the service
  registry, no imports).
- **Verification.** Static tests check only structural invariants like frontmatter and
  `allowed-tools` ↔ real tool-name agreement. The real quality is verified by eval (a
  **different kind of assurance** than a service's deterministic unit tests).

See [adding-a-skill.md](adding-a-skill.md) for the full procedure.

## File map

| Path | Role |
|------|------|
| `arcsolve/server.py` | Compose services → a single FastMCP |
| `arcsolve/service.py` | `Service` = the uniform contract every service implements |
| `arcsolve/http.py` | Shared HTTP calls + `UpstreamError` |
| `arcsolve/oauth.py` | Generic OAuth2 (authcode + refresh) + token store |
| `arcsolve/catalog.py` | Registry → auto-generates `docs/services.md` + `docs/skills.md` |
| `arcsolve/skill.py` | `Skill` = the uniform contract for skills + `skills/` auto-discovery (`SKILL.md` frontmatter) |
| `arcsolve/services/<name>/` | One service = `contract.py` + `tools.py` + `README.md` |
| `skills/<name>/` | One skill = `SKILL.md` (+ `scripts/`·`references/`) + `README.md` |

Document placement rules: see [adding-a-service.md](adding-a-service.md).
