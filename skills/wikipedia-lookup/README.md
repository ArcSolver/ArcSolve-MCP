# wikipedia-lookup (위키백과 조회)

위키백과에서 주제·엔티티·용어의 배경을 **검색 → 요약 → (필요시) 심화**로 조회하는 미니멀
**단일소스** 스킬. `academic-discovery`(멀티소스 삼각검증)와 대비되는, 한 권위 출처로 충분할 때의
깔끔한 순차 워크플로 예시다.

> 이 스킬은 상류 API를 직접 치지 않고 **ArcSolve MCP 도구를 오케스트레이션**한다(AGENTS.md 규칙 2-2).
> 검증된 계약은 `wikipedia` 서비스의 `contract.py`에 단일 출처로 남는다(스킬은 계약을 재정의하지 않는다).

## 계약 출처 (공식 문서)
스킬이 기대는 MCP 서비스(`wikipedia`)의 검증된 계약:
- per-wiki REST(검색): https://www.mediawiki.org/wiki/API:REST_API/Reference
- Wikimedia REST API(rest_v1 요약): https://www.mediawiki.org/wiki/Wikimedia_REST_API
- TextExtracts(본문): https://www.mediawiki.org/wiki/Extension:TextExtracts
- Action API Query(링크·분류): https://www.mediawiki.org/wiki/API:Query

## 필요 MCP 도구
ArcSolve MCP 서버에서 아래 도구가 노출돼 있어야 한다(`SKILL.md`의 `allowed-tools`와 일치):
- Wikipedia — `wikipedia_search`, `wikipedia_summary`, `wikipedia_extract`, `wikipedia_links`

> 셋업: `arcsolve-mcp serve wikipedia` (또는 `ARCSOLVE_SERVICES=wikipedia`). 읽기 전용·무인증으로
> 동작하지만 Wikimedia는 식별용 `User-Agent`를 요구한다(`WIKIPEDIA_USER_AGENT` 권장) — 서비스 README 참고.

## 범위 / 경계
- **포함**: 문서 검색·lead 요약·평문 본문·나가는 링크/분류 조회, 동음이의 해소, Wikidata Q-id 브리지 안내.
- **제외(다른 스킬)**: 멀티소스 학술 탐색(`academic-discovery`), 위키데이터 구조화 조회(`wikidata_*`),
  편집/쓰기, 내러티브 합성.

## 품질 검증
- 정적 테스트: [`tests/test_wikipedia_lookup_skill.py`](../../tests/test_wikipedia_lookup_skill.py)
  — frontmatter·`allowed-tools`↔실재 도구·단일소스 불변식.
- eval: [`evals/`](evals/) — skill-creator 하니스(비결정적, pytest CI와 별개).
