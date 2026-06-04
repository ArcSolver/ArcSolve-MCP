---
name: info-gathering
description: Gathers and tracks fresh web content by orchestrating ArcSolve MCP reading tools — pulling RSS/Atom/RDF feeds (news, blogs, release notes, YouTube channels) and Hacker News (front-page ranking, search, item threads, user activity). Use when a user wants a digest of what's new across sources, to monitor a topic or a set of feeds, to surface trending tech discussion, or to follow a specific HN thread or author — whenever one source is not enough.
allowed-tools:
  - feeds_fetch
  - hn_top
  - hn_search
  - hn_item
  - hn_user
---

# Info gathering

Build a **fresh digest** across the open web: subscribe to arbitrary RSS/Atom feeds and fold in
Hacker News (ranking + search + threads). Each source surfaces different things, so this skill
queries both, deduplicates by link, and presents a ranked, dated digest.

This skill **orchestrates ArcSolve MCP tools** — it does not call any API directly. The MCP server
must expose the `feeds` and `hackernews` services (see "필요 MCP 도구" in [README](README.md)).
All read-only and unauthenticated.

## When to use
- "What's new on <blog/news/release feed>?" — pull and summarize a feed.
- "What's trending on Hacker News?" / "Anything on HN about <topic>?" — ranking + search.
- "Digest these N feeds for me" — monitor a set of sources at once.
- "Follow this HN thread / what has <user> posted?" — item threads and user activity.

## Source coverage
| Source | Service | Tools |
|--------|---------|-------|
| Any RSS/Atom/RDF feed | `feeds` | `feeds_fetch` |
| Hacker News | `hackernews` | `hn_top`, `hn_search`, `hn_item`, `hn_user` |

## Workflow
1. **Pick sources.** Map the request to feeds (explicit URLs) and/or Hacker News (ranking or search).
   For a topic, run `hn_search(query)` and fetch the relevant feeds.
2. **Pull.** `feeds_fetch(url, limit=...)` per feed; `hn_top(...)` for the front page or
   `hn_search(query)` for a topic. Keep limits small first, widen if needed.
3. **Drill down.** `hn_item(id)` for a story's discussion; `hn_user(id)` for an author's recent items.
4. **Deduplicate & rank.** Merge by canonical link; collapse the same story appearing in a feed and on
   HN. Order by recency (and HN points when relevant).
5. **Present** a dated digest: title · source · link · 1-line gist, newest first. Always link out so the
   user can verify. Note each item's timestamp.

## Boundary (what this skill does NOT do)
- **Read-only.** No posting, voting, or commenting.
- **SSRF-safe by construction.** `feeds_fetch` validates the URL host (the core blocks internal/metadata
   addresses); pass through user URLs as-is and let the tool guard.
- **No synthesis beyond a digest** — report what sources say; no essays or opinion.
- **No general web search.** It reads the feeds you give it + Hacker News; it does not crawl the open web.
- **Hand-offs (mention, don't perform).** To deliver the digest, hand off to a messaging skill — *mention, don't perform*.

## Etiquette
Prefer a few targeted feeds + a focused HN query over large dumps. Respect rate limits and keep
per-source limits modest. Pass timestamps and source attribution through to the user.
