# Changelog

이 프로젝트의 주요 변경 사항. Keep a Changelog 형식 · SemVer 준수.

<!-- BEGIN UNRELEASED -->
## [Unreleased]

- **arxiv**: arXiv 학술 프리프린트 읽기 서비스 추가 — 검색·id 조회 2개 GET 도구(`arxiv_search`/`arxiv_get`), 무인증, **Atom 1.0 XML** 응답을 표준 라이브러리 `xml.etree.ElementTree`로 파싱(외부 의존 없음), HTTP 200 error-entry(title='Error') 감지·매핑, max_results 기본 10·총 ≤30000(초과 HTTP 400)
- **core**: `get_text` HTTP 동사 추가 — 비-JSON 본문(arXiv Atom XML 등)을 raw str로 반환(get_json과 동형, 4xx/5xx UpstreamError 매핑)
- **core**: 레지스트리 지연·격리 로딩(한 서비스 오류가 전체를 죽이지 않음, 선택 서비스만 import)
- **core**: auth 레지스트리 일반화(`Service.make_auth_client`) — 새 OAuth 서비스가 코어 수정 없이 인증
- **core**: OAuth PKCE(S256) + 토큰 파일 0600/디렉토리 0700
- **core**: 공통 HTTP 동사 추가(`get_json`/`post_json`/`patch_json`/`delete_json`/`post_multipart`) + 의존성 격리 규칙
- **core**: provenance 강제 테스트 + GitHub Actions CI(pytest·ruff·카탈로그/체인지로그 drift)
- **core**: 도구 런타임 기능 테스트(요청 조립·응답 파싱·에러 매핑) + MCP 배선 스모크 추가; tools/service의 fastmcp import를 TYPE_CHECKING으로 이동(도구 모듈 런타임 의존 제거)
- **core**: LICENSE(Apache-2.0)·CONTRIBUTING 추가
- **crossref**: Crossref 학술 메타데이터 읽기 서비스 추가 — works/journals 검색·단건 조회 4개 GET 도구(`crossref_search_works`/`crossref_get_work`/`crossref_search_journals`/`crossref_get_journal`), 무인증·polite pool 이메일(`CROSSREF_MAILTO`)은 선택 쿼리 파라미터+User-Agent, 본문 message 기반 건수 안내(rows 0–1000·offset 0–10000)
- **discord**: Webhook 메시지 전송 MCP 추가 — `discord_send_message`
- **discord**: 핵심 도구 확장 — Webhook 임베드/편집/삭제(`discord_send_embed`·`discord_edit_message`·`discord_delete_message`) + Bot 토큰 경로(`discord_create_message`·`discord_list_messages`, `DISCORD_BOT_TOKEN`)
- **kakao**: '나에게 보내기' MCP 추가 — `kakao_send_text_to_me`, `kakao_send_link_to_me`
- **line**: LINE Messaging API push 텍스트 MCP 추가 — `line_send_text`(전송 메시지 id 반환)
- **line**: push 응답 계약을 공식 스펙(`sentMessages[]`)에 맞게 수정, text 길이를 UTF-16 코드 유닛으로 검증
- **line**: 코어 도구 확장 — `line_reply_text`(reply, sentMessages), `line_multicast_text`(userId 최대 500, 빈 응답), `line_broadcast_text`(빈 응답), `line_get_profile`(Profile 조회) 추가
- **notion**: Notion 워크스페이스 읽기 서비스 추가 — search·page·block children·database·data source 조회/쿼리 6개 도구(`notion_search`/`notion_get_page`/`notion_get_block_children`/`notion_get_database`/`notion_get_data_source`/`notion_query_data_source`), 필수 Bearer 토큰(`NOTION_TOKEN`), API 버전 2026-03-11 핀 고정(data source 모델)
- **openalex**: OpenAlex 학술 그래프 읽기 서비스 추가 — works/authors 검색·단건 조회 4개 GET 도구(`openalex_search_works`/`openalex_get_work`/`openalex_search_authors`/`openalex_get_author`), API 키·mailto는 선택 쿼리 파라미터(키 없이도 동작), 본문 meta 기반 건수 안내
- **openmeteo**: Open-Meteo 날씨·기후 읽기 서비스 추가 — 예보·지오코딩 2개 GET 도구(`openmeteo_geocode`/`openmeteo_forecast`), 무인증(키·env 불필요·식별 User-Agent만), hourly/daily/current는 콤마 구분 변수명 문자열 그대로 전달(검증 상류 위임), 동적 변수 블록은 dict로 수신(`forecast_days` 0–16·`count` 1–100), 지오코딩 무매칭 시 `results` 키 부재 안전 처리, 에러 봉투 `{error,reason}`(400) 매핑
- **repo**: README 상단 배지(CI · License · Python) 추가, 저장소 public 공개
- **semanticscholar**: Semantic Scholar 학술 그래프 읽기 서비스 추가 — papers/authors 검색·단건 조회 4개 GET 도구(`s2_search_papers`/`s2_get_paper`/`s2_search_authors`/`s2_get_author`), API 키는 선택 `x-api-key` 헤더(키 없이 공유 풀로 동작·전용 풀 1 RPS), `fields` 콤마 구분 필드 선택, 본문 `total`/`offset`/`next` 기반 건수 안내(paper limit≤100·offset+limit<1000, author limit≤1000)
- **telegram**: sendMessage 기반 telegram_send_message 추가
- **telegram**: 코어 도구 확장 — getMe(헬스체크)/sendPhoto/sendDocument/editMessageText/deleteMessage 추가
- **telegram**: sendPhoto/sendDocument 로컬 파일 multipart 업로드 지원(사진≤10MB·파일≤50MB), editMessageText inline_message_id 경로 추가
- **zotero**: Zotero 라이브러리 읽기 서비스 추가(Web API v3 + 로컬 데스크톱 API 단일 서비스·백엔드 전환) — 검색/아이템/자식/컬렉션/컬렉션 아이템/태그/전문/헬스 8개 GET 도구, 응답 헤더 기반 페이지네이션 안내
<!-- END UNRELEASED -->
