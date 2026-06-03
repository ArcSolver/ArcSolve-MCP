# PubMed 서비스

NCBI E-utilities **읽기** 래퍼 — PubMed 생의학 문헌 검색·요약·초록(abstract). 전부 GET·읽기.
**인증은 선택**(키 없이도 동작), 키·식별값(`api_key`/`tool`/`email`)은 모두 **쿼리 파라미터**다.

E-utilities는 도구별로 응답 포맷이 다르다 — esearch/esummary는 **JSON**(`retmode=json`), efetch는
**XML만**(JSON 미지원). 따라서 검색·요약은 코어 `get_json`, 초록은 코어 `get_text` + 표준 라이브러리
`xml.etree.ElementTree`로 파싱한다(외부 의존 없음).

## 계약 출처 (공식 문서)
- E-utilities Quick Start(개요·base URL·esearch/esummary/efetch 흐름): https://www.ncbi.nlm.nih.gov/books/NBK25500/
- E-utilities In-Depth(전 파라미터·`retmode`·`sort`·`api_key`·JSON 출력 구조·efetch는 XML만): https://www.ncbi.nlm.nih.gov/books/NBK25499/
- General Introduction(레이트리밋 3/s·10/s·`api_key`·`tool`/`email` 등록 요구): https://www.ncbi.nlm.nih.gov/books/NBK25497/
- 라이브 응답 확인: `GET esearch.fcgi?retmode=json` · `esummary.fcgi?retmode=json` · `efetch.fcgi?rettype=abstract&retmode=xml`

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 상수·쿼리 제약·빌더·JSON/XML 파서).

## 인증 (선택 · 쿼리 파라미터)
`PubMedSettings`(`NCBI_*`)가 (선택) 자격증명을 로드한다. **헤더가 아니라 쿼리 파라미터**다.

| env | 쓰임 | 비고 |
|---|---|---|
| `NCBI_API_KEY` | `api_key=<키>` | 선택. 있으면 **10 req/s**, 없으면 **3 req/s** |
| `NCBI_TOOL` | `tool=<이름>` | 선택·권장(기본 `ArcSolve-MCP`). 공백 없는 문자열 |
| `NCBI_EMAIL` | `email=<이메일>` | 선택·권장. 공백 없는 유효 이메일 |

- 키가 없어도 호출은 성공한다(초당 3건 한도). 키는 [NCBI 계정 Settings 페이지](https://www.ncbi.nlm.nih.gov/account/settings/)에서 발급한다.
- base `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`, `db=pubmed` 고정.

## 레이트리밋 (공식 · NBK25497)
- **키 없음**: 한 IP에서 **초당 3건 초과** 시 에러(429).
- **키 있음**: `api_key` 포함 시 기본 **초당 10건**.
- 정책 위반으로 차단되면 `tool`/`email` 등록 후에야 복구 — 식별값 동봉을 권장.

## 엔드포인트 (전부 GET · `<base><util>`)
| 도구 | UTIL · 핵심 파라미터 | 포맷 |
|------|------|------|
| 검색 | `GET esearch.fcgi?db=pubmed&term=&retmax=&retstart=&sort=&retmode=json` | JSON → `get_json` |
| 요약 | `GET esummary.fcgi?db=pubmed&id=&retmode=json` | JSON → `get_json` |
| 초록 | `GET efetch.fcgi?db=pubmed&id=&rettype=abstract&retmode=xml` | **XML** → `get_text` + `xml.etree` |

> esearch JSON 봉투: `{"esearchresult":{count, retmax, retstart, idlist:[PMID...]}}`(count/retmax/retstart는 라이브에서 **문자열**로 와 int로 변환).
> esummary JSON 봉투: `{"result":{uids:[...], "<uid>":{title, authors:[{name,authtype}], source, fulljournalname, pubdate, volume, issue, pages, elocationid, articleids:[{idtype,value}]}}}`. DOI는 `articleids`에서 `idtype='doi'`로 추출.
> efetch XML: `<PubmedArticleSet>/<PubmedArticle>/<MedlineCitation>/<Article>` 하위의 `ArticleTitle`·`Abstract/AbstractText`(구조화 초록은 `Label` 속성)·`Journal/Title`.

## 셋업
1. (선택) [NCBI 계정 Settings](https://www.ncbi.nlm.nih.gov/account/settings/)에서 API 키 발급.
2. `.env`(선택): `NCBI_API_KEY=<키>`, `NCBI_EMAIL=<이메일>` — 초당 10건 + 식별.

> 키는 선택 쿼리 파라미터 — 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth pubmed` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `pubmed_search(query, retmax?=20, retstart?=0, sort?)` | Entrez 검색식으로 PMID 목록 조회. retmax 0..10000, sort=relevance/pub_date/Author/JournalName |
| `pubmed_get_summary(ids)` | PMID로 요약(제목·저자·저널·날짜·DOI). 콤마 구분, 1회 최대 200개 |
| `pubmed_fetch_abstract(ids)` | PMID로 초록 본문(구조화 초록은 라벨 표시). 콤마 구분, 1회 최대 200개 |

## 범위 / 제약 (공식)
- **읽기만.** esearch(검색)·esummary(요약)·efetch(초록)만(MVP).
- 제외: WebEnv/history 서버 체이닝(`usehistory`/`WebEnv`/`query_key`), pubmed 외 db, MeSH 상세, `elink`/`einfo`/`espell`.
- `retmax` 최대 10000(esearch). id는 1회 최대 200개(이상은 POST 권장 — 범위 밖).

## UNVERIFIED / provenance 노트
- esearch의 `count`/`retmax`/`retstart`는 In-Depth 문서엔 정수로 보이나 **라이브 JSON에선 문자열**이라 `_to_int`로 변환(`int|None`).
- 잘못된 검색식 등은 HTTP 200 + `{"esearchresult":{..., "ERROR":"..."}}`로 올 수 있어 `search_error`로 감지해 메시지만 노출한다.
- efetch XML 요소 경로(PubmedArticle/MedlineCitation/Article/...)는 공식 PubMed DTD를 라이브 응답으로 확인했다(구조화 초록 `AbstractText@Label` 포함). DTD 전체를 모델링하지 않고 제목·초록·저널만 부분 추출한다.

## 확장 포인트
- `usehistory=y` + `WebEnv`/`query_key`로 대용량 결과 서버 체이닝, `elink`(관련 문헌)·`einfo`(DB 메타)·`espell`(철자), pubmed 외 db(nuccore/protein 등), id 200개 초과 시 POST(`post_form`)는 동일 패턴으로 상수·도구 추가. POST는 코어에 이미 있음.
