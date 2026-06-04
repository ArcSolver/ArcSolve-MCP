# 스킬 카탈로그

> ⚙️ 자동 생성 — 직접 수정하지 마세요. `arcsolve catalog`로 재생성됩니다.

현재 **6개 스킬**. 스킬은 실행 중인 MCP 도구를 오케스트레이션한다(검증된 계약은 MCP 서비스 쪽 단일 출처).

## academic-discovery

Discovers and cross-references scholarly papers across multiple academic databases (arXiv, Crossref, OpenAlex, PubMed, Semantic Scholar) via the ArcSolve MCP tools. Use when finding papers on a topic, locating a specific work across sources, tracing citations or an author's output, or triangulating metadata — whenever one database's search is not enough.

오케스트레이션 도구: `arxiv_search`, `arxiv_get`, `crossref_search_works`, `crossref_get_work`, `openalex_search_works`, `openalex_get_work`, `openalex_search_authors`, `openalex_get_author`, `pubmed_search`, `pubmed_get_summary`, `pubmed_fetch_abstract`, `s2_search_papers`, `s2_get_paper`, `s2_search_authors`, `s2_get_author`

## info-gathering

Gathers and tracks fresh web content by orchestrating ArcSolve MCP reading tools — pulling RSS/Atom/RDF feeds (news, blogs, release notes, YouTube channels) and Hacker News (front-page ranking, search, item threads, user activity). Use when a user wants a digest of what's new across sources, to monitor a topic or a set of feeds, to surface trending tech discussion, or to follow a specific HN thread or author — whenever one source is not enough.

오케스트레이션 도구: `feeds_fetch`, `hn_top`, `hn_search`, `hn_item`, `hn_user`

## journey-planning

Plans a real-time, multi-modal trip across Korea by orchestrating ArcSolve MCP transit tools — subway and bus arrivals, intercity/express bus and rail schedules, airport flight status, public-bike availability, and (at the destination) parking vacancy and EV-charger status. Use when a user asks how to get somewhere in Korea, when the next bus/subway/train arrives, whether there's parking or an open EV charger at the destination, or to assemble an at-a-glance door-to-door plan combining several live sources.

오케스트레이션 도구: `seoul_subway_arrivals`, `seoul_bike_status`, `tago_search_bus_stops`, `tago_bus_arrivals`, `tago_bus_route`, `tago_express_bus`, `tago_intercity_bus`, `tago_train`, `tago_city_codes`, `airport_arrivals`, `airport_departures`, `parking_search`, `parking_realtime`, `ev_charger_status`, `ev_charger_info`

## messaging-routing

Routes a message or notification to the right chat channel by orchestrating ArcSolve MCP messaging tools — Kakao (note-to-self), Telegram (text/photo/document), Discord (message/embed), and LINE (push/multicast/broadcast). Use when a user wants to send or broadcast a notification, pick the appropriate channel for an audience, fan a message out to several channels, or format the same content correctly per platform — whenever delivery spans more than one messaging service.

오케스트레이션 도구: `kakao_send_text_to_me`, `kakao_send_link_to_me`, `telegram_send_message`, `telegram_send_photo`, `telegram_send_document`, `discord_send_message`, `discord_send_embed`, `line_send_text`, `line_multicast_text`, `line_broadcast_text`

## situational-awareness

Assembles a real-time situational picture for a place in Korea by orchestrating ArcSolve MCP weather, air-quality, and emergency-room tools — geocoding the location, then reading current/forecast weather (Open-Meteo), real-time fine-dust/air quality (AirKorea), and emergency-room bed availability or severe-case acceptance (E-Gen). Use when a user asks what conditions are like right now in a Korean place, combines weather with air quality, needs the nearest available ER, or wants an at-a-glance outdoor/safety readout — whenever one domain alone is not enough.

오케스트레이션 도구: `openmeteo_geocode`, `openmeteo_forecast`, `airkorea_realtime_by_region`, `airkorea_realtime_by_station`, `airkorea_forecast`, `egen_realtime_beds`, `egen_severe_acceptance`, `egen_list`

## wikipedia-lookup

Looks up encyclopedic background on a topic, entity, or term in Wikipedia via the ArcSolve MCP tools — finding the right article, then reading its summary and (only when needed) full extract, outgoing links, and Wikidata id. Use when you need quick factual context, to disambiguate a name, verify a fact, or find the canonical article for an entity — when a single authoritative source is enough.

오케스트레이션 도구: `wikipedia_search`, `wikipedia_summary`, `wikipedia_extract`, `wikipedia_links`

