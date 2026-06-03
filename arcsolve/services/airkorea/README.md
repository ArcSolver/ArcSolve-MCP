# AirKorea(에어코리아) 서비스

한국환경공단 **대기오염정보**(ArpltnInforInqireSvc) **읽기** 래퍼 — 시도별·측정소별 실시간
측정정보와 대기질 예보통보. 전부 GET·JSON. **서비스키 필수**(공공데이터포털 발급), 키는
**쿼리 파라미터 `serviceKey`**다(OAuth 아님).

## 계약 출처 (공식 문서)
- 대기오염정보 OpenAPI(ArpltnInforInqireSvc) 상세: https://www.data.go.kr/data/15073861/openapi.do

> base `http://apis.data.go.kr/B552584/ArpltnInforInqireSvc`. 공통 파라미터(serviceKey·returnType·numOfRows·pageNo), 봉투 구조(`response.header`/`response.body.items`), 예보(getMinuDustFrcstDspth) 파라미터/필드는 위 페이지에서 확인된다. 두 실시간 조회 operation의 ver별 필드 확장·sidoName/dataTerm 표는 위 페이지의 다운로드 기술문서(zip)에 있다.
>
> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 경로·쿼리 빌더·응답 모델).

## 인증 (필수)
`AirKoreaSettings`(`AIRKOREA_*`)가 서비스키를 로드한다. **헤더가 아니라 쿼리 파라미터**다.

| env | 쿼리 파라미터 | 비고 |
|---|---|---|
| `AIRKOREA_SERVICE_KEY` | `serviceKey=<키>` | 필수. data.go.kr에서 발급 |

> ⚠️ **Decoding 키(원문)를 넣으세요.** data.go.kr 서비스키는 **Encoding/Decoding 2종**으로 발급됩니다. httpx가 쿼리 파라미터를 자동 URL-인코딩하므로, 이미 인코딩된 키를 넣으면 **이중 인코딩**되어 `등록되지 않은 서비스키(30)` 오류가 납니다. 반드시 **Decoding 키(원문)**를 사용하세요.
> 키가 없으면 HTTP 호출 전에 안내 문자열을 반환합니다(`returnType=json`은 항상 자동으로 붙습니다 — 미지정 시 상류가 XML을 줄 수 있음).

## 엔드포인트 (전부 GET · `<base><path>`)
| 도구 | METHOD · PATH |
|------|------|
| 시도별 실시간 | `GET /getCtprvnRltmMesureDnsty?sidoName=&ver=&numOfRows=&pageNo=` |
| 측정소별 실시간 | `GET /getMsrstnAcctoRltmMesureDnsty?stationName=&dataTerm=&ver=&numOfRows=&pageNo=` |
| 대기질 예보통보 | `GET /getMinuDustFrcstDspth?searchDate=&informCode=&numOfRows=&pageNo=` |

> 응답 봉투: `{response:{header:{resultCode,resultMsg}, body:{items:[...], totalCount, pageNo, numOfRows}}}`. **`resultCode != "00"`이면 에러**(서비스키 오류 등) — HTTP 200이라도 봉투로 온다. 측정값(`pm10Value`·`khaiValue` 등)은 **문자열**이며 결측은 `"-"`다.

## 셋업
1. [공공데이터포털 대기오염정보 OpenAPI](https://www.data.go.kr/data/15073861/openapi.do)에서 활용 신청 → **Decoding 서비스키** 확인.
2. `.env`:
   - `AIRKOREA_SERVICE_KEY=<Decoding 키>`

> 서비스키는 사전발급 쿼리 파라미터 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth airkorea` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `airkorea_realtime_by_region(sidoName, ver?, numOfRows?, pageNo?)` | 시도별 실시간 측정정보. 시도 내 측정소별 PM10/PM2.5/O3/NO2/CO/SO2·통합지수(khai). `sidoName`=전국·서울·부산·…·세종 |
| `airkorea_realtime_by_station(stationName, dataTerm?, ver?, numOfRows?, pageNo?)` | 측정소별 실시간 측정정보(시간대별). `dataTerm`=DAILY(기본)·MONTH·3MONTH |
| `airkorea_forecast(searchDate, informCode?, numOfRows?, pageNo?)` | 대기질 예보통보. 권역별 등급·개황·원인·행동요령. `searchDate`=`YYYY-MM-DD`, `informCode`=PM10·PM25·O3(선택) |

## 범위 / 제약 (공식)
- **읽기만.** 시도/측정소 실시간 측정 + 예보통보(MVP).
- 제외: 측정소 목록 조회(별도 `MsrstnInfoInqireSvc`), 통합대기환경지수(CAI) 상세, 통계, 주간예보.
- `ver`(시도별/측정소별): 기본 **1.3**(PM2.5 포함). 1.0=기본 6항목+통합지수, 1.3=PM2.5, 1.4=PM10/PM2.5 24시간 예측이동농도(`pm10Value24`/`pm25Value24`).
- 레이트리밋: **개발계정 500건/일**(운영계정은 활용사례 등록 후 상향).

## UNVERIFIED / provenance 노트
- 두 실시간 조회 operation의 `ver`별 정확한 필드 추가 범위(1.1/1.2/1.5/1.6 세부)와 `sidoName`/`dataTerm` 허용값 표는 data.go.kr **다운로드 기술문서(zip)**에만 있어 상세 페이지에서 인라인 확인이 어렵다. 응답 모델은 `extra="ignore"`로 느슨히 받아 버전차를 흡수한다(`contract.py`의 `TODO(provenance)` 참고).
- 측정값/등급 필드는 전부 **문자열**(`str | None`)로 받는다(상류가 수치도 문자열로 주고 결측은 `"-"` — 캐스팅하지 않는다).

## 확장 포인트
- 측정소 목록(`MsrstnInfoInqireSvc`), 통합대기환경지수 상세, 주간예보(`getMinuDustWeekFrcstDspth`)는 동일 패턴으로 경로 상수·도구 추가.
