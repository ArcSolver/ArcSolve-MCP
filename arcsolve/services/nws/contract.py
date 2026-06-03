"""NWS(National Weather Service) 미국 날씨 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 경로 빌더, 좌표/주코드 검증, GeoJSON 응답 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·읽기. **무인증**(키 없음). 단, NWS는 **`User-Agent` 헤더가 필수**다(없으면 403). 식별용
기본 User-Agent를 `DEFAULT_USER_AGENT` 상수로 둔다(env로 덮어쓸 수 있게 tools에서 처리). 응답은
**GeoJSON**(`application/geo+json`)으로, 콘텐츠는 `properties`(단건/그리드 예보) 또는 `features`
(FeatureCollection, 특보 목록)에 실린다.

NWS 특유 패턴: 좌표→예보는 **2단계**다. `/points/{lat},{lon}`로 office/grid(gridId·gridX·gridY)와
`forecast` URL을 얻고, 그 다음 `/gridpoints/{office}/{x},{y}/forecast`(또는 `.../forecast/hourly`)를
조회한다. **미국(+속령) 좌표만 유효** — 해외 좌표는 404(`problems/InvalidPoint`)다.

출처(공식 문서 — weather.gov API + api.weather.gov 라이브):
  - API 안내(base·User-Agent 필수·GeoJSON·엔드포인트·area 코드): https://www.weather.gov/documentation/services-web-api
  - OpenAPI 스펙: https://api.weather.gov/openapi.json
  - 라이브 응답 확인: https://api.weather.gov/points/{lat},{lon} ·
    /gridpoints/{office}/{x},{y}/forecast · /gridpoints/{office}/{x},{y}/forecast/hourly ·
    /alerts/active?area={ST}
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처(base): API 안내 ("The API is located at https://api.weather.gov") + 라이브
BASE_URL = "https://api.weather.gov"

# ─── User-Agent (필수) ──────────────────────────────────────
# NWS는 User-Agent 헤더가 없으면 403을 준다(라이브 확인). 공식 안내는 "A User Agent is required
# to identify your application"이며 연락처 포함을 권장한다. 기본값을 상수로 두고 env로 덮어쓴다.
# 출처: API 안내 ("User Agent ... is required") + 라이브(헤더 없음 → 403).
DEFAULT_USER_AGENT = "ArcSolve-MCP (github.com/ArcSolver/ArcSolve-Kit)"


def points_path(latitude: float, longitude: float) -> str:
    """좌표→그리드 변환 경로 /points/{lat},{lon}.

    소수점 좌표를 콤마로 잇는다(NWS는 소수 4자리 이내를 권장하나 그대로 전달). 미국 밖 좌표는
    404(`problems/InvalidPoint`, title "Data Unavailable For Requested Point")로 온다(라이브 확인).
    출처: API 안내 (/points/{latitude},{longitude}) + 라이브.
    """
    return f"/points/{latitude},{longitude}"


def gridpoint_forecast_path(office: str, grid_x: int, grid_y: int, *, hourly: bool = False) -> str:
    """그리드 예보 경로 /gridpoints/{office}/{x},{y}/forecast[/hourly].

    `/points` 응답의 gridId(=office)·gridX·gridY로 직접 조립한다(응답의 `forecast` URL은 `:80`
    포트가 섞여 오므로 경로를 직접 만든다). hourly=True면 시간별 예보 경로.
    출처: API 안내 (/gridpoints/{wfo}/{x},{y}/forecast, .../forecast/hourly) + 라이브.
    """
    suffix = "/forecast/hourly" if hourly else "/forecast"
    return f"/gridpoints/{office}/{grid_x},{grid_y}{suffix}"


ALERTS_ACTIVE = "/alerts/active"


# ─── 좌표 / 주코드 검증 ─────────────────────────────────────
# 위도 -90..90, 경도 -180..180 (좌표 기본 범위). NWS 좌표 검증 자체는 서버가 하지만(미국 밖은
# 404), 명백한 범위 밖은 HTTP 전에 막는다.
MIN_LATITUDE, MAX_LATITUDE = -90.0, 90.0
MIN_LONGITUDE, MAX_LONGITUDE = -180.0, 180.0

# `/alerts/active?area=`의 유효 코드(공식 enum, 라이브 400 응답에서 확인).
# 50개 주 + DC + 속령/자유연합(AS·GU·PR·VI·MP·PW·FM·MH) — 모두 2글자(대문자).
# 출처: 라이브 (/alerts/active?area=ZZ → 400 parameterErrors의 enumeration).
VALID_STATE_AREAS = frozenset(
    {
        "AL", "AK", "AS", "AR", "AZ", "CA", "CO", "CT", "DE", "DC",
        "FL", "GA", "GU", "HI", "ID", "IL", "IN", "IA", "KS", "KY",
        "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE",
        "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR",
        "PA", "PR", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VI",
        "VA", "WA", "WV", "WI", "WY", "MP", "PW", "FM", "MH",
    }
)


def validate_latitude(latitude: float) -> float:
    """위도를 -90..90 범위로 검증한다."""
    if latitude < MIN_LATITUDE or latitude > MAX_LATITUDE:
        raise ValueError(
            f"latitude는 {MIN_LATITUDE}..{MAX_LATITUDE} 범위여야 합니다(현재 {latitude})."
        )
    return latitude


def validate_longitude(longitude: float) -> float:
    """경도를 -180..180 범위로 검증한다."""
    if longitude < MIN_LONGITUDE or longitude > MAX_LONGITUDE:
        raise ValueError(
            f"longitude는 {MIN_LONGITUDE}..{MAX_LONGITUDE} 범위여야 합니다(현재 {longitude})."
        )
    return longitude


def validate_area(area: str) -> str:
    """`area`를 2글자 주/속령 코드(대문자)로 정규화·검증한다(공식 enum).

    소문자로 줘도 대문자로 맞춰 검증한다. 미국 외/오타 코드는 상류가 400을 주기 전에 막는다.
    출처: 라이브 (/alerts/active?area=<bad> → 400 enumeration).
    """
    code = area.strip().upper()
    if code not in VALID_STATE_AREAS:
        raise ValueError(
            f"area는 미국 2글자 주/속령 코드여야 합니다(현재 {area!r}). "
            "예: CA, TX, NY, FL, DC, PR."
        )
    return code


# ─── 응답 모델 (GeoJSON 부분 모델) ─────────────────────────
# GeoJSON Feature 봉투: {"type","geometry","properties":{...}}. 콘텐츠는 properties에 실린다.
# extra="ignore"로 느슨히 받고(부분 모델), 확신하는 필드만 모델링한다.


class PointProperties(BaseModel):
    """`/points/{lat},{lon}` 응답의 `properties`(부분).

    그리드 식별자(gridId·gridX·gridY)와 예보 URL(forecast·forecastHourly)을 담는다. gridId는
    발령 오피스(=cwa). 라이브의 `forecast`/`forecastHourly`는 `:80` 포트가 섞여 와서 직접
    쓰지 않고 gridId·gridX·gridY로 경로를 재조립한다(gridpoint_forecast_path).
    출처: 라이브 /points (properties: cwa·gridId·gridX·gridY·forecast·forecastHourly).
    """

    model_config = {"extra": "ignore"}

    grid_id: str | None = Field(default=None, alias="gridId")
    grid_x: int | None = Field(default=None, alias="gridX")
    grid_y: int | None = Field(default=None, alias="gridY")
    forecast: str | None = None
    forecast_hourly: str | None = Field(default=None, alias="forecastHourly")
    cwa: str | None = None


class PointResponse(BaseModel):
    """`/points/{lat},{lon}` GeoJSON Feature 봉투 — properties가 곧 PointProperties.

    출처: 라이브 /points (type "Feature").
    """

    model_config = {"extra": "ignore"}

    properties: PointProperties


class ForecastPeriod(BaseModel):
    """그리드 예보의 `periods[]` 한 항목(부분).

    number·name·시간(startTime/endTime ISO-8601)·isDaytime·온도(temperature/temperatureUnit)·
    바람(windSpeed/windDirection)·shortForecast·detailedForecast. 시간별 예보도 동일 스키마다.
    출처: 라이브 /gridpoints/.../forecast(+/hourly) (properties.periods[]).
    """

    model_config = {"extra": "ignore"}

    number: int | None = None
    name: str | None = None
    start_time: str | None = Field(default=None, alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    is_daytime: bool | None = Field(default=None, alias="isDaytime")
    temperature: int | None = None
    temperature_unit: str | None = Field(default=None, alias="temperatureUnit")
    wind_speed: str | None = Field(default=None, alias="windSpeed")
    wind_direction: str | None = Field(default=None, alias="windDirection")
    short_forecast: str | None = Field(default=None, alias="shortForecast")
    detailed_forecast: str | None = Field(default=None, alias="detailedForecast")


class ForecastProperties(BaseModel):
    """그리드 예보 응답의 `properties`(periods 포함, 부분).

    출처: 라이브 /gridpoints/.../forecast (properties: generatedAt·updateTime·periods[]).
    """

    model_config = {"extra": "ignore"}

    updated: str | None = Field(default=None, alias="updateTime")
    generated_at: str | None = Field(default=None, alias="generatedAt")
    periods: list[ForecastPeriod] = []


class ForecastResponse(BaseModel):
    """그리드 예보 GeoJSON Feature 봉투 — properties가 곧 ForecastProperties.

    출처: 라이브 /gridpoints/.../forecast (type "Feature").
    """

    model_config = {"extra": "ignore"}

    properties: ForecastProperties


class AlertProperties(BaseModel):
    """활성 특보 Feature의 `properties`(부분).

    event(특보명)·severity·urgency·certainty·areaDesc(영향 지역)·headline·effective/expires(시각)·
    description·instruction·senderName. CAP 기반 필드들로, 출력엔 핵심만 쓴다.
    출처: 라이브 /alerts/active (features[].properties).
    """

    model_config = {"extra": "ignore"}

    event: str | None = None
    severity: str | None = None
    urgency: str | None = None
    certainty: str | None = None
    area_desc: str | None = Field(default=None, alias="areaDesc")
    headline: str | None = None
    effective: str | None = None
    expires: str | None = None
    description: str | None = None
    instruction: str | None = None
    sender_name: str | None = Field(default=None, alias="senderName")


class AlertFeature(BaseModel):
    """활성 특보 FeatureCollection의 한 Feature — properties가 곧 AlertProperties.

    출처: 라이브 /alerts/active (features[]).
    """

    model_config = {"extra": "ignore"}

    properties: AlertProperties


class AlertsResponse(BaseModel):
    """`/alerts/active` GeoJSON FeatureCollection 봉투(부분).

    type "FeatureCollection" + features[] + title("Current watches, warnings, and advisories
    for <state>") + updated. 활성 특보가 없으면 features는 빈 배열.
    출처: 라이브 /alerts/active?area={ST} (type "FeatureCollection").
    """

    model_config = {"extra": "ignore"}

    title: str | None = None
    updated: str | None = None
    features: list[AlertFeature] = []


class ProblemResponse(BaseModel):
    """NWS 에러 봉투(RFC 7807 problem+json, 부분).

    라이브: 미국 밖 좌표 → 404 `{type:"...problems/InvalidPoint", title:"Data Unavailable For
    Requested Point", status:404, detail:"Unable to provide data for requested point ..."}`.
    잘못된 area → 400 `{type:"...problems/BadRequest", title:"Bad Request", parameterErrors:[...]}`.
    출처: 라이브 (/points/<해외>, /alerts/active?area=<bad>).
    """

    model_config = {"extra": "ignore"}

    type: str | None = None
    title: str | None = None
    status: int | None = None
    detail: str | None = None
