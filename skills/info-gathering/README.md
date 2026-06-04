# info-gathering (정보 수집)

열린 웹의 **새 소식을 모아 다이제스트**로 묶는 **다중 서비스 오케스트레이션** 스킬: 임의 RSS/Atom/RDF
피드 + 해커뉴스(랭킹·검색·스레드·사용자)를 가로질러 링크 기준으로 중복을 제거하고 날짜순 다이제스트로
정리한다. 전부 읽기 전용·무인증. 📡 정보수집 번들의 페어 스킬.

> 이 스킬은 상류 API를 직접 치지 않고 **ArcSolve MCP 도구를 오케스트레이션**한다(AGENTS.md 규칙 2-2).
> 검증된 계약은 각 서비스의 `contract.py`에 단일 출처로 남는다.

## 계약 출처 (공식 문서)
스킬이 기대는 MCP 서비스들의 검증된 계약:
- RSS 명세: https://www.rssboard.org/rss-specification
- Hacker News API: https://github.com/HackerNews/API

## 필요 MCP 도구
ArcSolve MCP 서버에서 아래 도구가 노출돼 있어야 한다(`SKILL.md`의 `allowed-tools`와 일치):
- 피드 — `feeds_fetch`
- 해커뉴스 — `hn_top`, `hn_search`, `hn_item`, `hn_user`

> 셋업: `arcsolve serve feeds hackernews` (또는 `ARCSOLVE_SERVICES=feeds,hackernews`). 무인증·읽기 전용.

## 범위 / 경계
- **포함**: 임의 피드 가져오기·요약 + 해커뉴스 랭킹/검색/스레드/사용자 조회를 링크 기준 중복제거해 날짜순 다이제스트로 통합.
- **읽기 전용**: 게시·투표·댓글을 하지 않는다.
- **SSRF 안전**: `feeds_fetch`가 URL 호스트를 검증한다(코어가 내부망/메타데이터 주소 차단) — 사용자 URL을 그대로 넘기면 도구가 막는다.
- **범용 웹검색 아님**: 주어진 피드 + 해커뉴스를 읽을 뿐 열린 웹을 크롤하지 않는다. 합성/의견 생성 X.
- **제외(다른 스킬)**: 다이제스트 전송은 메시징 도구로 **안내만**(직접 수행 X).

## 품질 검증
- 정적 테스트: [`tests/test_info_gathering_skill.py`](../../tests/test_info_gathering_skill.py)
  — frontmatter·`allowed-tools`↔실재 도구·다중 서비스 교차 불변식.
- eval: [`evals/`](evals/) — skill-creator 하니스(비결정적, pytest CI와 별개).
