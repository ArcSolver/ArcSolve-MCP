# Zotero 서비스

Zotero 라이브러리 **읽기** 래퍼 — 검색·아이템·컬렉션·태그·전문(full-text). **한 서비스 = 두 백엔드**:
공개/개인 **Web API v3**와 **로컬 데스크톱 API**(Zotero 앱). 로컬 API가 Web API v3를 미러하므로
경로·쿼리·응답 모델이 동일하고, 차이는 base URL + 인증뿐이다.

## 계약 출처 (공식 문서)
- Web API v3 basics(엔드포인트·쿼리·페이지네이션·백오프·제약): https://www.zotero.org/support/dev/web_api/v3/basics
- 아이템 타입·필드: https://www.zotero.org/support/dev/web_api/v3/types_and_fields
- 전문(Full-Text) 콘텐츠 포맷: https://www.zotero.org/support/dev/web_api/v3/fulltext_content
- 로컬 API 1차 출처(공식 레포 소스 주석 — 전용 산문 문서 없음): https://github.com/zotero/zotero/blob/main/chrome/content/zotero/xpcom/server/server_localAPI.js

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 경로 빌더·쿼리 제약·응답 모델).

## 백엔드 (web / local)
`ZoteroSettings`(`ZOTERO_*`)가 `_resolve() -> (base, prefix, headers, source)`로 분기한다.

| | base URL | prefix | 인증 헤더 | 쓰기 |
|---|---|---|---|---|
| **web** | `https://api.zotero.org` | `users/<ZOTERO_USER_ID>` 또는 `groups/<ZOTERO_GROUP_ID>` | `Zotero-API-Key: <키>` + `Zotero-API-Version: 3`(공개 라이브러리면 키 생략) | (이 서비스는 읽기만) |
| **local** | `ZOTERO_LOCAL_BASE`(기본 `http://localhost:23119/api`) | 항상 `users/0` | `Zotero-API-Version: 3`(무인증) | 불가(로컬 API 읽기 전용) |

- `ZOTERO_SOURCE` = `web` | `local` | 미지정(auto: `ZOTERO_API_KEY` 있으면 web, 없으면 local).
- 로컬 API는 Zotero 데스크톱의 pref `httpServer.localAPI.enabled`가 켜져 있어야 한다(끄면 403).

## 엔드포인트 (전부 GET · `<base>/<prefix>/…`)
| 도구 | METHOD · PATH |
|------|------|
| 검색/나열 | `GET /{prefix}/items?q=&qmode=&itemType=&tag=&sort=&limit=&start=` |
| 단건 | `GET /{prefix}/items/{itemKey}?include=` |
| 자식 | `GET /{prefix}/items/{itemKey}/children` |
| 컬렉션 목록 | `GET /{prefix}/collections`(+`/top`) |
| 컬렉션 아이템 | `GET /{prefix}/collections/{collectionKey}/items` |
| 태그 | `GET /{prefix}/tags` |
| 전문 | `GET /{prefix}/items/{itemKey}/fulltext` |

> 페이지네이션/버전/백오프는 **응답 헤더**에 실린다: `Total-Results`, `Link`(rel=next 등), `Last-Modified-Version`, `Backoff`/`Retry-After`(429/503). list/search 도구는 코어 `get_with_headers` + `parse_link_header`로 "총 N건 중 M건, 다음 start=K"를 안내한다.

## 셋업
**web**
1. [Zotero 설정 > Feeds/API](https://www.zotero.org/settings/keys)에서 **API 키** 발급(개인 라이브러리면 필요, 공개 라이브러리는 생략 가능).
2. `.env`:
   - `ZOTERO_SOURCE=web`
   - `ZOTERO_API_KEY=<키>` (공개 라이브러리면 생략 가능)
   - `ZOTERO_USER_ID=<숫자 userID>` 또는 `ZOTERO_GROUP_ID=<숫자 groupID>`(그룹 지정 시 그룹 우선)

**local**
1. Zotero 데스크톱에서 로컬 API 활성(pref `httpServer.localAPI.enabled`).
2. `.env`: `ZOTERO_SOURCE=local` (필요 시 `ZOTERO_LOCAL_BASE`로 포트/주소 변경).

> 사전발급 API 키(헤더) 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve auth zotero` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `zotero_search_items(q?, item_type?, tag?, limit?, start?, qmode?)` | 아이템 검색/나열. `qmode=everything`이면 전문 포함 검색. limit 기본 25·최대 100 |
| `zotero_get_item(item_key, include?)` | 단일 아이템 조회. `include`(예: `data,bib,citation`) 기본 data |
| `zotero_get_item_children(item_key)` | 아이템의 자식(노트/첨부) 나열 |
| `zotero_list_collections(top?)` | 컬렉션 나열(`top=True`면 최상위만) |
| `zotero_get_collection_items(collection_key, limit?, start?)` | 컬렉션 내 아이템 나열 |
| `zotero_list_tags(limit?, start?)` | 태그 나열 |
| `zotero_get_fulltext(item_key)` | 첨부 전문 + 인덱싱 메타(텍스트=chars / PDF=pages) |
| `zotero_health()` | 백엔드 연결/설정 점검(local 활성·web 키/유저 도달) |

## 범위 / 제약 (공식)
- **읽기만.** write는 미지원(로컬 API는 읽기 전용, web write는 v2 범위 밖). 파일 바이너리 다운로드, 비-JSON 포맷(bib/RIS 등), 그룹 상세는 제외.
- `limit` 기본 **25**, 최대 **100**. 다중 itemKey 요청은 최대 **50**개, `bib` 포맷은 최대 **150**개(향후 확장 시 적용).
- 로컬 라이브러리 prefix는 항상 `users/0`(로그인 사용자만).

## UNVERIFIED / provenance 노트
- 최상위 read 오브젝트 키 `key`/`version`/`library`/`links`/`meta`/`data`는 공식 Read Requests에 일관되게 등장한다. 그러나 `library`/`links`/`meta` **서브객체의 정확한 키**는 공식 산문으로 완전히 확인되지 않아(UNVERIFIED) 해당 모델은 `extra="ignore"` + `dict`로 느슨히 받는다(`contract.py`의 `# TODO(provenance)` 참고). `data`는 아이템 타입별 가변이라 `dict`.

## 확장 포인트
- `include=bib,citation`/CSL 스타일, 다중 itemKey(`?itemKey=A,B,C`, ≤50), 버전 조건부 요청(`If-Modified-Since-Version`), `/items/{key}/tags` 등은 동일 패턴으로 도구·경로 빌더 추가.
