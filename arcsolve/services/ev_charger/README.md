# EV Charger(전기차 충전소) 서비스

한국환경공단 **전기자동차 충전소 정보**(EvCharger) **읽기** 래퍼 — 충전소 정보(위치·충전기
타입·운영기관·이용가능시간)와 충전기 실시간 상태(충전중/대기/통신이상·상태갱신일시). 전부
GET·**XML**. **서비스키 필수**(공공데이터포털 발급), 키는 **쿼리 파라미터 `serviceKey`**다
(OAuth 아님). airkorea·egen과 같은 기관(B552584/data.go.kr) 패턴.

## 계약 출처 (공식 문서)
- 한국환경공단_전기자동차 충전소 정보 OpenAPI(EvCharger) 상세: https://www.data.go.kr/data/15076352/openapi.do
- 전국전기차충전소표준데이터(필드 한글 라벨 교차참조): https://www.data.go.kr/data/15013115/standard.do

> base `http://apis.data.go.kr/B552584/EvCharger`. 공통 파라미터(serviceKey·pageNo·numOfRows·zcode·zscode), getChargerStatus 전용 `period`(분), 봉투 구조(`response.header`/`response.body.items.item`), getChargerStatus 응답 필드(busiId·statId·chgerId·stat·statUpdDt)와 `stat` 코드 의미(1통신이상·2충전대기·3충전중·4운영중지·5점검중·9상태미확인), 실시간 약 5분 갱신은 위 data.go.kr 상세 페이지에서 확인된다. **getChargerInfo 응답 필드 전체 표와 chgerType 코드표는 다운로드 활용가이드(.docx v1.23)에 있다**(상세 페이지 인라인 미렌더).
>
> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 경로·쿼리 빌더·XML 파서·응답 모델·코드표).

## 인증 (필수)
`EvChargerSettings`(`EV_CHARGER_*`)가 서비스키를 로드한다. **헤더가 아니라 쿼리 파라미터**다.

| env | 쿼리 파라미터 | 비고 |
|---|---|---|
| `EV_CHARGER_SERVICE_KEY` | `serviceKey=<키>` | 필수. data.go.kr에서 발급 |

> ⚠️ **Decoding 키(원문)를 넣으세요.** data.go.kr 서비스키는 **Encoding/Decoding 2종**으로 발급됩니다. httpx가 쿼리 파라미터를 자동 URL-인코딩하므로, 이미 인코딩된 키를 넣으면 **이중 인코딩**되어 `등록되지 않은 서비스키(30)` 오류가 납니다. 반드시 **Decoding 키(원문)**를 사용하세요.
> 키가 없으면 HTTP 호출 전에 안내 문자열을 반환합니다.

## 엔드포인트 (전부 GET · `<base><path>`)
| 도구 | METHOD · PATH |
|------|------|
| 충전기 실시간 상태 | `GET /getChargerStatus?zcode=&zscode=&period=&numOfRows=&pageNo=` |
| 충전소 정보 | `GET /getChargerInfo?zcode=&zscode=&numOfRows=&pageNo=` |

> 응답 봉투(XML): `<response><header><resultCode/><resultMsg/></header><body><items><item>...</item></items><totalCount/><pageNo/><numOfRows/></body></response>`. **`resultCode != "00"`이면 에러**(서비스키 오류 등) — HTTP 200이라도 봉투로 온다(게이트웨이 키 차단은 `<header>` 대신 `cmmMsgHeader/returnReasonCode`로 옴 → 30 등 매핑). 상태(`stat`)·타입(`chgerType`)·위경도(`lat`/`lng`)·플래그(`*Yn`)는 **전부 문자열**이며 결측은 빈 값 → 캐스팅하지 않는다.

## 충전기 상태 코드(stat)
| 코드 | 의미 |
|---|---|
| 1 | 통신이상 |
| 2 | 충전대기 |
| 3 | 충전중 |
| 4 | 운영중지 |
| 5 | 점검중 |
| 9 | 상태미확인 |

> 출처: data.go.kr 상세 페이지 getChargerStatus 응답 `stat` 설명.

## 셋업
1. [공공데이터포털 전기차 충전소 정보 OpenAPI](https://www.data.go.kr/data/15076352/openapi.do)에서 활용 신청 → **Decoding 서비스키** 확인.
2. `.env`:
   - `EV_CHARGER_SERVICE_KEY=<Decoding 키>`

> 서비스키는 사전발급 쿼리 파라미터 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth ev_charger` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `evcharger_status(zcode?, zscode?, period?, numOfRows?, pageNo?)` ⭐ | 충전기 실시간 상태(충전중/대기/통신이상/운영중지/점검중/상태미확인 + 상태갱신일시). ⚠️ 약 5분 지연 캐시 |
| `evcharger_info(zcode?, zscode?, numOfRows?, pageNo?)` | 충전소 정보(충전기 타입 코드·주소·위경도·운영기관·이용가능시간) |

> `zcode`(시도)/`zscode`(시군구)는 **행정구역 지역코드**(zcode=행정구역코드 앞 2자리, 예: 11=서울). 둘 다 생략 시 전국. `period`(분)는 상태갱신 조회범위(기본 5·최소 1·최대 10).

## 범위 / 제약 (공식)
- **읽기만.** 충전기 실시간 상태 + 충전소 정보(MVP).
- 제외: 전국전기차충전소표준데이터(정적 표준데이터·별도 데이터셋), 급속충전 별도 서비스, 충전량/통계.
- 페이지네이션: `numOfRows`(기본 100, **최소 10·최대 9999** — 빌더가 클램프)·`pageNo`(기본 1) — 건수/페이지는 응답 **본문**(`body.totalCount/pageNo`)에 실린다.
- ⚠️ **실시간 상태 지연**: `getChargerStatus`는 "실시간"이지만 상류가 **약 5분 주기**로 갱신한다 → 결과는 항상 수 분 지연된 캐시 스냅샷이다(`statUpdDt`로 실제 갱신시각 확인). 도구 출력 헤더에 "약 5분 지연(캐시 스냅샷)"을 명시한다.

## UNVERIFIED / provenance 노트
- **응답 포맷**: data.go.kr 상세 페이지·활용가이드(v1.23)가 **XML** 기준이며 `_type=json` 지원 여부를 공식 확인할 수 없어, 안전하게 XML로 받아(`get_text`) 표준 라이브러리(`xml.etree.ElementTree`)로 파싱한다(egen/arxiv 패턴).
- **getChargerInfo 응답 필드 / chgerType 코드표**: 상세 페이지는 `getChargerStatus`만 인라인 렌더하고(busiId·statId·chgerId·stat·statUpdDt + stat 코드 의미 확인됨), `getChargerInfo` 전체 응답 필드 표와 `chgerType` 코드 매핑은 **다운로드 활용가이드(.docx v1.23)**에만 있다. 정보 필드는 [전국전기차충전소표준데이터](https://www.data.go.kr/data/15013115/standard.do)의 한글 라벨로 교차확인해 모델링했고, 응답 모델은 `extra="ignore"`로 느슨히 받아 가이드 버전차/미확인 필드를 흡수한다(`contract.py`의 `TODO(provenance)` 참고). 미상 `chgerType` 코드는 매핑 없이 원본 코드를 그대로 표시한다.
- **지역코드(zcode/zscode)**: 상세 페이지는 zcode를 "시도 코드(행정구역코드 앞 2자리)"로만 안내하고 전체 코드↔지역명 매핑 표는 제공하지 않는다(활용가이드 의존). 따라서 도구는 코드 문자열을 그대로 받아 전달한다(예: 11=서울특별시 — 통상 행정표준코드).

## 확장 포인트
- 표준데이터(`15013115`, 정적 전수)·충전량/통계 데이터셋은 별도 서비스로 동일 패턴 추가. getChargerInfo의 확장 필드(가이드 v1.23 코드표 전체)는 `contract.py`의 `Charger` 모델에 출처와 함께 추가.
