# 스킬 카탈로그

> ⚙️ 자동 생성 — 직접 수정하지 마세요. `arcsolve catalog`로 재생성됩니다.

현재 **3개 스킬**. 스킬은 실행 중인 MCP 도구를 오케스트레이션한다(검증된 계약은 MCP 서비스 쪽 단일 출처).

## academic-discovery

Discovers and cross-references scholarly papers across multiple academic databases (arXiv, Crossref, OpenAlex, PubMed, Semantic Scholar) via the ArcSolve MCP tools. Use when finding papers on a topic, locating a specific work across sources, tracing citations or an author's output, or triangulating metadata — whenever one database's search is not enough.

오케스트레이션 도구: `arxiv_search`, `arxiv_get`, `crossref_search_works`, `crossref_get_work`, `openalex_search_works`, `openalex_get_work`, `openalex_search_authors`, `openalex_get_author`, `pubmed_search`, `pubmed_get_summary`, `pubmed_fetch_abstract`, `s2_search_papers`, `s2_get_paper`, `s2_search_authors`, `s2_get_author`

## situational-awareness

Assembles a real-time situational picture for a place in Korea by orchestrating ArcSolve MCP weather, air-quality, and emergency-room tools — geocoding the location, then reading current/forecast weather (Open-Meteo), real-time fine-dust/air quality (AirKorea), and emergency-room bed availability or severe-case acceptance (E-Gen). Use when a user asks what conditions are like right now in a Korean place, combines weather with air quality, needs the nearest available ER, or wants an at-a-glance outdoor/safety readout — whenever one domain alone is not enough.

오케스트레이션 도구: `openmeteo_geocode`, `openmeteo_forecast`, `airkorea_realtime_by_region`, `airkorea_realtime_by_station`, `airkorea_forecast`, `egen_realtime_beds`, `egen_severe_acceptance`, `egen_list`

## wikipedia-lookup

Looks up encyclopedic background on a topic, entity, or term in Wikipedia via the ArcSolve MCP tools — finding the right article, then reading its summary and (only when needed) full extract, outgoing links, and Wikidata id. Use when you need quick factual context, to disambiguate a name, verify a fact, or find the canonical article for an entity — when a single authoritative source is enough.

오케스트레이션 도구: `wikipedia_search`, `wikipedia_summary`, `wikipedia_extract`, `wikipedia_links`

