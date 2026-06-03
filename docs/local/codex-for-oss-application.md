# Codex for Open Source — Application Draft

> Working draft for the OpenAI **Codex for Open Source** program
> (form: https://openai.com/form/codex-for-oss/ ·
> program: https://developers.openai.com/community/codex-for-oss).
> The form is merit-based and asks you to be **concise and honest** — answers
> below are written to be pasted field-by-field. Numbers marked `[fill in]`
> must be filled from the live repo at submit time; do not inflate them.

---

## Quick facts

| Field | Value |
|------|-------|
| Project | **ArcSolve MCP** |
| Repository | https://github.com/ArcSolver/ArcSolve-MCP |
| License | Apache-2.0 (OSI-approved) |
| Language / stack | Python 3.11+, FastMCP (Model Context Protocol) |
| Your role | Core maintainer (write access / project lead) |
| Status | Early-stage, actively maintained — 10 services, 47 tools today |
| Stars / downloads | `[fill in at submit time — currently small; this is a young project]` |

---

## 1. What is the project? (description)

ArcSolve MCP is an open-source collection that standardizes the **public API
contracts** of popular services as composable **MCP (Model Context Protocol)
tools**. A single FastMCP server composes many services and exposes them through
one consistent interface; each service is exactly **one folder = a contract +
its tools**.

Today it ships **10 services / 47 tools** across three areas:

- **Messaging / SNS** — KakaoTalk, LINE, Telegram, Discord
- **Academic & research reading** — arXiv, Crossref, OpenAlex, Semantic Scholar, Zotero
- **Productivity** — Notion

## 2. Why does this project matter to the ecosystem?

It fills a real, underserved gap rather than re-wrapping what already has
first-party MCPs:

- **Regional messaging that has no official MCP.** KakaoTalk (Korea), LINE
  (Japan/Taiwan/SEA) are dominant chat platforms with large user bases but no
  first-party MCP. ArcSolve gives models a clean, contract-faithful way to reach
  them — alongside Telegram and Discord.
- **A scholarly-reading layer.** arXiv, Crossref, OpenAlex, Semantic Scholar and
  Zotero are unified under one consistent read interface, so an agent can
  research a topic across sources without bespoke glue per source.
- **Composable by design.** Each service registers independently
  (`SERVICE.register(mcp)`), so agentic-workflow developers can embed just the
  modules they need into their own MCP server — building blocks, not a monolith.
- **License-clean.** Every contract is a self-built client whose every endpoint
  and field is traced to the provider's **official documentation** (enforced by
  provenance tests), not reverse-engineered or copied SDK code.

The "itch" it removes: today, adding chat/notification to a product, pulling in
research data, and managing both in one place each require different, repetitive
integration work. ArcSolve makes all three a uniform, model-callable contract.

## 3. Maintenance & governance (evidence of active, disciplined upkeep)

- **Single source of rules:** [`AGENTS.md`](../AGENTS.md) defines exactly how any
  contributor (human or AI) adds a service; `kakao/` is the canonical
  spec-by-example.
- **Contract/tools split:** `contract.py` (pure endpoints + pydantic models, no
  network/MCP) vs `tools.py` (thin MCP wrappers) — see
  [`docs/architecture.md`](architecture.md).
- **Provenance discipline:** every contract field carries a source link; a
  provenance test fails the build if a service README lacks official-doc links.
- **CI + isolation:** auto-discovery registry, per-service changelog fragments,
  and an auto-generated catalog keep parallel contributions conflict-free; tests
  and lint run in CI on every change.

## 4. How we will use ChatGPT Pro with Codex

The architecture was **deliberately built for an AI maintainer**: uniform
`folder = contract + tools`, spec-by-example, provenance tests, and isolated
changelog fragments mean a model can extend the project consistently without
stepping on other work. We will use ChatGPT Pro with Codex to:

- **Add and maintain service contracts at scale** — generate each new
  `contract.py`/`tools.py`/tests folder strictly from official API docs, the same
  way `kakao` was built.
- **Detect and fix contract drift** — when an upstream API changes, Codex
  re-verifies the affected `contract.py` against the official docs and opens a fix.
- **Triage issues and review PRs** — enforce the `AGENTS.md` Definition-of-Done
  checklist (provenance, prefix naming, core-reuse, tests) on incoming PRs.
- **Multilingual support** — produce tool descriptions, docs, and messages in
  multiple languages (a core roadmap goal).

## 5. How we will use API credits (Codex Open Source Fund)

Fold Codex directly into core project processes:

- **PR review automation** — a Codex reviewer that checks every PR against the
  contract-fidelity and core-reuse rules before a human looks.
- **A "contract-drift" CI check** — periodically re-validate each `contract.py`
  against its official-doc source (this automates the provenance discipline we
  already practice by hand).
- **Release automation** — assemble `CHANGELOG.md` from fragments and regenerate
  the service catalog on release.

## 6. Codex Security (if offered)

Of interest for the auth/credential core: ArcSolve handles upstream OAuth2
(authcode + PKCE + refresh) and stores tokens locally. A security review of
`arcsolve/oauth.py` and the HTTP core, plus checks on new service contracts that
touch credentials, would be valuable for a project whose whole purpose is to let
models act through third-party APIs.

## 7. One-paragraph summary (for a short "why you" box)

ArcSolve MCP standardizes public API contracts as composable MCP tools so models
can reach many products — regional SNS chat (KakaoTalk, LINE), academic reading
(arXiv, Crossref, OpenAlex, Semantic Scholar, Zotero), Notion — through one
consistent, license-clean interface, and so agentic-workflow developers can
assemble those modules into the service they want. It is young but built
specifically for **consistent, contract-based growth maintained primarily by
Codex**: every service is one folder of contract + tools, every field traces to
official docs, and the contributor rules are codified for AI and humans alike.
The grant would let us make Codex the project's main maintainer — scaling
services, keeping contracts in sync with upstream APIs, and adding multilingual
support.

---

### Honesty checklist before submitting

- [ ] Fill `[fill in]` metrics from the live repo — **do not inflate**.
- [ ] The program welcomes projects that don't meet every criterion if they play
      an important ecosystem role — lead with *merit and the gap filled*, not stars.
- [ ] Confirm Apache-2.0 + non-commercial/open-source use (program terms).
- [ ] Keep it concise; the reviewers explicitly value brevity and honesty.
