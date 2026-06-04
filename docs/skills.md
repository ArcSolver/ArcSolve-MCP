# 스킬 카탈로그

> ⚙️ 자동 생성 — 직접 수정하지 마세요. `arcsolve catalog`로 재생성됩니다.

현재 **2개 스킬**. 스킬은 실행 중인 MCP 도구를 오케스트레이션한다(검증된 계약은 MCP 서비스 쪽 단일 출처).

## academic-discovery

Discovers and cross-references scholarly papers across multiple academic databases (arXiv, Crossref, OpenAlex, PubMed, Semantic Scholar) via the ArcSolve MCP tools. Use when finding papers on a topic, locating a specific work across sources, tracing citations or an author's output, or triangulating metadata — whenever one database's search is not enough.

오케스트레이션 도구: `arxiv_search`, `arxiv_get`, `crossref_search_works`, `crossref_get_work`, `openalex_search_works`, `openalex_get_work`, `openalex_search_authors`, `openalex_get_author`, `pubmed_search`, `pubmed_get_summary`, `pubmed_fetch_abstract`, `s2_search_papers`, `s2_get_paper`, `s2_search_authors`, `s2_get_author`

## wikipedia-lookup

Looks up encyclopedic background on a topic, entity, or term in Wikipedia via the ArcSolve MCP tools — finding the right article, then reading its summary and (only when needed) full extract, outgoing links, and Wikidata id. Use when you need quick factual context, to disambiguate a name, verify a fact, or find the canonical article for an entity — when a single authoritative source is enough.

오케스트레이션 도구: `wikipedia_search`, `wikipedia_summary`, `wikipedia_extract`, `wikipedia_links`

