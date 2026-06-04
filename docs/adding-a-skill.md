# Adding a new skill

> **English** · [한국어](adding-a-skill.ko.md)

A skill = **one folder** (`skills/<name>/`). A skill is not imported code but **shipped
data** — its `SKILL.md` captures "how to wire MCP tools together." Don't touch the
shared framework (`skill`/`catalog`).

> **The core (AGENTS.md rule 2-2):** a skill does not import `contract.py` and does not
> hit the upstream API directly. The verified contract stays the single source of truth
> in the MCP service, and the skill **orchestrates the tools of a running ArcSolve MCP
> server**. A skill = instructions that wire tools together well + (optionally) a thin
> stdlib helper.

## Layout

```
skills/<name>/
├── SKILL.md        # Contract: frontmatter (name·description·allowed-tools) + workflow-instruction body
├── scripts/        # (optional) pure helpers — stdlib-only, no direct upstream API calls
├── references/     # (optional) reference docs for progressive loading
└── README.md       # Operating guide + "Contract sources" + "Required MCP tools"
```

### 1. `SKILL.md` — frontmatter + body

```markdown
---
name: example-discovery
description: Discovers and cross-checks X across multiple sources. Use when ... (trigger). (one line — frontmatter is minimal YAML)
allowed-tools:
  - foo_search
  - foo_get
  - bar_search
---

# Example discovery

## When to use
...(trigger situations)

## Workflow
1. Translate the query per source ...
2. Search across sources, then dedup by identifier ...
3. ...

## Boundaries
- Up to ... only. Does not synthesize or write (that's another skill).
```

Frontmatter rules:
- `name`: same as the folder, lowercase and hyphenated.
- `description`: **third person, "what + when (trigger)"**. No overclaiming (this is the
  public promise = the contract).
- `allowed-tools`: the **ArcSolve MCP tool names** to orchestrate (e.g. `arxiv_search`).
  The static test cross-checks them against real tools (the `docs/services.md` catalog),
  so they **must be real tool names**.

### 2. Body — workflow instructions

Write the procedure Claude should follow. Track sources for the factual parts (tool
names, parameters, command syntax) and leave a `TODO(provenance)` when uncertain.
Workflow/judgment has no external source, so its **quality is verified by eval**.

### 3. (optional) `scripts/` · `references/`

- `scripts/`: deterministic helpers only (formatting, dedup, etc.). Use **only the
  standard library** and do not import `arcsolve`. API calls are the MCP tool's job.
- `references/`: material too long to inline in the body (per-source coverage, query
  syntax, etc.). Loaded progressively when needed.

### Wrap-up

- `tests/test_<name>_skill.py` → **static invariants only**: frontmatter required fields,
  reference resolution, `allowed-tools` match real tool names (no network, no model).
- `evals/` (or `skills/<name>/evals/`) → **quality gate**: the skill-creator harness
  verifies "does it make Claude behave correctly" (non-deterministic, model calls —
  separate from pytest CI).
- `changelog.d/skill-<name>.md` → one-line summary (`skill-` prefix to avoid name clashes
  with services).
- At the integration stage (not the individual agent), run `arcsolve catalog` →
  regenerates `docs/skills.md`.

## Skill README template (required)

Keep the doc **next to the skill**: `skills/<name>/README.md`. The provenance test checks
the "Contract sources" and "Required MCP tools" sections.

```markdown
# <Skill>
One-line description (kind: discovery/summary/...).

## Contract sources (official docs)
Relies on the verified contracts of the MCP services it orchestrates (a skill does not
redefine contracts).
- <service A> API: <url>
- <service B> API: <url>

## Required MCP tools
This skill needs the following tools exposed by the ArcSolve MCP server (matching `allowed-tools`).
- `foo_search`, `foo_get` — <service A>
- `bar_search` — <service B>
> Setup: `arcsolve serve <service A> <service B>` (or ARCSOLVE_SERVICES)

## Scope / boundaries
- Included = ... / Excluded (other skills) = ...
```

## What goes where (summary)

| Doc | Location | Source (who is the truth) |
|------|------|------|
| Verified API contract | MCP `services/<x>/contract.py` | **code** — skills don't redefine it |
| Skill body (workflow·triggers) | `skills/<name>/SKILL.md` | one per skill |
| Skill operating guide | `skills/<name>/README.md` | one per skill |
| Skill catalog | `docs/skills.md` | **auto-generated** (`arcsolve catalog`) |
| Changelog | `changelog.d/skill-<name>.md` → `CHANGELOG.md` | written as fragments, **assembled** |
| Shared working rules | `AGENTS.md` | single source of truth for every agent |
