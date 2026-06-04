# hackernews 서비스

Hacker News **읽기** 래퍼 — 아이템·프론트페이지 랭킹·전문 검색·사용자 프로필.
전부 GET·**무인증**(키 없음). 두 공식 API를 합성한다 — 구조적 데이터는 **Firebase**,
전문 검색은 **Algolia HN Search**. 둘 다 JSON이라 코어 `get_json`을 쓴다.

## 계약 출처 (공식 문서)
- Firebase API: https://github.com/HackerNews/API
- Algolia HN Search API: https://hn.algolia.com/api

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 상수·랭킹 매핑·JSON→pydantic 모델).

## 인증 (없음)
무인증이다. 키·토큰·env 설정이 필요 없다.

> 무인증이므로 `arcsolve-mcp auth hackernews` 단계는 없다.

## 엔드포인트 (전부 GET)
| 종류 | METHOD · PATH |
|------|------|
| 아이템 | `GET https://hacker-news.firebaseio.com/v0/item/{id}.json` |
| 사용자 | `GET https://hacker-news.firebaseio.com/v0/user/{id}.json` |
| 랭킹 | `GET https://hacker-news.firebaseio.com/v0/{top\|new\|best\|ask\|show\|job}stories.json` |
| 검색(관련도) | `GET https://hn.algolia.com/api/v1/search?query=&tags=&hitsPerPage=` |
| 검색(최신) | `GET https://hn.algolia.com/api/v1/search_by_date?query=` |

> Firebase 랭킹 엔드포인트는 **id 배열만** 준다 → `hn_top`은 상위 N개를 개별 조회한다(N+1).
> `asyncio.gather`로 병렬화하고 상한(50)으로 호출 폭증을 막는다.

### 응답 (JSON)
- **item**: `id`·`type`(story/comment/job/poll/pollopt)·`by`·`time`(unix)·`text`(HTML)·`title`(HTML)·`url`·`score`·`descendants`(댓글 수)·`kids`·`parent`·`deleted`·`dead`.
- **user**: `id`·`created`(unix)·`karma`·`about`(HTML)·`submitted`.
- **Algolia hit**: `objectID`·`title`·`url`·`author`·`points`·`num_comments`·`created_at`·`story_text`·`comment_text`.

## 셋업
1. 키 발급 단계 없음(무인증). `.env` 변경 불필요.

## 도구
| 도구 | 설명 |
|------|------|
| `hn_item(id)` | 아이템 조회. story/job=제목·점수·댓글·작성자·시간·URL·본문, comment=본문·부모 |
| `hn_top(kind?, limit?)` | 랭킹 상위 항목. `kind`=top/new/best/ask/show/job(기본 top), `limit` 1..50 |
| `hn_search(query, by_date?, tags?, limit?)` | Algolia 전문 검색. `by_date`=최신순, `tags`=필터 문자열, `limit` 1..50 |
| `hn_user(id)` | 사용자 프로필(karma·가입·about·제출 수) |

## 범위 / 제약
- **읽기만.** 글쓰기·투표·로그인은 비목표(API 자체가 읽기 전용).
- `time`/`created`는 unix timestamp → `YYYY-MM-DD HH:MM UTC`로 표시.
- `title`/`text`/`about`은 HTML을 담아 평문화한다(태그 제거·엔티티 복원·길이 제한).
- `hn_top` 상한 50(N+1 비용). 댓글 트리 전체 펼치기는 비목표(`kids` id만 노출).
- `hn_search` `tags`는 빌더 없이 **문자열 그대로** 전달한다(arxiv `search_query`와 동형).

## provenance 노트
- 랭킹 종류→엔드포인트 매핑(`top`→`topstories` …)은 공식 README 표기를 그대로 박제.
- Algolia 정렬: `/search`=관련도(→점수→댓글수), `/search_by_date`=최신순(공식 문서).
- 삭제(`deleted`)·죽은(`dead`) 아이템은 빈/부분 응답이라 도구가 방어적으로 처리한다.

## 확장 포인트
- 댓글 트리 재귀 조회, `numericFilters`(점수/날짜 범위), 페이지네이션(`page`/`nbPages`),
  `/v0/maxitem`·`/v0/updates`(증분 폴링)는 동일 패턴으로 확장 가능.
