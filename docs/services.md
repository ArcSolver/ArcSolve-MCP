# 서비스 카탈로그

> ⚙️ 자동 생성 — 직접 수정하지 마세요. `arcsolve-mcp catalog`로 재생성됩니다.

현재 **15개 서비스 · 총 60개 도구**.

## airkorea — 에어코리아 대기오염정보 읽기(시도·측정소 실시간 측정 + 예보)
공식 문서: https://www.data.go.kr/data/15073861/openapi.do

| 도구 | 설명 |
|------|------|
| `airkorea_forecast` | 대기질 예보통보를 조회한다(GET /getMinuDustFrcstDspth). |
| `airkorea_realtime_by_region` | 시도별 실시간 측정정보를 조회한다(GET /getCtprvnRltmMesureDnsty). |
| `airkorea_realtime_by_station` | 측정소별 실시간 측정정보를 조회한다(GET /getMsrstnAcctoRltmMesureDnsty). |

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

