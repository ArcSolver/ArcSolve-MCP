# 서비스 카탈로그

> ⚙️ 자동 생성 — 직접 수정하지 마세요. `arcsolve-mcp catalog`로 재생성됩니다.

현재 **23개 서비스 · 총 87개 도구**.

## airkorea — 에어코리아 대기오염정보 읽기(시도·측정소 실시간 측정 + 예보)
공식 문서: https://www.data.go.kr/data/15073861/openapi.do

| 도구 | 설명 |
|------|------|
| `airkorea_forecast` | 대기질 예보통보를 조회한다(GET /getMinuDustFrcstDspth). |
| `airkorea_realtime_by_region` | 시도별 실시간 측정정보를 조회한다(GET /getCtprvnRltmMesureDnsty). |
| `airkorea_realtime_by_station` | 측정소별 실시간 측정정보를 조회한다(GET /getMsrstnAcctoRltmMesureDnsty). |

## airport — 인천국제공항 여객편 운항현황 읽기(실시간 출발·도착 — 편명·항공사·시각·터미널·게이트·상태)
공식 문서: https://www.data.go.kr/data/15140153/openapi.do

| 도구 | 설명 |
|------|------|
| `airport_arrivals` | 인천공항 여객편 도착현황을 조회한다(GET /StatusOfPassengerFlightsDeOdp/getPassengerArrivalsDeOdp). |
| `airport_departures` | 인천공항 여객편 출발현황을 조회한다(GET /StatusOfPassengerFlightsDeOdp/getPassengerDeparturesDeOdp). |

## arxiv — arXiv 학술 프리프린트 읽기(검색·id 조회, Atom XML)
공식 문서: https://info.arxiv.org/help/api/user-manual.html

| 도구 | 설명 |
|------|------|
| `arxiv_get` | arXiv id로 프리프린트 메타데이터를 조회한다(GET /api/query, id_list). |
| `arxiv_search` | arXiv에서 학술 프리프린트를 검색한다(GET /api/query, search_query). |

## crossref — Crossref 학술 메타데이터 읽기(works/journals 검색·조회)
공식 문서: https://github.com/CrossRef/rest-api-doc/blob/master/README.md

| 도구 | 설명 |
|------|------|
| `crossref_get_journal` | 단일 journal을 ISSN으로 조회한다(GET /journals/{issn}). |
| `crossref_get_work` | 단일 work를 DOI로 조회한다(GET /works/{doi}). |
| `crossref_search_journals` | Crossref에서 저널(journals)을 검색/나열한다(GET /journals). |
| `crossref_search_works` | Crossref에서 학술 출판물(works)을 검색/나열한다(GET /works). |

## discord — Discord — Webhook으로 채널에 메시지 전송
공식 문서: https://discord.com/developers/docs/resources/webhook

| 도구 | 설명 |
|------|------|
| `discord_create_message` | Bot 토큰으로 임의 채널에 메시지를 전송한다. |
| `discord_delete_message` | Webhook이 보낸 기존 메시지를 삭제한다. |
| `discord_edit_message` | Webhook이 보낸 기존 메시지를 편집한다(본문 교체). |
| `discord_list_messages` | Bot 토큰으로 채널의 최근 메시지를 조회한다. |
| `discord_send_embed` | Discord 채널에 Webhook으로 리치 임베드(카드) 1개를 전송한다. |
| `discord_send_message` | Discord 채널에 Webhook으로 메시지를 전송한다. |

## egen — E-Gen 응급의료정보 읽기(응급실 실시간 가용병상·중증질환 수용가능·응급의료기관 목록)
공식 문서: https://www.data.go.kr/data/15000563/openapi.do

| 도구 | 설명 |
|------|------|
| `egen_list` | 응급의료기관 목록정보를 조회한다(GET /getEgytListInfoInqire). |
| `egen_realtime_beds` | 응급실 실시간 가용병상정보를 조회한다(GET /getEmrrmRltmUsefulSckbdInfoInqire). |
| `egen_severe_acceptance` | 중증질환자 수용가능정보를 조회한다(GET /getSrsillDissAceptncPosblInfoInqire). |

## ev_charger — 전기차 충전소(한국환경공단) 정보·실시간 상태 읽기(충전소 정보 + 충전기 실시간 상태)
공식 문서: https://www.data.go.kr/data/15076352/openapi.do

| 도구 | 설명 |
|------|------|
| `evcharger_info` | 충전소 정보를 조회한다(GET /getChargerInfo). |
| `evcharger_status` | 충전기 실시간 상태를 조회한다(GET /getChargerStatus). |

## kakao — 카카오톡 메시지 — 나에게 보내기
공식 문서: https://developers.kakao.com/docs/latest/ko/kakaotalk-message/rest-api

| 도구 | 설명 |
|------|------|
| `kakao_send_link_to_me` | 카카오톡 '나에게 보내기'로 URL을 스크랩(미리보기 카드) 형태로 전송한다. |
| `kakao_send_text_to_me` | 카카오톡 '나에게 보내기'로 텍스트 메시지를 전송한다. |

## line — LINE Messaging API — 텍스트 메시지 전송(push/reply/multicast/broadcast) + 프로필 조회
공식 문서: https://developers.line.biz/en/reference/messaging-api/

| 도구 | 설명 |
|------|------|
| `line_broadcast_text` | LINE Messaging API broadcast로 모든 친구에게 텍스트 1건을 전송한다. |
| `line_get_profile` | LINE Messaging API로 사용자 프로필 정보를 조회한다. |
| `line_multicast_text` | LINE Messaging API multicast로 동일 텍스트를 여러 userId에게 전송한다. |
| `line_reply_text` | LINE Messaging API reply로 텍스트 메시지 1건을 회신한다. |
| `line_send_text` | LINE Messaging API push로 텍스트 메시지 1건을 전송한다. |

## notion — Notion 워크스페이스 읽기(search·pages·blocks·databases·data sources)
공식 문서: https://developers.notion.com/reference/intro

| 도구 | 설명 |
|------|------|
| `notion_get_block_children` | 블록(또는 페이지)의 자식 블록을 나열해 본문을 읽는다(GET /blocks/{id}/children). |
| `notion_get_data_source` | data source의 스키마(프로퍼티)를 조회한다(GET /data_sources/{id}). |
| `notion_get_database` | database를 조회해 자식 data source 목록을 얻는다(GET /databases/{id}). |
| `notion_get_page` | 단일 페이지의 메타데이터를 조회한다(GET /pages/{id}). |
| `notion_query_data_source` | data source의 행(page)을 쿼리한다(POST /data_sources/{id}/query). |
| `notion_search` | Notion 워크스페이스에서 page/data source를 제목으로 검색한다(POST /search). |

## nws — NWS 미국 날씨 읽기(예보·시간별 예보·활성 기상특보)
공식 문서: https://www.weather.gov/documentation/services-web-api

| 도구 | 설명 |
|------|------|
| `nws_alerts` | 미국 주(state)의 활성 기상특보를 조회한다(GET /alerts/active?area={ST}). |
| `nws_forecast` | 미국 좌표의 다단계(12시간 주야) 예보를 조회한다(2단계: /points → /gridpoints). |
| `nws_hourly_forecast` | 미국 좌표의 시간별 예보를 조회한다(2단계: /points → /gridpoints/.../forecast/hourly). |

## openalex — OpenAlex 학술 그래프 읽기(works/authors 검색·조회)
공식 문서: https://developers.openalex.org/how-to-use-the-api/api-overview

| 도구 | 설명 |
|------|------|
| `openalex_get_author` | 단일 author를 조회한다(GET /authors/{id}). |
| `openalex_get_work` | 단일 work를 조회한다(GET /works/{id}). |
| `openalex_search_authors` | OpenAlex에서 저자(authors)를 검색/나열한다(GET /authors). |
| `openalex_search_works` | OpenAlex에서 학술 논문(works)을 검색/나열한다(GET /works). |

## openmeteo — Open-Meteo 날씨·기후 읽기(예보·지오코딩)
공식 문서: https://open-meteo.com/en/docs

| 도구 | 설명 |
|------|------|
| `openmeteo_forecast` | 좌표의 날씨 예보를 조회한다(GET api /v1/forecast). |
| `openmeteo_geocode` | 지명을 좌표·국가·시간대로 변환한다(GET geocoding-api /v1/search). |

## parking — 한국교통안전공단 전국 주차장 정보 읽기(시설·운영 + 실시간 잔여면 ⭐ 연동 주차장 한정)
공식 문서: https://www.data.go.kr/data/15099883/openapi.do

| 도구 | 설명 |
|------|------|
| `parking_operation` | 전국 주차장 운영정보를 조회한다(GET /B553881/Parking/PrkOprInfo). |
| `parking_realtime` | 전국 주차장 실시간 잔여 주차면을 조회한다(GET /B553881/Parking/PrkRealtimeInfo). ⭐ |
| `parking_search` | 전국 주차장 시설정보를 조회한다(GET /B553881/Parking/PrkSttusInfo). |

## pubmed — PubMed(NCBI E-utilities) 생의학 문헌 읽기(검색·요약·abstract)
공식 문서: https://www.ncbi.nlm.nih.gov/books/NBK25500/

| 도구 | 설명 |
|------|------|
| `pubmed_fetch_abstract` | PMID로 초록(abstract) 본문을 가져온다(GET efetch.fcgi, rettype=abstract&retmode=xml). |
| `pubmed_get_summary` | PMID로 논문 요약(제목·저자·저널·날짜·DOI)을 조회한다(GET esummary.fcgi, retmode=json). |
| `pubmed_search` | PubMed에서 생의학 문헌을 검색해 PMID 목록을 받는다(GET esearch.fcgi, db=pubmed). |

## semanticscholar — Semantic Scholar 학술 그래프 읽기(papers/authors 검색·조회)
공식 문서: https://api.semanticscholar.org/api-docs/graph

| 도구 | 설명 |
|------|------|
| `s2_get_author` | 단일 author를 조회한다(GET /author/{id}). |
| `s2_get_paper` | 단일 paper를 조회한다(GET /paper/{id}). |
| `s2_search_authors` | Semantic Scholar에서 저자(authors)를 검색한다(GET /author/search). |
| `s2_search_papers` | Semantic Scholar에서 논문(papers)을 relevance 검색한다(GET /paper/search). |

## seoul_transit — 서울 실시간 교통 읽기(지하철 도착·따릉이 대여소)
공식 문서: https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do

| 도구 | 설명 |
|------|------|
| `seoul_bike_status` | 서울 따릉이 대여소의 실시간 현황을 조회한다(GET bikeList). |
| `seoul_subway_arrivals` | 서울 지하철 역의 실시간 도착정보를 조회한다(GET realtimeStationArrival). |

## tago_transit — TAGO 전국 대중교통 통합 읽기(버스 도착·정류소·노선 + 고속/시외버스 + 열차)
공식 문서: https://www.data.go.kr/data/15098530/openapi.do

| 도구 | 설명 |
|------|------|
| `tago_bus_arrivals` | 정류소별 버스 실시간 도착예정을 조회한다(GET /ArvlInfoInqireService/…ArvlPrearngeInfoList). |
| `tago_bus_route` | 노선의 경유정류소 목록을 조회한다(GET /BusRouteInfoInqireService/…ThrghSttnList). |
| `tago_city_codes` | 전국 도시코드 목록을 조회한다(GET /ArvlInfoInqireService/getCtyCodeList). |
| `tago_express_bus` | 고속버스 운행을 조회한다(GET /ExpBusInfoService/getStrtpntAlocFndExpbusInfo). |
| `tago_intercity_bus` | 시외버스 운행을 조회한다(GET /SuburbsBusInfoService/getStrtpntAlocFndSuberbsBusInfo). |
| `tago_search_bus_stops` | 정류소명으로 정류소를 검색한다(GET /BusSttnInfoInqireService/getSttnNoList). |
| `tago_train` | 도시간 열차 운행을 조회한다(GET /TrainInfoService/getStrtpntAlocFndTrainInfo). |

## telegram — Telegram Bot API — 텍스트/사진/문서 전송, 메시지 편집·삭제, getMe 헬스체크
공식 문서: https://core.telegram.org/bots/api

| 도구 | 설명 |
|------|------|
| `telegram_delete_message` | 봇이 접근 가능한 메시지를 삭제한다(deleteMessage). |
| `telegram_edit_message_text` | 메시지의 텍스트를 편집한다(editMessageText). |
| `telegram_get_me` | 봇 신원/토큰 유효성을 확인한다(getMe). 헬스체크용. 파라미터 없음. |
| `telegram_send_document` | Telegram 봇으로 문서(파일)를 전송한다(sendDocument). |
| `telegram_send_message` | Telegram 봇으로 텍스트 메시지를 전송한다(sendMessage). |
| `telegram_send_photo` | Telegram 봇으로 사진을 전송한다(sendPhoto). |

## usgs_quake — USGS 지진 정보 읽기(FDSN Event API — 검색·건수, GeoJSON)
공식 문서: https://earthquake.usgs.gov/fdsnws/event/1/

| 도구 | 설명 |
|------|------|
| `usgs_count_earthquakes` | 조건에 매칭되는 지진 건수만 센다(GET /count?format=geojson). |
| `usgs_search_earthquakes` | USGS에서 지진 이벤트를 검색/나열한다(GET /query?format=geojson). |

## wikidata — Wikidata 읽기(엔티티 검색·단건 조회·statements·SPARQL)
공식 문서: https://www.wikidata.org/wiki/Wikidata:Data_access

| 도구 | 설명 |
|------|------|
| `wikidata_entity` | 단일 엔티티(item Q… 또는 property P…)를 조회한다(REST v1 /entities). |
| `wikidata_search` | Wikidata에서 엔티티를 검색한다(Action API wbsearchentities). |
| `wikidata_sparql` | WDQS에 SPARQL 쿼리를 실행한다(GET /sparql, format=json). |
| `wikidata_statements` | item의 statements(속성→값)를 조회한다(REST v1 /entities/items/{id}/statements). |

## wikipedia — 위키백과 읽기(검색·요약·본문·링크)
공식 문서: https://www.mediawiki.org/wiki/API:REST_API/Reference

| 도구 | 설명 |
|------|------|
| `wikipedia_extract` | 문서 평문 본문을 조회한다(TextExtracts: GET /w/api.php?action=query&prop=extracts). |
| `wikipedia_links` | 문서의 나가는 링크와 분류를 조회한다(Action API: prop=links|categories). |
| `wikipedia_search` | 위키백과에서 문서를 검색한다(클린 REST: GET /w/rest.php/v1/search/page). |
| `wikipedia_summary` | 문서의 lead 요약(extract)을 조회한다(rest_v1: GET /api/rest_v1/page/summary/{title}). |

## zotero — Zotero 라이브러리 읽기(Web API v3 + 로컬 데스크톱 API)
공식 문서: https://www.zotero.org/support/dev/web_api/v3/basics

| 도구 | 설명 |
|------|------|
| `zotero_get_collection_items` | 컬렉션의 아이템을 나열한다(GET /{prefix}/collections/{collectionKey}/items). |
| `zotero_get_fulltext` | 첨부 아이템의 전문(full-text)을 조회한다(GET /{prefix}/items/{itemKey}/fulltext). |
| `zotero_get_item` | 단일 아이템을 조회한다(GET /{prefix}/items/{itemKey}). |
| `zotero_get_item_children` | 아이템의 자식(노트/첨부)을 나열한다(GET /{prefix}/items/{itemKey}/children). |
| `zotero_health` | 백엔드 연결/설정 상태를 점검한다. |
| `zotero_list_collections` | 컬렉션을 나열한다(GET /{prefix}/collections, top=True면 /collections/top). |
| `zotero_list_tags` | 라이브러리의 태그를 나열한다(GET /{prefix}/tags). |
| `zotero_search_items` | Zotero 라이브러리에서 아이템을 검색/나열한다(GET /{prefix}/items). |

