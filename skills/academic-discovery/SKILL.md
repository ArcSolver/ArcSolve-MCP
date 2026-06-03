---
name: academic-discovery
description: Discovers and cross-references scholarly papers across multiple academic databases (arXiv, Crossref, OpenAlex, PubMed, Semantic Scholar) via the ArcSolve MCP tools. Use when finding papers on a topic, locating a specific work across sources, tracing citations or an author's output, or triangulating metadata — whenever one database's search is not enough.
allowed-tools:
  - arxiv_search
  - arxiv_get
  - crossref_search_works
  - crossref_get_work
  - openalex_search_works
  - openalex_get_work
  - openalex_search_authors
  - openalex_get_author
  - pubmed_search
  - pubmed_get_summary
  - pubmed_fetch_abstract
  - s2_search_papers
  - s2_get_paper
  - s2_search_authors
  - s2_get_author
---

# Academic discovery

Find and triangulate scholarly literature across five complementary sources. No single
database covers everything, so this skill queries several, reconciles results by identifier,
and surfaces the strongest candidates with their provenance.

This skill **orchestrates ArcSolve MCP tools** — it does not call any API directly. The MCP
server must expose the academic services (see "필요 MCP 도구" in [README](README.md)).

## When to use
- "Find recent papers on <topic>" — broad discovery across sources.
- "Is there a published version of <preprint / title>?" — cross-source lookup.
- "What cites / is related to <paper>?" — citation tracing.
- "What has <author> published recently?" — author-centric discovery.
- "Reconcile the metadata (DOI, venue, year) for <work>" — triangulation.

## Source coverage (pick by need)
| Source | Tool prefix | Strength | Note |
|--------|-------------|----------|------|
| arXiv | `arxiv_` | Preprints (physics, CS, math) | Not peer-reviewed; field-prefixed query (`ti:`/`au:`/`cat:`) |
| PubMed | `pubmed_` | Biomedical / life sciences | PMID-keyed; MeSH terms help |
| Crossref | `crossref_` | DOI registry / publisher metadata | Authoritative DOIs & bibliographic records |
| OpenAlex | `openalex_` | Open scholarly graph | Citations, concepts, open-access status |
| Semantic Scholar | `s2_` | AI-enhanced graph | Influential citations, TLDRs |

Details in [references/sources.md](references/sources.md).

## Workflow
1. **Frame the query per source.** The same question maps differently: arXiv uses field
   prefixes and boolean operators in `search_query`; PubMed favours MeSH; OpenAlex/Crossref/S2
   take free text. Route by domain (biomedical → PubMed; CS/physics preprints → arXiv;
   everything → OpenAlex + Crossref + S2).
2. **Search** with the relevant `*_search*` tools. Keep result sets small first (top 10–20 per
   source), then widen if needed.
3. **Deduplicate & reconcile.** Match across sources by **DOI first**; fall back to normalized
   title + year (or arXiv id). Merge into one record per work, noting which sources found it.
4. **Triangulate.** A work found in several sources is more trustworthy; flag preprint-only vs
   published (preprint on arXiv + DOI in Crossref → published).
5. **Expand by citation** when asked: use `openalex_get_work` / `s2_get_paper` to find
   related/citing works.
6. **Drill down** with `*_get*` / `pubmed_get_summary` / `pubmed_fetch_abstract` / `arxiv_get`
   to pull abstracts and full metadata for shortlisted candidates.
7. **Present** a ranked, deduped shortlist. Always cite the source + identifier (DOI / PMID /
   arXiv id) for each item so the user can verify.

## Boundary (what this skill does NOT do)
- No narrative synthesis, literature-review writing, claim extraction, or quality appraisal —
  that is a separate (future) skill. Stop at "found and triangulated".
- Optional hand-offs (mention, don't perform): save findings to a reference manager
  (`zotero_*`), or fetch background entities (`wikipedia_*` / `wikidata_*`).

## Etiquette
Respect each source's rate limits (arXiv recommends ~3s between calls). Prefer narrow queries
over large result dumps.
