# Adding a new service

> **English** · [한국어](adding-a-service.ko.md)

One service = **one folder**. Don't touch the shared framework
(`server`/`service`/`http`/`oauth`).

## 3 steps

### 1. Write the contract — `arcsolve/services/<name>/contract.py`
The upstream API's "truth" only. Pure constants + pydantic models, no MCP/network dependency.
```python
from pydantic import BaseModel, Field

BASE_URL = "https://api.example.com"
SOME_ENDPOINT = "/v1/things"          # endpoints as constants

class CreateThing(BaseModel):          # request schema
    title: str = Field(max_length=100)

class ThingResult(BaseModel):          # response schema
    ok: bool
```
If you use OAuth, put `AUTHORIZE_URL` / `TOKEN_URL` / `SCOPES` here too.

### 2. Write the tools — `arcsolve/services/<name>/tools.py`
Define `@mcp.tool`s inside `register(mcp)` and use the shared `http`/`oauth`.
Tool names use a **single service prefix** (`example_create_thing`).
```python
from fastmcp import FastMCP
from arcsolve.http import post_form, UpstreamError
from arcsolve.services.example import contract as c

def register(mcp: FastMCP) -> None:
    @mcp.tool
    async def example_create_thing(title: str) -> str:
        """Create one thing."""        # the first line becomes the catalog description
        ...
```

### 3. Declare — `arcsolve/services/<name>/__init__.py`
```python
from arcsolve.service import Service
from arcsolve.services.example.tools import register  # , make_oauth_client (if OAuth)

SERVICE = Service(
    name="example",
    register=register,
    docs_url="https://docs.example.com/api",   # provenance — required
    summary="one-line description",
    # make_auth_client=make_oauth_client,       # OAuth services only — auto-wires the auth CLI
)
```
**Don't touch the registry.** It scans `services/` and auto-discovers `SERVICE`, so
dropping in a folder registers it (no conflicts when adding in parallel).

> Reuse the shared core HTTP verbs (`post_form`/`get_json`/`post_json` in `arcsolve.http`).
> **Do not add a new third-party dependency** in the service folder (if needed, reflect
> it in `pyproject.toml` at the integration stage).

### Finishing up
- `tests/test_<name>_contract.py` → contract-model validation (no network)
- `tests/test_<name>_tools.py` → tool runtime validation (request assembly, response parsing, error mapping).
  Use `tests/conftest.py`'s `FakeMCP` (collects the `@mcp.tool`s that register attached) and
  `RecordingHTTP` (mocks the http verbs) fixtures (no network).
- `changelog.d/<name>.md` → one-line change summary (e.g. `- **example**: add tool X`)
- At the integration stage (not the individual agent), run `arcsolve-mcp catalog` + `arcsolve-mcp changelog`

## Service README template (required)

Keep docs **next to the code**: `arcsolve/services/<name>/README.md`. Don't create a
separate `docs/<name>.md` (duplication = drift). Every service follows the same skeleton below.

```markdown
# <Service>
One-line description.

## Contract sources (official docs)
- API reference: <url>
- Auth/token: <url>
> The contract body is set in stone as code in contract.py.

## Endpoints
| Kind | METHOD · PATH |
|------|------|
| ... | ... |
Base: `...` · Auth: `...` · Scope: `...`

## Setup
1. Issue a key
2. Authenticate: `arcsolve-mcp auth <name>`

## Tools
| Tool | Description |
|------|------|
| `<name>_...` | ... |

## Scope / limits
- ...

## Extension points
- ...
```

## Where things go (summary)

| Document | Location | Source (who is the truth) |
|------|------|------|
| Contract reference (fields/limits) | `contract.py` | **code** — no prose duplication |
| Service operating guide | `services/<name>/README.md` | one per service |
| Cross-cutting (architecture, this doc) | `docs/` | fixed regardless of service count |
| Service catalog | `docs/services.md` | **auto-generated** (`arcsolve-mcp catalog`) |
| Changelog | `changelog.d/<name>.md` → `CHANGELOG.md` | written as fragments, then **assembled** (`arcsolve-mcp changelog`) |
| Shared working rules | `AGENTS.md` | single source of truth for every agent |
