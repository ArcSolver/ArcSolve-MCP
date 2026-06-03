# 소스별 커버리지 & 질의 팁

각 학술 소스는 커버리지가 다르다. 탐색 시 도메인에 맞는 소스를 고르고, 결과를 식별자로 합친다.

## arXiv (`arxiv_*`)
- 커버리지: 물리·수학·CS 중심 **프리프린트**(피어리뷰 전). full-text 없음(메타데이터·초록).
- 질의: `arxiv_search`의 `query`는 `search_query` 문자열 — 필드 prefix(`ti:`/`au:`/`abs:`/`cat:`/`all:`) +
  불리언 `AND`/`OR`/`ANDNOT`. 예: `cat:cs.CL AND ti:retrieval`.
- 식별자: arXiv id(버전 접미사 `v1` 등). DOI가 있으면 출판본과 매칭.
- etiquette: 연속 호출 시 ~3초 지연 권장.

## PubMed (`pubmed_*`)
- 커버리지: **생의학·생명과학**. PMID 키.
- 흐름: `pubmed_search`(→ PMID 목록) → `pubmed_get_summary`(제목·저자·저널·DOI) → `pubmed_fetch_abstract`.
- 질의: MeSH 용어·필드 태그가 정밀도를 높인다.

## Crossref (`crossref_*`)
- 커버리지: **DOI 레지스트리** — 출판사 메타데이터의 권위 출처(저널 논문 광범위).
- 흐름: `crossref_search_works`(free text) → `crossref_get_work`(DOI 단건).
- 쓰임: DOI 확정·서지정보 reconcile의 기준점.

## OpenAlex (`openalex_*`)
- 커버리지: **오픈 학술 그래프** — works/authors, 인용, 개념, OA 상태.
- 흐름: `openalex_search_works` / `openalex_get_work`; 저자는 `openalex_search_authors` / `openalex_get_author`.
- 쓰임: 인용 기반 확장·오픈액세스 여부.

## Semantic Scholar (`s2_*`)
- 커버리지: **AI 보강 그래프** — influential citations, TLDR 요약.
- 흐름: `s2_search_papers` / `s2_get_paper`; 저자는 `s2_search_authors` / `s2_get_author`.
- 쓰임: 영향력 있는 인용·간결 요약으로 후보 추림.

## dedup / reconcile 규칙
1. **DOI 우선** 매칭.
2. DOI 없으면 정규화 제목 + 연도(또는 arXiv id) fallback.
3. 여러 소스에 잡히면 신뢰↑(삼각검증). 프리프린트 vs 출판본 구분(arXiv + Crossref DOI → 출판).
