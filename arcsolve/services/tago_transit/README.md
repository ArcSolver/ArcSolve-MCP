# TAGO Transit(국토부 전국 대중교통) 서비스

국토교통부 **TAGO(국가대중교통정보센터)** 전국 대중교통 **읽기** 래퍼 — 시내버스 실시간 도착·
정류소 검색·노선 경유정류소 + 고속/시외버스 운행 + 도시간 열차. 전부 GET·JSON. TAGO는 **단일
네임스페이스 `1613000`**에 전국 대중교통이 통합돼 있어 **하나의 data.go.kr 서비스키로 6개
서비스를 모두 커버**한다. **서비스키 필수**(공공데이터포털 발급), 키는 **쿼리 파라미터
`serviceKey`**다(OAuth 아님).

## 계약 출처 (공식 문서)
- 버스도착정보 ArvlInfoInqireService: https://www.data.go.kr/data/15098530/openapi.do
  - `getSttnAcctoArvlPrearngeInfoList`(정류소별 도착예정), `getCtyCodeList`(도시코드 목록)
- 버스정류소정보 BusSttnInfoInqireService: https://www.data.go.kr/data/15098534/openapi.do
  - `getSttnNoList`(정류소명 검색)
- 버스노선정보 BusRouteInfoInqireService: https://www.data.go.kr/data/15098529/openapi.do
  - `getRouteAcctoThrghSttnList`(노선별 경유정류소)
- 고속버스정보 ExpBusInfoService: https://www.data.go.kr/data/15098522/openapi.do
  - `getStrtpntAlocFndExpbusInfo`(출/도착지기반 고속버스), `getExpBusTrminlList`(터미널 목록)
- 시외버스정보 SuburbsBusInfoService: https://www.data.go.kr/data/15098541/openapi.do
  - `getStrtpntAlocFndSuberbsBusInfo`(출/도착지기반 시외버스), `getSuberbsBusTrminlList`(터미널 목록)
- 열차정보 TrainInfoService: https://www.data.go.kr/data/15098552/openapi.do
  - `getCtyAcctoTrainList`(도시간 열차)
- (참고) TAGO 구 OpenAPI 13종 호출중지·대체 공지(이 6종이 현행 대체본): https://www.data.go.kr/bbs/ntc/selectNotice.do?originId=NOTICE_0000000002723

> base `http://apis.data.go.kr/1613000/<Service>/<operation>`. 공통 파라미터(serviceKey·`_type`·numOfRows·pageNo), 봉투 구조(`response.header`/`response.body.items.item[]`), 각 응답 항목 필드는 위 페이지에서 확인된다.
>
> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(서비스/오퍼레이션 경로·쿼리 빌더·응답 모델·items 정규화).

## 인증 (필수)
`TagoSettings`(`TAGO_*`)가 서비스키를 로드한다. **헤더가 아니라 쿼리 파라미터**다. 단일 키로 6개 서비스 전부 커버.

| env | 쿼리 파라미터 | 비고 |
|---|---|---|
| `TAGO_SERVICE_KEY` | `serviceKey=<키>` | 필수. data.go.kr에서 발급 |

> ⚠️ **Decoding 키(원문)를 넣으세요.** data.go.kr 서비스키는 **Encoding/Decoding 2종**으로 발급됩니다. httpx가 쿼리 파라미터를 자동 URL-인코딩하므로, 이미 인코딩된 키를 넣으면 **이중 인코딩**되어 `등록되지 않은 서비스키(30)` 오류가 납니다. 반드시 **Decoding 키(원문)**를 사용하세요.
> 키가 없으면 HTTP 호출 전에 안내 문자열을 반환합니다(`_type=json`은 항상 자동으로 붙습니다 — 미지정 시 상류가 XML을 줍니다).

## 엔드포인트 (전부 GET · `http://apis.data.go.kr/1613000<service><op>`)
| 도구 | service / operation |
|------|------|
| 도시코드 목록 | `ArvlInfoInqireService/getCtyCodeList?serviceKey=&_type=json` |
| 정류소 검색 | `BusSttnInfoInqireService/getSttnNoList?cityCode=&nodeNm=&…` |
| 정류소 도착예정 ⭐ | `ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList?cityCode=&nodeId=&…` |
| 노선 경유정류소 | `BusRouteInfoInqireService/getRouteAcctoThrghSttnList?cityCode=&routeId=&…` |
| 고속버스 | `ExpBusInfoService/getStrtpntAlocFndExpbusInfo?depTerminalId=&arrTerminalId=&depPlandTime=&…` |
| 시외버스 | `SuburbsBusInfoService/getStrtpntAlocFndSuberbsBusInfo?depTerminalId=&arrTerminalId=&depPlandTime=&…` |
| 열차 | `TrainInfoService/getCtyAcctoTrainList?depPlaceId=&arrPlaceId=&depPlandTime=&…` |

> 응답 봉투: `{response:{header:{resultCode,resultMsg}, body:{items:{item:[...]}, totalCount, pageNo, numOfRows}}}`. **`resultCode != "00"`이면 에러**(서비스키 오류·무데이터 등) — HTTP 200이라도 봉투로 온다. 게이트웨이 키 차단은 `cmmMsgHeader.returnReasonCode`로 올 수 있어 함께 검사한다. ⚠️ data.go.kr JSON quirk: `body.items`는 한 단계 더(`{"item": …}`) 싸이고, 1건이면 `item`이 **단일 객체**, 0건이면 `items`가 **빈 문자열 `""`** — `contract.normalize_items`가 셋을 흡수한다. 코드·요금·시각은 **문자열**로 받는다(캐스팅하지 않음).

## 셋업
1. [공공데이터포털](https://www.data.go.kr/)에서 위 6개 TAGO OpenAPI를 활용 신청 → **Decoding 서비스키** 확인. (네임스페이스가 같아 한 번 신청한 키가 6개 모두에 통하나, data.go.kr은 서비스별 활용신청을 요구하므로 6개 모두 신청해 두세요.)
2. `.env`:
   - `TAGO_SERVICE_KEY=<Decoding 키>`

> 서비스키는 사전발급 쿼리 파라미터 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth tago_transit` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `tago_city_codes()` | 전국 도시코드 목록(도시명=코드). 버스 도구 입력 `city_code` 보조 |
| `tago_search_bus_stops(city_code, node_name, numOfRows?, pageNo?)` | 정류소명 검색 → **nodeId**·정류소번호·위경도. `tago_bus_arrivals` 입력 보조 |
| `tago_bus_arrivals(city_code, node_id, numOfRows?, pageNo?)` ⭐ | 정류소별 버스 실시간 도착예정(노선번호·남은 정류장 수·도착예정 초→분 환산·차량유형) |
| `tago_bus_route(city_code, route_id, numOfRows?, pageNo?)` | 노선 경유정류소(경유 순번·상하행·nodeId) |
| `tago_express_bus(dep_terminal_id, arr_terminal_id, dep_date, numOfRows?, pageNo?)` | 고속버스 운행(등급·요금·출/도착 시각). `dep_date`=`YYYYMMDD` |
| `tago_intercity_bus(dep_terminal_id, arr_terminal_id, dep_date, numOfRows?, pageNo?)` | 시외버스 운행(등급·요금·출/도착 시각) |
| `tago_train(dep_station_id, arr_station_id, dep_date, numOfRows?, pageNo?)` | 도시간 열차(KTX/일반 — 등급·열차번호·요금·출/도착 시각) |

## 코드 의존 — 입력 ID 확보 방법 (중요)
TAGO 도구들은 위치를 **코드/ID**로 받는다. 자기완결성을 위해 일부는 보조 도구로 해결한다:

| 입력 | 확보 방법 |
|---|---|
| `city_code`(도시코드) | **`tago_city_codes()`** 도구로 조회(자기완결) |
| `node_id`(정류소ID) | **`tago_search_bus_stops(city_code, 정류소명)`** 도구로 검색(자기완결) |
| `route_id`(노선ID) | `tago_bus_arrivals`/`tago_search_bus_stops` 응답의 `routeid`, 또는 `BusRouteInfoInqireService/getRouteNoList`(노선번호 목록조회 — 본 MVP 외) |
| `dep/arr_terminal_id`(터미널ID) | `ExpBusInfoService/getExpBusTrminlList`·`SuburbsBusInfoService/getSuberbsBusTrminlList`(터미널 목록조회 — 본 MVP 외). 예시 형식: 고속 `NAEK010`/`NAEK300` |
| `dep/arr_station_id`(역ID) | `TrainInfoService`의 시도별 역 목록조회(`getCtyAcctoMnvSttnList` 계열 — 본 MVP 외). `TODO(provenance)`: 정확한 역코드 조회 오퍼레이션명은 라이브 키로 확인 필요 |

## 범위 / 제약 (공식)
- **읽기만.** 버스 도착/정류소/노선 + 고속/시외버스 운행 + 도시간 열차(MVP, 7개 도구).
- 제외(스코프 밖): 버스 **실시간 위치**(BusLcInfoService), 퍼스널 모빌리티, 터미널/역 **코드 마스터 조회**(위 표의 *목록조회 오퍼레이션 — 입력 ID 확보 경로만 안내), 노선번호 목록조회.
- 페이지네이션 `numOfRows`(기본 100, 상류 기본은 10)·`pageNo`(기본 1).
- 레이트리밋: 서비스별 **개발계정 일일 트래픽 한도**(예: 시외버스 10,000/일). 운영계정은 활용사례 등록 후 상향.
- 구 TAGO OpenAPI 13종은 **2022-09-01 호출중지**됐고, 이 6종이 현행 대체본이다(위 공지 참고).

## UNVERIFIED / provenance 노트
- **서비스 경로 접미사 `…Service`**: 고속/시외/열차 서비스의 경로 끝 `Service`는 구 OpenAPI 대체 공지·국토부 표기 기준이다. data.go.kr 영문 상세의 "Service URL"에는 축약형(`ExpBusInfo`/`TrainInfo`)이 표시되나 표시용 약어로 보이며 실 호출 경로는 `…Service`로 본다(버스 3종은 `getCtyCodeList` 샘플 링크로 확인). 라이브 키가 없어 4종 경로 직접 검증은 보류(`contract.py`의 `TODO(provenance)`).
- **응답 필드명**: data.go.kr 상세 페이지가 첫 오퍼레이션의 스키마만 렌더해, 노선 경유정류소(`nodeord`/`updowncd`)·고속/시외(`gradeNm`/`charge`)·열차(`traingradename`/`adultcharge`) 등 일부 필드명은 동 네임스페이스 표준 표기를 채택했다. 모델은 `extra="ignore"`로 느슨히 받아 변형을 흡수한다.
- 모든 코드/요금/시각 값은 **문자열**(`str | None`)로 받는다(상류가 수치도 문자열·숫자로 섞어 줄 수 있어 캐스팅하지 않음).

## 확장 포인트
- 버스 실시간 위치(`BusLcInfoService`), 터미널/역 코드 마스터(`getExpBusTrminlList`·`getSuberbsBusTrminlList`·역 목록조회), 노선번호 목록(`getRouteNoList`), 정류소별 특정노선 도착예정(`getSttnAcctoSpcifyRouteBusArvlPrearngeInfoList`)은 동일 패턴으로 서비스/오퍼레이션 경로 상수·도구 추가.
