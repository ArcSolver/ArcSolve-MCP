---
name: wikipedia-lookup
description: Looks up encyclopedic background on a topic, entity, or term in Wikipedia via the ArcSolve MCP tools — finding the right article, then reading its summary and (only when needed) full extract, outgoing links, and Wikidata id. Use when you need quick factual context, to disambiguate a name, verify a fact, or find the canonical article for an entity — when a single authoritative source is enough.
allowed-tools:
  - wikipedia_search
  - wikipedia_summary
  - wikipedia_extract
  - wikipedia_links
---

# Wikipedia lookup

Get encyclopedic background on a topic from a single authoritative source: find the right
article, read its summary, and drill down only as far as the question needs.

This skill **orchestrates ArcSolve MCP tools** — it does not call any API directly. The MCP
server must expose the `wikipedia` service (see "필요 MCP 도구" in [README](README.md)).

## When to use
- "What is X?" / "Who is Y?" — quick encyclopedic background on a topic, person, place, or term.
- Disambiguate an ambiguous name (e.g. "Mercury" — planet, element, or person?).
- Verify a fact or pin down dates, definitions, and the canonical name of an entity.
- Find the **canonical article + Wikidata id** for an entity, or what an article links to.

## Workflow
1. **Find the article.** `wikipedia_search(query)` and pick the best-matching title. Downstream
   tools are title-keyed, so resolving to the right title first matters.
2. **Read the summary.** `wikipedia_summary(title)` → lead extract, canonical URL, and the
   **Wikidata Q-id** (when present). This is often the whole answer.
3. **Disambiguate.** If the summary `type` is a disambiguation page (or search results are
   ambiguous), narrow the query or choose among candidates; ask the user when genuinely unclear.
4. **Go deeper only if needed.** `wikipedia_extract(title, intro_only=False)` (or `max_chars`)
   for a fuller body; `wikipedia_links(title)` for outgoing links and categories to branch from.
5. **Cite.** Always give the article **title + canonical URL** (and Wikidata id when present), and
   note the language edition, so the user can verify.

## Language
Default `lang="en"`. Switch (`ko`, `de`, …) when the topic is better covered in another edition
or the user asks; pass the **same `lang` consistently** across all calls in one lookup.

## Boundary (what this skill does NOT do)
- **Read-only.** No editing or uploads.
- **Single source.** Wikipedia only. For cross-source scholarly discovery use
  `academic-discovery`; for structured entity facts/relations, hand off to Wikidata
  (`wikidata_*`) using the summary's Wikidata id as the bridge — *mention, don't perform*.
- **No synthesis** beyond reporting what the article says (no essays, no opinion).

## Etiquette
Prefer a narrow search + summary over dumping full extracts. Respect rate limits; a meaningful
`User-Agent` is recommended (see the service README).
