# academic-discovery (학술 탐색)

여러 학술 출처(arXiv·Crossref·OpenAlex·PubMed·Semantic Scholar)를 가로질러 논문을 **탐색·교차검증**하는
스킬. 단일 DB 검색으로는 안 나오는 **커버리지 차이·식별자 dedup·인용 삼각검증**이 핵심 가치다.

> 이 스킬은 상류 API를 직접 치지 않고 **ArcSolve MCP 도구를 오케스트레이션**한다(AGENTS.md 규칙 2-2).
> 검증된 계약은 각 MCP 서비스의 `contract.py`에 단일 출처로 남는다(스킬은 계약을 재정의하지 않는다).

## 계약 출처 (공식 문서)
스킬이 기대는 MCP 서비스의 검증된 계약:
- arXiv API: https://info.arxiv.org/help/api/user-manual.html
- Crossref REST API: https://github.com/CrossRef/rest-api-doc/blob/master/README.md
- OpenAlex API: https://developers.openalex.org/how-to-use-the-api/api-overview
- PubMed (NCBI E-utilities): https://www.ncbi.nlm.nih.gov/books/NBK25500/
- Semantic Scholar Graph API: https://api.semanticscholar.org/api-docs/graph

## 필요 MCP 도구
ArcSolve MCP 서버에서 아래 도구가 노출돼 있어야 한다(`SKILL.md`의 `allowed-tools`와 일치):
- arXiv — `arxiv_search`, `arxiv_get`
- Crossref — `crossref_search_works`, `crossref_get_work`
- OpenAlex — `openalex_search_works`, `openalex_get_work`, `openalex_search_authors`, `openalex_get_author`
- PubMed — `pubmed_search`, `pubmed_get_summary`, `pubmed_fetch_abstract`
- Semantic Scholar — `s2_search_papers`, `s2_get_paper`, `s2_search_authors`, `s2_get_author`

> 셋업: `arcsolve serve arxiv crossref openalex pubmed semanticscholar`
> (또는 `ARCSOLVE_SERVICES=arxiv,crossref,openalex,pubmed,semanticscholar`). 전부 읽기 전용이지만
> OpenAlex/Crossref/S2/PubMed는 식별용 연락처·키를 권장한다 — 각 서비스 README 참고.

## 범위 / 경계
- **포함**: 멀티소스 검색·식별자(DOI/PMID/arXiv id) dedup·삼각검증·인용 확장·후보 랭킹·초록 조회.
- **제외(다른 스킬)**: 내러티브 리뷰 작성·주장 추출·품질 평가. 선택 핸드오프: `zotero_*`(저장), `wikipedia_*`/`wikidata_*`(배경 맥락).

## 품질 검증
- 정적 테스트: [`tests/test_academic_discovery_skill.py`](../../tests/test_academic_discovery_skill.py) — frontmatter·`allowed-tools`↔실재 도구.
- eval: [`evals/`](evals/) — skill-creator 하니스(비결정적, pytest CI와 별개).
