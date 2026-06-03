"""Open-Meteo 날씨·기후 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 쿼리 제약/빌더, 응답 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·JSON·읽기. **무인증**(키 없음 — apikey는 상업용 도메인 전용, 범위 밖). 코어 `get_json`만으로
충분하다(페이지네이션·헤더 동사 불필요 — 단발 조회). hourly/daily/current 변수는 **콤마 구분 문자열**로
받아 그대로 쿼리에 전달한다(변수명 검증은 상류에 위임 — 카탈로그가 방대해 화이트리스트 환각 위험).

출처(공식 문서 — open-meteo.com + 라이브 응답 확인):
  - 예보 API 문서(엔드포인트·파라미터·forecast_days 0–16·hourly/daily/current·응답 구조·에러 봉투):
    https://open-meteo.com/en/docs
  - 지오코딩 API 문서(엔드포인트·name/count/language/countryCode·results 필드):
    https://open-meteo.com/en/docs/geocoding-api
  - 라이브 응답 확인: https://api.open-meteo.com/v1/forecast · https://geocoding-api.open-meteo.com/v1/search
"""

from __future__ import annotations

from pydantic import BaseModel

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처(예보 base·path): 예보 문서 ("https://api.open-meteo.com/v1/forecast")
# 출처(지오코딩 base·path): 지오코딩 문서 ("https://geocoding-api.open-meteo.com/v1/search")
FORECAST_BASE_URL = "https://api.open-meteo.com/v1"
GEOCODING_BASE_URL = "https://geocoding-api.open-meteo.com/v1"
FORECAST = "/forecast"
GEOCODING_SEARCH = "/search"


# ─── 쿼리 파라미터 제약(공식) ───────────────────────────────
# 출처(지오코딩): 지오코딩 문서 (count 기본 10·"Up to 100 results can be retrieved")
GEOCODING_DEFAULT_COUNT = 10
GEOCODING_MIN_COUNT = 1
GEOCODING_MAX_COUNT = 100

# 출처(예보): 예보 문서 (forecast_days 기본 7·범위 "0-16")
FORECAST_DEFAULT_DAYS = 7
FORECAST_MIN_DAYS = 0
FORECAST_MAX_DAYS = 16

# 공식 쿼리 파라미터명(정확한 철자).
# 출처(예보): 예보 문서 (latitude·longitude·hourly·daily·current·timezone·forecast_days)
PARAM_LATITUDE = "latitude"
PARAM_LONGITUDE = "longitude"
PARAM_HOURLY = "hourly"
PARAM_DAILY = "daily"
PARAM_CURRENT = "current"
PARAM_TIMEZONE = "timezone"
PARAM_FORECAST_DAYS = "forecast_days"
# 출처(지오코딩): 지오코딩 문서 (name·count·language·countryCode — countryCode는 camelCase)
PARAM_NAME = "name"
PARAM_COUNT = "count"
PARAM_LANGUAGE = "language"
PARAM_COUNTRY_CODE = "countryCode"


def validate_count(count: int) -> int:
    """지오코딩 count를 1..100 범위로 검증한다(공식 제약).

    출처: 지오코딩 문서 (기본 10 · "Up to 100 results can be retrieved").
    """
    if count < GEOCODING_MIN_COUNT or count > GEOCODING_MAX_COUNT:
        raise ValueError(
            f"count는 {GEOCODING_MIN_COUNT}..{GEOCODING_MAX_COUNT} 범위여야 합니다(현재 {count})."
        )
    return count


def validate_forecast_days(days: int) -> int:
    """forecast_days를 0..16 범위로 검증한다(공식 제약).

    출처: 예보 문서 (기본 7 · 범위 "0-16"). 위반 시 상류가 400 에러를 주기 전에 미리 막는다.
    """
    if days < FORECAST_MIN_DAYS or days > FORECAST_MAX_DAYS:
        raise ValueError(
            f"forecast_days는 {FORECAST_MIN_DAYS}..{FORECAST_MAX_DAYS} 범위여야 합니다(현재 {days})."
        )
    return days


def build_geocoding_params(
    *,
    name: str,
    count: int | None = None,
    language: str | None = None,
    country_code: str | None = None,
) -> dict[str, str | int]:
    """지오코딩 검색 쿼리스트링을 만든다. None/빈값은 생략한다.

    - name → `name`(필수, 2자=정확 매칭·3자+=퍼지 매칭)
    - count → `count`(1..100 검증, 미지정 시 생략 → 상류 기본 10)
    - language → `language`(소문자 ISO 언어 코드, 예 `en`/`ko`)
    - country_code → `countryCode`(ISO-3166-1 alpha2, camelCase 주의)
    출처: 지오코딩 문서 (name·count·language·countryCode)
    """
    params: dict[str, str | int] = {PARAM_NAME: name}
    if count is not None:
        params[PARAM_COUNT] = validate_count(count)
    if language:
        params[PARAM_LANGUAGE] = language
    if country_code:
        params[PARAM_COUNTRY_CODE] = country_code
    return params


def build_forecast_params(
    *,
    latitude: float,
    longitude: float,
    hourly: str | None = None,
    daily: str | None = None,
    current: str | None = None,
    timezone: str | None = None,
    forecast_days: int | None = None,
) -> dict[str, str | int | float]:
    """예보 쿼리스트링을 만든다. None/빈값은 생략한다.

    - latitude/longitude → `latitude`/`longitude`(필수, WGS84)
    - hourly/daily/current → 동명 파라미터(**콤마 구분 변수명 문자열** 그대로 전달,
      예 `temperature_2m,precipitation`). 변수 카탈로그 검증은 상류에 위임(화이트리스트 환각 회피).
    - timezone → `timezone`(IANA 이름 또는 `auto`, 미지정 시 상류 기본 GMT)
    - forecast_days → `forecast_days`(0..16 검증, 미지정 시 상류 기본 7)
    출처: 예보 문서 (latitude·longitude·hourly·daily·current·timezone·forecast_days)
    """
    params: dict[str, str | int | float] = {
        PARAM_LATITUDE: latitude,
        PARAM_LONGITUDE: longitude,
    }
    if hourly:
        params[PARAM_HOURLY] = hourly
    if daily:
        params[PARAM_DAILY] = daily
    if current:
        params[PARAM_CURRENT] = current
    if timezone:
        params[PARAM_TIMEZONE] = timezone
    if forecast_days is not None:
        params[PARAM_FORECAST_DAYS] = validate_forecast_days(forecast_days)
    return params


# ─── 응답 모델 ──────────────────────────────────────────────
# extra="ignore"로 느슨히 받고(부분 모델), 확신하는 필드만 모델링한다.
# 변수별 시계열(hourly/daily/current)은 변수명이 동적이라 dict로 받는다(스키마 고정 불가).


class GeocodingResult(BaseModel):
    """지오코딩 검색 결과 1건(부분).

    공식/라이브 필드(지오코딩 문서 + 라이브): id(Integer) · name(String) ·
    latitude·longitude·elevation(Float) · timezone(String) · feature_code(String) ·
    country_code(String) · country(String) · country_id(Integer) · population(Integer) ·
    admin1..admin4(String). "Empty fields are not returned"이므로 전부 선택(Optional)이다.
    출처: 지오코딩 문서 (results 오브젝트 필드) + 라이브 /search?name=Berlin
    """

    model_config = {"extra": "ignore"}

    id: int | None = None
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    timezone: str | None = None
    feature_code: str | None = None
    country: str | None = None
    country_code: str | None = None
    population: int | None = None
    admin1: str | None = None
    admin2: str | None = None


class GeocodingResponse(BaseModel):
    """지오코딩 검색 응답 봉투 `{results:[...], generationtime_ms}`.

    ⚠️ 매칭이 없으면 `results` 키가 **아예 없다**(라이브: 빈 배열이 아니라 키 부재) →
    기본값 `[]`로 받아 안전하게 처리한다.
    출처: 지오코딩 문서 (results 배열) + 라이브 (/search?name=zzzznoplace → {"generationtime_ms":...})
    """

    model_config = {"extra": "ignore"}

    results: list[GeocodingResult] = []
    generationtime_ms: float | None = None


class ForecastResponse(BaseModel):
    """예보 응답 봉투(부분).

    공식/라이브 최상위 필드: latitude·longitude·elevation(Float) · generationtime_ms(Float) ·
    utc_offset_seconds(Integer) · timezone·timezone_abbreviation(String) ·
    hourly·daily·current(Object: {time, <변수>:[...]}) · hourly_units·daily_units·current_units(Object).
    변수명이 동적(요청에 따라 달라짐)이라 시계열/단위 블록은 dict로 받는다.
    `current`는 시계열이 아니라 단일 시각의 스칼라 값들 + `time`/`interval`이다(라이브 확인).
    출처: 예보 문서 (응답 구조) + 라이브 /forecast?...&current=...&hourly=...&daily=...
    """

    model_config = {"extra": "ignore"}

    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    generationtime_ms: float | None = None
    utc_offset_seconds: int | None = None
    timezone: str | None = None
    timezone_abbreviation: str | None = None
    hourly: dict | None = None
    hourly_units: dict | None = None
    daily: dict | None = None
    daily_units: dict | None = None
    current: dict | None = None
    current_units: dict | None = None


class ErrorResponse(BaseModel):
    """Open-Meteo 에러 봉투 `{"error": true, "reason": "..."}`(HTTP 400).

    라이브 확인: 좌표 누락/잘못된 변수명 → 400 `{"reason":"...","error":true}`.
    출처: 예보 문서 (에러 응답) + 라이브 (/forecast?latitude=52.52 → 400)
    """

    model_config = {"extra": "ignore"}

    error: bool | None = None
    reason: str | None = None
