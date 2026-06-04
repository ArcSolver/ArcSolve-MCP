# feeds 서비스

RSS/Atom/RDF 피드 **읽기** 래퍼 — 임의 피드 URL을 받아 채널 메타와 최근 항목을 요약한다.
전부 GET·**무인증**(키 없음). 피드는 JSON이 아니라 XML이므로 코어 `get_text`(raw str)로 받고
**표준 라이브러리 `xml.etree.ElementTree`**로 파싱한다(feedparser/lxml 등 외부 의존 없음).

> **왜 RSS인가:** 임의 웹사이트 콘텐츠 수집을 **스크래핑 없이** 하는 정공법. 표준 포맷이라
> 출처가 명확하고(공식 계약), 대부분 뉴스·블로그·릴리스노트·팟캐스트·YouTube 채널이 피드를
> 제공한다. 코어 `get_text` 인프라(arXiv·PubMed에서 검증)를 그대로 재사용한다.

## 계약 출처 (공식 스펙)
- RSS 2.0: https://www.rssboard.org/rss-specification
- Atom 1.0 (RFC 4287): https://datatracker.ietf.org/doc/html/rfc4287
- RSS 1.0 (RDF Site Summary): https://web.resource.org/rss/1.0/spec
- Dublin Core elements (`dc:creator`·`dc:date`): https://www.dublincore.org/specifications/dublin-core/dcmi-terms/

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(포맷 감지·로컬명 기반 탐색·통일 모델 정규화).

## 인증 (없음)
무인증이다. 키·토큰·env 설정이 필요 없다(식별용 User-Agent만 보낸다).

> 무인증이므로 `arcsolve-mcp auth feeds` 단계는 없다. 비공개·인증 필요 피드는 401/403으로 매핑한다.

## 엔드포인트 (임의 피드 URL · 전부 GET)
| 종류 | 입력 |
|------|------|
| 피드 조회 | 임의 `http(s)` 피드 URL(RSS 2.0 / Atom 1.0 / RSS 1.0·RDF) |

포맷은 **루트 엘리먼트로 자동 감지**한다 — `<rss>`=RSS 2.0, `<feed>`=Atom 1.0, `<rdf:RDF>`=RSS 1.0/RDF.

### 응답 정규화 (포맷 무관 통일 모델)
요소 탐색은 **로컬명 기반**(네임스페이스 무관)이라 변형과 확장(`dc:`/`content:`)을 함께 흡수한다.

| 통일 필드 | RSS 2.0 | Atom 1.0 | RSS 1.0/RDF |
|------|------|------|------|
| 항목 제목 | `item/title` | `entry/title` | `item/title` |
| 항목 링크 | `item/link`(텍스트) | `entry/link[@rel=alternate]/@href` | `item/link` |
| 게시일 | `item/pubDate`(RFC822) | `entry/published`\|`updated`(ISO8601) | `item/dc:date` |
| 요약 | `item/description`\|`content:encoded` | `entry/summary`\|`content` | `item/description` |
| 작성자 | `item/author`\|`dc:creator` | `entry/author/name` | `item/dc:creator` |
| 식별자 | `item/guid` | `entry/id` | `item/@rdf:about` |

> 날짜는 **원본 문자열 그대로** 보존한다(RFC822↔ISO8601 변환은 파싱 실패 위험 → 비목표, 표시용으로 충분).
> 요약은 HTML 스니펫이 흔해 태그 제거·엔티티 복원·길이 제한(500자)으로 평문화한다.

## 셋업
1. 키 발급 단계 없음(무인증). `.env` 변경 불필요.

## 도구
| 도구 | 설명 |
|------|------|
| `feeds_fetch(url, limit?)` | 피드 URL → 채널 메타(제목·링크·설명) + 최근 항목(제목·링크·게시일·요약). `limit` 기본 20·1..100 |

## 범위 / 제약
- **읽기만.** 피드 구독 관리·증분 추적·전문 본문 저장은 하지 않는다(항목 link로 위임).
- 지원 포맷 = RSS 2.0 · Atom 1.0 · RSS 1.0(RDF). 그 외 루트는 명확한 에러로 거부한다.
- **피드 자동 발견(HTML `<link rel=alternate>` 탐지)은 비목표** — 피드 URL을 직접 받는다.
- `limit` 1..100. 날짜는 미변환(원본 보존). 요약 500자·채널 설명 300자 제한.

## provenance 노트
- 포맷 감지는 **루트 로컬명**(`rss`/`feed`/`RDF`)으로 한다 — 네임스페이스 선언 차이에 견고.
- RDF는 `<item>`이 `<channel>` 밖, `<rdf:RDF>` 직계 형제로 오는 구조라 별도 파서로 처리한다.
- Atom `<link>`는 속성(`href`/`rel`)이라 `rel=alternate`(또는 rel 미지정)를 고른다(self/enclosure 제외).

## 확장 포인트
- HTML 피드 자동 발견, 조건부 GET(ETag/Last-Modified) 증분, JSON Feed(application/feed+json),
  enclosure(팟캐스트 오디오) 노출은 동일 패턴으로 확장 가능.
