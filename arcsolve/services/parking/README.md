# Parking(한국교통안전공단 전국 주차정보) 서비스

한국교통안전공단(KOTSA) **주차정보 제공 API** **읽기** 래퍼 — 전국 주차장 **시설정보**(이름·주소·
위경도·총 주차면)·**운영정보**(운영시간·요금)·**실시간 잔여면**(현재 주차가능 구획 수). 전부
GET·JSON. 단일 base `B553881/Parking` 아래 3개 오퍼레이션이 **하나의 data.go.kr 서비스키로
전부 커버**된다. 모든 오퍼레이션은 **주차장관리번호 `prk_center_id`를 PK**로 공유한다(데이터
형식은 ITS Korea 실시간 주차정보 수집·연계 규격 준용). **서비스키 필수**(공공데이터포털 발급),
키는 **쿼리 파라미터 `serviceKey`**다(OAuth 아님).

> ⚠️ **실시간 잔여면 제공은 연동 주차장 한정.** 공식 안내상 **운영정보·실시간 정보는 시설정보보다
> 데이터 수가 훨씬 적습니다** — 시스템에 연동된 일부 주차장만 실시간 잔여면을 제공하고, 전국
> 대다수 주차장은 정적 시설정보만 있습니다. 과장된 커버리지를 기대하지 마세요(`parking_realtime`이
> 비어 있어도 정상일 수 있습니다).

## 계약 출처 (공식 문서)
- 한국교통안전공단 주차정보 제공 API: https://www.data.go.kr/data/15099883/openapi.do
  - `PrkSttusInfo`(주차장 시설정보 — 이름·주소·위경도·총 주차구획 수, PK `prk_center_id`)
  - `PrkOprInfo`(주차장 운영정보 — 운영시간·요금 체계)
  - `PrkRealtimeInfo`(주차장 실시간 정보 — 현재 주차가능 구획 수 ⭐ 연동 주차장 한정)

> base `http://apis.data.go.kr/B553881/Parking/<operation>`. 공통 필수 파라미터(serviceKey·pageNo·numOfRows·**format** 1=XML/2=JSON), PK=주차장관리번호(`prk_center_id`), 시설정보 응답 필드(`prk_plce_nm`/`prk_plce_adres`/`prk_plce_entrc_la`/`prk_plce_entrc_lo`/`prk_cmprt_co`)는 위 페이지 상세에서 확인된다.
>
> 운영/실시간 오퍼레이션 경로(`PrkOprInfo`/`PrkRealtimeInfo`)와 그 응답 필드는 상세 페이지 내려받기 기술문서(주차정보시스템 기술문서)에 정의되며, 본 구현은 **다수 외부 구현으로 교차확인**해 채택했다(provenance 노트 참조). 미확정 필드는 `contract.py`의 `TODO(provenance)`로 표시하고 `extra="ignore"`로 흡수한다.
>
> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(오퍼레이션 경로·쿼리 빌더·응답 모델·items 정규화).

## 인증 (필수)
`ParkingSettings`(`PARKING_*`)가 서비스키를 로드한다. **헤더가 아니라 쿼리 파라미터**다. 단일 키로 3개 오퍼레이션 전부 커버.

| env | 쿼리 파라미터 | 비고 |
|---|---|---|
| `PARKING_SERVICE_KEY` | `serviceKey=<키>` | 필수. data.go.kr에서 발급 |

> ⚠️ **Decoding 키(원문)를 넣으세요.** data.go.kr 서비스키는 **Encoding/Decoding 2종**으로 발급됩니다. httpx가 쿼리 파라미터를 자동 URL-인코딩하므로, 이미 인코딩된 키를 넣으면 **이중 인코딩**되어 `등록되지 않은 서비스키(30)` 오류가 납니다. 반드시 **Decoding 키(원문)**를 사용하세요.
> 키가 없으면 HTTP 호출 전에 안내 문자열을 반환합니다(`format=2`는 항상 자동으로 붙습니다 — 미지정 시 상류가 XML을 줍니다).

## 엔드포인트 (전부 GET · `http://apis.data.go.kr/B553881/Parking/<op>`)
| 도구 | operation |
|------|------|
| 시설정보 | `PrkSttusInfo?serviceKey=&pageNo=&numOfRows=&format=2` |
| 운영정보 | `PrkOprInfo?serviceKey=&pageNo=&numOfRows=&format=2` |
| 실시간정보 ⭐ | `PrkRealtimeInfo?serviceKey=&pageNo=&numOfRows=&format=2` |

> 응답 봉투(**B553881 고유 — tago/airkorea와 다름**): 최상위 dict에 `{resultCode, resultMsg, numOfRows, pageNo, totalCount, <오퍼레이션명>: [항목...]}`. 즉 **항목 배열이 오퍼레이션명 키(`PrkSttusInfo`/`PrkOprInfo`/`PrkRealtimeInfo`) 바로 아래**에 실린다(표준 `response.body.items.item` 래핑이 아님). **`resultCode != "00"`이면 에러**(서비스키 오류·무데이터 등) — HTTP 200이라도 봉투로 온다. 게이트웨이 키 차단은 `cmmMsgHeader.returnReasonCode`로 올 수 있어 함께 검사한다. ⚠️ quirk: 결과가 1건이면 오퍼레이션명 값이 **단일 객체**, 0건이면 키가 없거나 빈 값 — `contract.normalize_items`가 흡수한다. 좌표·요금·시각·면수는 **문자열**로 받는다(캐스팅하지 않음).

## 셋업
1. [공공데이터포털](https://www.data.go.kr/data/15099883/openapi.do)에서 한국교통안전공단 '주차정보 제공 API'를 활용 신청 → **Decoding 서비스키** 확인.
2. `.env`:
   - `PARKING_SERVICE_KEY=<Decoding 키>`

> 서비스키는 사전발급 쿼리 파라미터 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve auth parking` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `parking_search(numOfRows?, pageNo?)` | 전국 주차장 **시설정보**(주차장명·도로명주소·위경도·총 주차구획 수·PK). 페이지로 조회 |
| `parking_operation(numOfRows?, pageNo?)` | 주차장 **운영정보**(운영시간·기본/추가 요금·무료회차 시간). ⚠️ 시설정보보다 데이터 수 적음 |
| `parking_realtime(numOfRows?, pageNo?)` ⭐ | 주차장 **실시간 잔여면**(현재 주차가능/총 구획 수). ⚠️ **연동 주차장 한정** — 대다수 미제공 |

> 세 오퍼레이션은 개별 주차장 필터 입력 없이 **전국 목록을 페이지(`numOfRows`/`pageNo`)로** 받는다. 같은 주차장은 세 응답에서 **`prk_center_id`(주차장관리번호)로 연결**된다.

## 범위 / 제약 (공식)
- **읽기만.** 시설정보 + 운영정보 + 실시간 잔여면(MVP, 3개 도구).
- **⚠️ 실시간 잔여면은 연동된 일부 주차장만** 제공된다(공식 안내: 운영·실시간 정보는 시설정보보다 데이터 수가 적음). 표준/대다수 주차장은 정적 시설정보 전용.
- 제외(스코프 밖): 서울 공영주차장(별도 데이터셋), 주정차금지구역 등 표준데이터(정적 전용), 개별 주차장관리번호 기반 단건 조회(상류가 전국 페이지 목록만 제공).
- 페이지네이션 `numOfRows`(기본 100)·`pageNo`(기본 1) — 4개 파라미터 전부 상류 필수.
- 레이트리밋: data.go.kr **개발계정 일일 트래픽 한도**(운영계정은 활용사례 등록 후 상향).

## provenance 노트 (독립 검증 결과)
- **base·시설정보(PrkSttusInfo)** — data.go.kr 상세 페이지에서 직접 확인: base `http://apis.data.go.kr/B553881/Parking`, 요청주소 `…/PrkSttusInfo`, 필수 파라미터 `serviceKey`·`pageNo`·`numOfRows`·`format`(1=XML/2=JSON), 응답 필드 `prk_center_id`(PK)·`prk_plce_nm`·`prk_plce_adres`·`prk_plce_entrc_la`/`prk_plce_entrc_lo`·`prk_cmprt_co`, PK=주차장관리번호.
- **운영(PrkOprInfo)·실시간(PrkRealtimeInfo) 오퍼레이션 경로 및 필드** — 상세 페이지가 표를 전부 렌더하지 않고 필드 정의를 내려받기 기술문서(.docx)에 둬 인라인 확인이 불가했다. **다수 외부 구현(실제 API 호출 코드·외부 API 사용 문서)으로 교차확인**해 채택: 오퍼레이션명 `PrkSttusInfo`/`PrkOprInfo`/`PrkRealtimeInfo`, 운영 필드 `opertn_start_time`/`opertn_end_time`/`opertn_bs_free_time`/`parking_chrge_bs_time`/`parking_chrge_bs_chrg`/`parking_chrge_adit_unit_time`/`parking_chrge_adit_unit_chrge`, 실시간 필드 `pkfc_ParkingLots_total`(총 주차가능 구획)/`pkfc_Available_ParkingLots_total`(현재 주차가능 구획 = 잔여면). 실시간 잔여면 필드는 **둘 이상의 독립 구현의 실제 JSON 파싱**(`rt.pkfc_Available_ParkingLots_total`)으로 교차확인됨.
- **봉투 형태** — 표준 `response.body.items.item[]`이 **아니라** 최상위에 결과코드/페이지네이션 + **오퍼레이션명 키 아래 항목 배열**. 둘 이상의 독립 구현이 `data[<오퍼레이션명>]`로 항목을 꺼냄(교차확인). `normalize_items`가 단일/배열/누락을 흡수하며, 표준 래핑으로 올 경우도 보조 흡수한다.
- **미확정** — 시설정보의 노상/노외/부설 **구분 필드**와 요일별 운영시간(`Mo_open_time` 등) 표기는 구현별로 갈려 단일 대표 필드만 모델링(`contract.py`의 `TODO(provenance)`). `extra="ignore"`로 추가 필드를 흡수하며 추정하지 않는다.
- 모든 좌표/요금/시각/면수 값은 **문자열**(`str | None`)로 받는다(상류가 수치도 문자열·숫자로 섞어 줄 수 있어 캐스팅하지 않음).
- 라이브 서비스키가 없어 4xx/5xx·실데이터 경로는 mock으로만 검증함(요청 조립·봉투·items quirk·에러 매핑).

## 확장 포인트
- 노상/노외/부설 구분·요일별 운영시간·전화번호 등 추가 필드는 기술문서 확정 후 동일 패턴으로 모델에 추가(현재 `extra="ignore"`로 흡수 중). 주차장관리번호 단건 조회가 상류에 추가되면 빌더에 PK 파라미터를 더한다.
