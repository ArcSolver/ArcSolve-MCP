# NWS 서비스

NWS(National Weather Service) 미국 날씨 **읽기** 래퍼 — 예보·시간별 예보·활성 기상특보.
전부 GET·읽기. 응답은 **GeoJSON**(`application/geo+json`). **무인증**(키 없음)이지만
**`User-Agent` 헤더가 필수**다(없으면 403).

## 계약 출처 (공식 문서)
- API 안내(base·User-Agent 필수·GeoJSON·엔드포인트·`area` 코드): https://www.weather.gov/documentation/services-web-api
- OpenAPI 스펙: https://api.weather.gov/openapi.json
- 라이브 응답 확인: https://api.weather.gov/points/{lat},{lon} · `/gridpoints/{office}/{x},{y}/forecast` · `/gridpoints/{office}/{x},{y}/forecast/hourly` · `/alerts/active?area={ST}`

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트 경로 빌더·좌표/주코드 검증·GeoJSON 응답 모델).

## 인증 (없음 · User-Agent만 필수)
NWS는 **무인증**(키 없음)이지만, **`User-Agent` 헤더가 필수**다(없으면 403). 기본 식별 문자열
(`contract.DEFAULT_USER_AGENT`)을 항상 보내며, 연락처를 넣고 싶으면 `NWS_USER_AGENT`로 덮어쓴다.

| env | 쓰임 | 비고 |
|---|---|---|
| `NWS_USER_AGENT` | `User-Agent: <값>` | 선택. 미설정 시 기본 식별 문자열. 공식 권장은 연락처 포함(예: `(myapp.com, you@example.com)`) |

- 헤더는 코어 `get_json(headers=...)`로 주입한다(서비스 폴더에서 httpx 직접 생성 금지 — AGENTS 규칙).
- base `https://api.weather.gov`. 콘텐츠는 **응답 본문**(`properties`/`features`)이므로 코어 `get_json`만 쓴다.

## 엔드포인트 (전부 GET · `<base><path>`)
| 종류 | METHOD · PATH |
|------|------|
| 좌표→그리드 | `GET /points/{lat},{lon}` |
| 예보(12h 주야) | `GET /gridpoints/{office}/{x},{y}/forecast` |
| 시간별 예보 | `GET /gridpoints/{office}/{x},{y}/forecast/hourly` |
| 활성 특보 | `GET /alerts/active?area={ST}` |

Base: `https://api.weather.gov` · 인증: 없음(User-Agent 필수) · 스코프: 읽기 전용

> **2단계 조회**가 NWS 특유 패턴: 좌표→예보는 ① `/points/{lat},{lon}`로 `gridId`·`gridX`·`gridY`를 얻고 → ② `/gridpoints/{office}/{x},{y}/forecast`를 조회한다. (`/points` 응답의 `forecast` URL은 `:80` 포트가 섞여 와서, 경로를 `gridId`·`gridX`·`gridY`로 직접 재조립한다.)
> 응답 봉투: 예보는 GeoJSON `Feature`(`properties.periods[]`), 특보는 `FeatureCollection`(`features[].properties`). 에러는 RFC 7807 problem+json(`{type,title,status,detail}`).

## 셋업
1. 키 발급 단계 없음(무인증).
2. `.env`(선택): `NWS_USER_AGENT="(myapp.com, you@example.com)"` — 식별/연락용 User-Agent.

> 무인증·필수 User-Agent 방식 — 인터랙티브 OAuth가 아니므로 `arcsolve auth nws` 단계는 없다.

## 도구
| 도구 | 설명 |
|------|------|
| `nws_forecast(latitude, longitude)` | 미국 좌표의 다단계(12h 주야) 예보. 2단계(/points → /gridpoints). 기간별 온도·바람·요약 |
| `nws_hourly_forecast(latitude, longitude)` | 미국 좌표의 시간별 예보. 동일 2단계, `.../forecast/hourly` |
| `nws_alerts(area)` | 미국 주의 활성 기상특보. 2글자 주/속령 코드(CA·TX·NY·FL·DC·PR…). event·severity·영향 지역·만료 |

## 범위 / 제약 (공식)
- **읽기만.** 예보·시간별 예보·활성 특보만(MVP).
- **미국(+속령) 좌표만 유효.** 해외 좌표는 `/points`에서 404(`problems/InvalidPoint`) → "미국 좌표만 지원" 안내로 매핑.
- `area`는 2글자 주/속령 코드(50주 + DC + AS·GU·PR·VI·MP·PW·FM·MH). 그 외 코드는 상류 400 전에 차단.
- 제외: 관측소 상세(`/stations`), 존별 예보(`/zones/.../forecast`), CAP XML, 원시 그리드 데이터(`forecastGridData`), 글로서리·products.

## UNVERIFIED / provenance 노트
- `/points` 응답의 `forecast`/`forecastHourly` URL은 라이브에서 `https://api.weather.gov:80/...`처럼 **`:80` 포트가 섞여** 온다 → 그 URL을 직접 쓰지 않고 `gridId`·`gridX`·`gridY`로 경로를 재조립한다(`contract.gridpoint_forecast_path`).
- 응답은 GeoJSON `Feature`/`FeatureCollection`. 예보 콘텐츠는 `properties.periods[]`, 특보 콘텐츠는 `features[].properties`. 부분 모델(`extra="ignore"`)로 핵심 필드만 받는다.
- `area` 유효 코드 목록은 라이브 400(`parameterErrors`의 enumeration)에서 확보했다(`contract.VALID_STATE_AREAS`).

## 확장 포인트
- 관측소 최신 관측(`/stations/{id}/observations/latest`), 존별 예보(`/zones/forecast/{id}/forecast`), 특보 단건(`/alerts/{id}`)·다양한 필터(`?status=`·`?severity=`·`?event=`)는 동일 패턴으로 경로 상수·도구 추가. 원시 그리드 데이터(`forecastGridData`)는 별도 파싱 필요.
