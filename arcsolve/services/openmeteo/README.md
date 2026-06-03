# Open-Meteo 서비스

Open-Meteo 날씨·기후 **읽기** 래퍼 — 좌표 기반 예보(forecast)와 지명→좌표 지오코딩(geocoding).
전부 GET·JSON. **무인증**(키 없음·env 불필요). 식별용 User-Agent만 전송한다.

## 계약 출처 (공식 문서)
- 예보 API 문서(엔드포인트·파라미터·`forecast_days` 0–16·hourly/daily/current·응답 구조·에러 봉투): https://open-meteo.com/en/docs
- 지오코딩 API 문서(엔드포인트·`name`/`count`/`language`/`countryCode`·`results` 필드): https://open-meteo.com/en/docs/geocoding-api
- 라이브 응답 확인: https://api.open-meteo.com/v1/forecast · https://geocoding-api.open-meteo.com/v1/search

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 상수·쿼리 제약·쿼리 빌더·응답 모델).

## 인증 (없음)
Open-Meteo는 비상업 사용에 **무인증**이다(`apikey`는 상업용 도메인 전용 — 범위 밖). 별도 env가 필요 없다.

- base 예보 `https://api.open-meteo.com/v1`, 지오코딩 `https://geocoding-api.open-meteo.com/v1`.
- 단발 조회라 페이지네이션/헤더 동사가 없어 코어 `get_json`만 쓴다.

## 엔드포인트 (전부 GET · `<base><path>`)
| 종류 | METHOD · PATH |
|------|------|
| 예보 | `GET api.open-meteo.com/v1/forecast?latitude=&longitude=&hourly=&daily=&current=&timezone=&forecast_days=` |
| 지오코딩 | `GET geocoding-api.open-meteo.com/v1/search?name=&count=&language=&countryCode=` |

인증: 없음 · 스코프: 읽기 전용

> `hourly`/`daily`/`current`는 **콤마 구분 변수명 문자열**(예 `temperature_2m,precipitation`)로 그대로 전달한다. 변수 카탈로그가 방대해 화이트리스트 검증은 상류에 위임한다.
> `forecast_days`는 0–16(기본 7). `count`는 1–100(기본 10). `timezone`은 IANA 이름 또는 `auto`.
> 예보 응답: `{latitude, longitude, elevation, timezone, hourly:{time:[],<변수>:[]}, hourly_units:{...}, daily:{...}, daily_units:{...}, current:{time, <변수>:value}, current_units:{...}}`. 지오코딩 응답: `{results:[{id,name,latitude,longitude,country,country_code,timezone,admin1,...}]}` — **매칭이 없으면 `results` 키가 아예 없다**.

## 셋업
1. 키 발급 단계 없음(무인증).
2. env 변경 불필요(`.env.example` 무변경).

> 무인증 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth openmeteo` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `openmeteo_geocode(name, count?, language?)` | 지명→좌표·국가·시간대. `openmeteo_forecast`의 좌표 입력 보조. count 기본 10·1..100 |
| `openmeteo_forecast(latitude, longitude, hourly?, daily?, current?, timezone?, forecast_days?)` | 좌표 날씨 예보. hourly/daily/current는 콤마 구분 변수명 문자열. `forecast_days` 기본 7·0..16 |

## 범위 / 제약 (공식)
- **읽기만.** 예보 + 지오코딩 검색만(MVP).
- 제외: air-quality·marine·flood 등 별도 엔드포인트, 상업용 도메인(`customer-`/`apikey`), 모델 수동선택(`models`), `past_days`/단위 변환(`temperature_unit` 등)·`timeformat`·`elevation`·`cell_selection` 등 부가 파라미터, 과거 기록(Historical/ERA5) API.
- `forecast_days` 0–16(기본 7). `count` 1–100(기본 10). 변수명은 콤마 구분 문자열로 그대로 전달(검증 상류 위임).

## UNVERIFIED / provenance 노트
- hourly/daily/current 변수 카탈로그가 방대하고 동적이라(요청에 따라 응답 키가 달라짐) 시계열/단위 블록은 `dict`로 느슨히 받는다. 변수명 검증은 하지 않고 상류 400(`{"error":true,"reason":"...invalid String value..."}`)에 위임한다.
- 지오코딩은 매칭이 없을 때 **`results` 키 자체가 없는** 봉투(`{"generationtime_ms":...}`)를 반환한다(라이브 확인) → `GeocodingResponse.results` 기본값 `[]`로 안전 처리.
- `current` 블록은 시계열이 아니라 단일 시각의 스칼라 값 + `time`/`interval`이다(라이브 확인). 작업 문서의 `forecast_days` 1–16 표기와 달리 공식 문서는 **0–16**이라 0–16을 따랐다.

## 확장 포인트
- `past_days`(과거 일수), 단위 파라미터(`temperature_unit`·`wind_speed_unit`·`precipitation_unit`), `timeformat`, `models`(모델 선택), `elevation`/`cell_selection`은 동일 패턴으로 쿼리 빌더에 파라미터 추가. air-quality(`air-quality-api`)·marine(`marine-api`)·flood·Historical(ERA5) 등 별도 엔드포인트는 base 상수·도구 추가로 확장.
