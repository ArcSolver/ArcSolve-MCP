# Airport(인천국제공항 운항현황) 서비스

인천국제공항공사(IIAC) **여객편 운항현황** **읽기** 래퍼 — 실시간 도착·출발 항공편 현황(편명·
항공사·출발지/목적지·예정/변경 시각·터미널·수하물수취대/체크인카운터·탑승구·운항상태). 전부
GET·JSON. **서비스키 필수**(공공데이터포털 발급), 키는 **쿼리 파라미터 `serviceKey`**다(OAuth
아님). 기관코드 **B551177**, 서비스 `StatusOfPassengerFlightsDeOdp`.

## 계약 출처 (공식 문서)
- 인천국제공항공사_항공기 운항 현황 상세 조회(여객편 운항현황 상세조회): https://www.data.go.kr/data/15140153/openapi.do
  - `StatusOfPassengerFlightsDeOdp/getPassengerArrivalsDeOdp`(여객편 도착현황 상세조회)
  - `StatusOfPassengerFlightsDeOdp/getPassengerDeparturesDeOdp`(여객편 출발현황 상세조회)

> base `http://apis.data.go.kr/B551177/StatusOfPassengerFlightsDeOdp/<operation>`. 공통 파라미터(serviceKey·`type=json`·searchday·from_time·to_time·lang·numOfRows·pageNo), 봉투 구조(`response.header`/`response.body.items[]`), 각 응답 항목 필드는 위 페이지 + 다수 외부 구현 실호출로 확인된다.
>
> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(서비스/오퍼레이션 경로·쿼리 빌더·응답 모델·items 정규화).

## 인증 (필수)
`AirportSettings`(`AIRPORT_*`)가 서비스키를 로드한다. **헤더가 아니라 쿼리 파라미터**다.

| env | 쿼리 파라미터 | 비고 |
|---|---|---|
| `AIRPORT_SERVICE_KEY` | `serviceKey=<키>` | 필수. data.go.kr(15140153)에서 발급 |

> ⚠️ **Decoding 키(원문)를 넣으세요.** data.go.kr 서비스키는 **Encoding/Decoding 2종**으로 발급됩니다. httpx가 쿼리 파라미터를 자동 URL-인코딩하므로, 이미 인코딩된 키를 넣으면 **이중 인코딩**되어 `등록되지 않은 서비스키(30)` 오류가 납니다. 반드시 **Decoding 키(원문)**를 사용하세요.
> ⚠️ **개발계정은 일일 트래픽 500건 제한**입니다(운영계정은 활용사례 등록 후 상향 가능). 한도 초과 시 `서비스 요청 제한 초과(22)`가 옵니다.
> 키가 없으면 HTTP 호출 전에 안내 문자열을 반환합니다(`type=json`은 항상 자동으로 붙습니다 — 미지정 시 상류가 XML을 줍니다. ⚠️ 인천공항은 `_type`이 아니라 **`type`**입니다).

## 엔드포인트 (전부 GET · `http://apis.data.go.kr/B551177/StatusOfPassengerFlightsDeOdp<op>`)
| 도구 | operation |
|------|------|
| 도착현황 ⭐ | `getPassengerArrivalsDeOdp?serviceKey=&type=json&searchday=&from_time=&to_time=&lang=&…` |
| 출발현황 ⭐ | `getPassengerDeparturesDeOdp?serviceKey=&type=json&searchday=&from_time=&to_time=&lang=&…` |

> 응답 봉투: `{response:{header:{resultCode,resultMsg}, body:{items:[...], totalCount, pageNo, numOfRows}}}`. **`resultCode != "00"`이면 에러**(서비스키 오류·무데이터 등) — HTTP 200이라도 봉투로 온다. 게이트웨이 키 차단은 `cmmMsgHeader.returnReasonCode`로 올 수 있어 함께 검사한다. ⚠️ items quirk: 인천공항은 `body.items`가 **곧장 항목 리스트**(타 data.go.kr 서비스의 `items.item` 중첩과 다름), 1건이면 **단일 객체**, 0건이면 빈 리스트/빈 문자열 — `contract.normalize_items`가 네 형태를 모두 흡수한다. 편명·시각·터미널·게이트 등은 **문자열**로 받는다(캐스팅하지 않음).

## 셋업
1. [공공데이터포털](https://www.data.go.kr/data/15140153/openapi.do)에서 인천국제공항공사 '항공기 운항 현황 상세 조회'를 활용 신청 → **Decoding 서비스키** 확인.
2. `.env`:
   - `AIRPORT_SERVICE_KEY=<Decoding 키>`

> 서비스키는 사전발급 쿼리 파라미터 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth airport` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `airport_arrivals(search_day?, from_time?, to_time?, airport_code?, flight_id?, lang?, numOfRows?, pageNo?)` ⭐ | 여객편 도착현황(편명·항공사·출발지·예정/변경시각·터미널·수하물수취대·출구·운항상태) |
| `airport_departures(search_day?, from_time?, to_time?, airport_code?, flight_id?, lang?, numOfRows?, pageNo?)` ⭐ | 여객편 출발현황(편명·항공사·목적지·예정/변경시각·터미널·체크인카운터·탑승구·운항상태) |

- `search_day`=`YYYYMMDD`(미지정 시 당일). 조회 가능 범위는 **D-3~D+6**.
- `from_time`/`to_time`=`HHMM`(기본 `0000`~`2400` — 하루 전체).
- `airport_code`(IATA, 도착은 출발지·출발은 목적지)·`flight_id`(편명)는 선택 필터.
- `lang`=`K`(국문, 기본)/`E`(영문).

## 범위 / 제약 (공식)
- **읽기만.** 인천공항 **여객편** 실시간 출발·도착 운항현황(MVP, 2개 도구).
- 제외(스코프 밖): 화물편 운항현황, 주차·혼잡도(입국장/출국장)·면세·기상·교통 등 인천공항 부가 서비스, KAC(김포/제주 등) 타 공항.
- 페이지네이션 `numOfRows`(기본 100)·`pageNo`(기본 1).
- 레이트리밋: **개발계정 일 500건** 트래픽 한도(운영계정은 활용사례 등록 후 상향).

## provenance 노트 (독립 검증 결과)
- **기관코드 B551177 · 서비스 `StatusOfPassengerFlightsDeOdp` · 오퍼레이션 `getPassengerArrivalsDeOdp`/`getPassengerDeparturesDeOdp`** — data.go.kr 15140153 + 다수 외부 구현의 실호출 URL로 교차확인(`http://apis.data.go.kr/B551177/StatusOfPassengerFlightsDeOdp/getPassengerArrivalsDeOdp`).
- **`type=json`** — data.go.kr 공통 키는 보통 `_type`이지만, 인천공항 운항현황은 파라미터명이 **`type`**다(외부 구현 실호출 `params={'type':'json', …}`로 확인).
- **요청 파라미터** `searchday`/`from_time`/`to_time`/`lang`/`numOfRows`/`pageNo` — 외부 구현 실호출 params로 확인.
- **응답 필드** `airline`/`flightId`/`airport`/`airportCode`/`scheduleDateTime`/`estimatedDateTime`/`terminalid`/`gatenumber`/`remark`/`fid`/`codeshare`/`masterflightid`, 도착 `carousel`/`exitnumber`, 출발 `chkinrange` — 다수 외부 구현의 실응답 추출 로직(`item.get(...)`)으로 교차확인(aivle ICN-AI-chatbot Python, eyjs/convention C#, airscreen iOS Swift·Android Kotlin, TaeHyun77 Java).
- **`terminalid`는 코드** — 상류는 표시명(T1/T2)이 아니라 **코드 `P01`(제1터미널)/`P02`(탑승동)/`P03`(제2터미널)**를 준다(airscreen iOS·convention C# 교차확인). `tools._fmt_terminal`(`contract.TERMINAL_NAMES`)이 표시명으로 환산하고, 매핑에 없는 코드는 원문 그대로 보여준다.
- **`codeshare`/`masterflightid` 확정** — 단독/공동운항 구분(`codeshare`=Master/Slave 등)과 공동운항 시 주 편명(`masterflightid`)은 다중 외부 구현(eyjs/convention C#: `Codeshare=="Slave" ? Masterflightid`; airscreen iOS Swift 모델)으로 실재 확인되어 모델에 포함하고 출력에 부기한다(직전 `TODO(provenance)`에서 승격).
- **items 형태** — 인천공항은 `body.items`가 **곧장 리스트**(외부 구현 `body.get('items', [])` + `if isinstance(items, dict): items=[items]`). `normalize_items`가 리스트/단일 객체/`item` 중첩/빈 문자열을 모두 흡수.
- **남은 미확정** — `city`/`typeOfFlight`/`fstandposition` 등 일부 변형은 15140153 상세 페이지가 JS 렌더라 인라인 스키마를 정적으로 확인하지 못했고 단일 구현에서만 보여 모델에 두지 않는다. 다중 외부 구현으로 확인된 필드만 모델에 두고, `extra="ignore"`로 나머지 변형을 흡수한다(`contract.py`의 `TODO(provenance)`). 라이브 키가 없어 라이브 호출 검증은 보류.
- 모든 코드/시각/터미널/게이트 값은 **문자열**(`str | None`)로 받는다(상류가 수치도 문자열·숫자로 섞어 줄 수 있어 캐스팅하지 않음).

## 확장 포인트
- 화물편 운항현황(`StatusOfCargoFlights…` 계열), 다국어 운항현황, 주차/혼잡도/기상 등 인천공항 부가 OpenAPI는 동일 패턴으로 서비스/오퍼레이션 경로 상수·도구 추가. KAC(김포/제주 등)는 별도 기관코드·별도 서비스로 분리.
