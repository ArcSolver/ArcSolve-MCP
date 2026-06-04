# Seoul Transit(서울 실시간 교통) 서비스

서울시 **실시간 교통** 읽기 래퍼 — **지하철 실시간 도착정보**(TOPIS)와 **따릉이(공공자전거)
실시간 대여소 현황**. 전부 GET·JSON. **인증키 필수**(서울 열린데이터광장 발급), 키는
**URL path의 첫 세그먼트**다(OAuth·헤더·쿼리 아님).

## 계약 출처 (공식 문서)
- 지하철 실시간 도착정보(OA-12764): https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do
  - 공공데이터포털 미러: https://www.data.go.kr/data/15058052/openapi.do
- 따릉이 실시간 대여정보(OA-15493): https://data.seoul.go.kr/dataList/OA-15493/A/1/datasetView.do
- 공통 결과코드(RESULT.CODE) 메세지표: https://data.gangnam.go.kr/openinf/openapiview.jsp?infId=OA-18724

> 지하철: 호스트 `http://swopenAPI.seoul.go.kr/api/subway`, 경로 `{KEY}/{TYPE}/realtimeStationArrival/{START}/{END}/{역명}`, 봉투 `{errorMessage:{status,code,message,total}, realtimeArrivalList:[...]}`. 따릉이: 호스트 `http://openapi.seoul.go.kr:8088`, 경로 `{KEY}/{TYPE}/bikeList/{START}/{END}/`, 봉투 `{rentBikeStatus:{list_total_count, RESULT:{CODE,MESSAGE}, row:[...]}}`. `{TYPE}`에 `json`을 박아 `get_json`으로 받는다.
>
> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(호스트·경로 빌더·응답 모델).

## 인증 (필수 · ⚠️ 인증키 2종 분리)
`SeoulTransitSettings`(`SEOUL_*`)가 인증키 **2개**를 로드한다. **헤더가 아니라 URL path 세그먼트**다.

| env | 쓰는 도구 | 비고 |
|---|---|---|
| `SEOUL_SUBWAY_API_KEY` | `seoul_subway_arrivals` | 필수. **별도의 '실시간 지하철 인증키'**(일반 인증키와 다름) |
| `SEOUL_OPENDATA_API_KEY` | `seoul_bike_status` | 필수. 서울 열린데이터광장 '일반 인증키' |

> ⚠️ **지하철 실시간 도착은 별도 인증키가 필요합니다.** 서울 열린데이터광장은 지하철 실시간 데이터에 대해 일반 인증키와 **다른 '실시간 지하철 인증키'**를 발급합니다(전용 호스트 `swopenAPI.seoul.go.kr`). 따릉이 등 일반 데이터셋은 '일반 인증키'(`openapi.seoul.go.kr:8088`)를 씁니다. 각 도구는 해당 키가 없으면 HTTP 호출 전에 안내 문자열을 반환합니다.

## 엔드포인트 (전부 GET)
| 도구 | URL |
|------|------|
| 지하철 실시간 도착 | `GET swopenAPI.seoul.go.kr/api/subway/{KEY}/json/realtimeStationArrival/{START}/{END}/{역명}` |
| 따릉이 실시간 대여 | `GET openapi.seoul.go.kr:8088/{KEY}/json/bikeList/{START}/{END}/` |

> 인증키·역명·요청위치는 모두 **path 세그먼트**(쿼리 아님). 상류는 키/요청/데이터없음 오류를 **HTTP 200 + 봉투**(지하철은 `errorMessage.code`, 따릉이는 `RESULT.CODE`)로 주는 일이 많다 — `INFO-000`이 정상, 그 외(`INFO-100` 인증키·`INFO-200` 데이터없음·`ERROR-336` 1000건초과·`ERROR-5xx` 서버)는 안내 문자열로 매핑된다. 모든 항목 값은 **문자열**이다.

## 셋업
1. [서울 열린데이터광장](https://data.seoul.go.kr/)에서 인증키 신청 — **일반 인증키**와 **실시간 지하철 인증키**는 별도다.
2. `.env`:
   - `SEOUL_SUBWAY_API_KEY=<실시간 지하철 인증키>`
   - `SEOUL_OPENDATA_API_KEY=<일반 인증키>`

> 인증키는 사전발급 path 세그먼트 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve auth seoul_transit` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `seoul_subway_arrivals(station_name)` | 한 역의 실시간 도착(전 호선·상하행). 도착메시지·현재위치·열차종류·종착역. `recptnDt`(생성시각, **과거**)는 '현재로부터 N초 전 생성'으로 보정 표시 |
| `seoul_bike_status(start?=1, end?=1000, station_name?)` | 따릉이 대여소 현황. 거치 자전거수(`parkingBikeTotCnt`=대여가능)·거치율(`shared`)·위경도. **1회 최대 1000건**(end−start+1≤1000) 페이지네이션. `station_name`은 받아온 페이지 내 부분일치 필터 |

## 범위 / 제약 (공식)
- **읽기만.** 지하철 한 역의 실시간 도착 + 따릉이 실시간 대여소 현황(MVP).
- 제외: 버스(전국 TAGO는 별도 서비스), 지하철 실시간 **열차 위치**(OA-12601), 지하철 도착정보 **일괄**(OA-15799), 따릉이 대여소 **정적 정보**(OA-13252).
- 따릉이는 **1회 최대 1000건**(`ERROR-336`). 전체(대여소 약 3천 개)를 받으려면 `start`/`end`로 여러 번 호출.
- 지하철 실시간은 따릉이의 1회 한도와 별개로 **인증키당 하루 1,000건 요청 쿼터**가 있다(서울 열린데이터광장 실시간 지하철 키 정책). 호출 빈도 관리 필요.
- `recptnDt`는 수집·가공 지연으로 **과거 시각**이다 — 실제 도착까지 시간은 이 시각 기준이라 도구가 '생성 후 N초'를 함께 안내한다.

## UNVERIFIED / provenance 노트
- 지하철 봉투의 `errorMessage`는 **정상 응답에도 항상 존재**한다(`code=INFO-000`). 역명 오타·인증키 오류는 `code`가 `INFO-xxx`/`ERROR-xxx`로 바뀌고 `realtimeArrivalList`가 비거나 없을 수 있다 — 모델은 둘 다 `extra="ignore"`/Optional로 느슨히 받는다.
- 모든 항목 값은 **문자열**(`str | None`)로 받는다(상류가 수치·시각·위경도도 문자열로 줌 — 캐스팅하지 않는다).
- 따릉이 인증키/요청 오류는 서비스 래퍼(`rentBikeStatus`) 없이 **최상위 `RESULT`**로 올 수 있어, 도구가 양쪽(`body.RESULT`·`rentBikeStatus.RESULT`)을 모두 검사한다.
- `arvlCd`(도착 코드: 0 진입·1 도착·2 출발·3 전역출발·4 전역진입·5 전역도착·99 운행중)와 `arvlMsg2`는 모델에 있으나, 표시는 사람이 읽는 `arvlMsg2`(예: "전역 출발")를 우선한다.

## 확장 포인트
- 지하철 실시간 **열차 위치**(OA-12601 `realtimePosition`), 지하철 도착 **일괄**(OA-15799), 따릉이 **이용현황** 통계(OA-14994)는 동일 패턴으로 경로 상수·도구 추가.
