"""NWS 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수(base·기본 User-Agent)·경로 빌더(points·gridpoint forecast/hourly·alerts)·
좌표/주코드 검증·GeoJSON 응답 모델 파싱(Feature/FeatureCollection·alias·에러 봉투).
HTTP 호출은 일절 하지 않는다.
"""

import pytest

from arcsolve.services.nws.contract import (
    ALERTS_ACTIVE,
    BASE_URL,
    DEFAULT_USER_AGENT,
    VALID_STATE_AREAS,
    AlertsResponse,
    ForecastPeriod,
    ForecastResponse,
    PointResponse,
    ProblemResponse,
    gridpoint_forecast_path,
    points_path,
    validate_area,
    validate_latitude,
    validate_longitude,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert BASE_URL == "https://api.weather.gov"
    assert ALERTS_ACTIVE == "/alerts/active"
    assert "ArcSolve-MCP" in DEFAULT_USER_AGENT
    assert "ArcSolver/ArcSolve-MCP" in DEFAULT_USER_AGENT


def test_valid_state_areas_cover_states_and_territories():
    # 50개 주 + DC + 8개 속령/자유연합 = 59.
    assert len(VALID_STATE_AREAS) == 59
    for code in ("CA", "TX", "NY", "FL", "DC", "PR", "GU", "VI", "AS", "MP"):
        assert code in VALID_STATE_AREAS
    assert "ZZ" not in VALID_STATE_AREAS


# ─── 경로 빌더 ──────────────────────────────────────────────


def test_points_path():
    assert points_path(38.8894, -77.0352) == "/points/38.8894,-77.0352"


def test_gridpoint_forecast_path():
    assert gridpoint_forecast_path("TOP", 32, 81) == "/gridpoints/TOP/32,81/forecast"
    assert (
        gridpoint_forecast_path("TOP", 32, 81, hourly=True)
        == "/gridpoints/TOP/32,81/forecast/hourly"
    )


# ─── 좌표 / 주코드 검증 ─────────────────────────────────────


def test_validate_latitude_bounds():
    assert validate_latitude(38.0) == 38.0
    assert validate_latitude(-90.0) == -90.0
    assert validate_latitude(90.0) == 90.0
    with pytest.raises(ValueError):
        validate_latitude(90.1)
    with pytest.raises(ValueError):
        validate_latitude(-91.0)


def test_validate_longitude_bounds():
    assert validate_longitude(-77.0) == -77.0
    assert validate_longitude(180.0) == 180.0
    with pytest.raises(ValueError):
        validate_longitude(180.1)
    with pytest.raises(ValueError):
        validate_longitude(-181.0)


def test_validate_area_normalizes_and_validates():
    assert validate_area("ca") == "CA"  # 소문자 → 대문자
    assert validate_area("  TX ") == "TX"  # 공백 정리
    with pytest.raises(ValueError):
        validate_area("ZZ")
    with pytest.raises(ValueError):
        validate_area("California")  # 풀네임 아님


# ─── 응답 모델 (alias / GeoJSON) ───────────────────────────


def test_point_response_aliases():
    body = {
        "type": "Feature",
        "properties": {
            "cwa": "TOP",
            "gridId": "TOP",
            "gridX": 32,
            "gridY": 81,
            "forecast": "https://api.weather.gov:80/gridpoints/TOP/32,81/forecast",
            "forecastHourly": "https://api.weather.gov:80/gridpoints/TOP/32,81/forecast/hourly",
            "extra": "ignored",
        },
    }
    p = PointResponse.model_validate(body).properties
    assert p.grid_id == "TOP"  # gridId alias
    assert p.grid_x == 32 and p.grid_y == 81
    assert p.cwa == "TOP"
    assert p.forecast_hourly.endswith("/forecast/hourly")  # forecastHourly alias


def test_forecast_period_aliases():
    period = ForecastPeriod.model_validate(
        {
            "number": 1,
            "name": "Today",
            "startTime": "2026-06-03T07:00:00-05:00",
            "endTime": "2026-06-03T18:00:00-05:00",
            "isDaytime": True,
            "temperature": 80,
            "temperatureUnit": "F",
            "windSpeed": "5 to 15 mph",
            "windDirection": "SE",
            "shortForecast": "Chance Showers And Thunderstorms",
            "detailedForecast": "A chance of showers ...",
            "extra": "ignored",
        }
    )
    assert period.name == "Today"
    assert period.start_time.startswith("2026-06-03")  # startTime alias
    assert period.is_daytime is True  # isDaytime alias
    assert period.temperature == 80 and period.temperature_unit == "F"
    assert period.wind_speed == "5 to 15 mph"  # windSpeed alias
    assert period.short_forecast.startswith("Chance")  # shortForecast alias


def test_forecast_response_envelope():
    body = {
        "type": "Feature",
        "properties": {
            "updateTime": "2026-06-03T11:00:00+00:00",
            "generatedAt": "2026-06-03T12:00:00+00:00",
            "periods": [
                {"number": 1, "name": "Today", "temperature": 80, "temperatureUnit": "F"},
                {"number": 2, "name": "Tonight", "temperature": 62, "temperatureUnit": "F"},
            ],
        },
    }
    fc = ForecastResponse.model_validate(body).properties
    assert fc.updated == "2026-06-03T11:00:00+00:00"  # updateTime alias
    assert len(fc.periods) == 2
    assert fc.periods[0].name == "Today"


def test_alerts_response_feature_collection():
    body = {
        "type": "FeatureCollection",
        "title": "Current watches, warnings, and advisories for Texas",
        "updated": "2026-06-03T12:00:00+00:00",
        "features": [
            {
                "properties": {
                    "event": "Flash Flood Warning",
                    "severity": "Severe",
                    "urgency": "Immediate",
                    "areaDesc": "Crane, TX; Pecos, TX",
                    "headline": "Flash Flood Warning issued ...",
                    "effective": "2026-06-03T06:40:00-05:00",
                    "expires": "2026-06-03T08:45:00-05:00",
                    "senderName": "NWS Midland TX",
                }
            }
        ],
    }
    r = AlertsResponse.model_validate(body)
    assert "Texas" in r.title
    assert len(r.features) == 1
    p = r.features[0].properties
    assert p.event == "Flash Flood Warning"
    assert p.severity == "Severe"
    assert p.area_desc == "Crane, TX; Pecos, TX"  # areaDesc alias
    assert p.sender_name == "NWS Midland TX"  # senderName alias


def test_alerts_response_empty_features():
    body = {
        "type": "FeatureCollection",
        "title": "Current watches, warnings, and advisories for Kansas",
        "features": [],
    }
    r = AlertsResponse.model_validate(body)
    assert r.features == []


def test_problem_response_invalid_point():
    body = {
        "correlationId": "abc",
        "title": "Data Unavailable For Requested Point",
        "type": "https://api.weather.gov/problems/InvalidPoint",
        "status": 404,
        "detail": "Unable to provide data for requested point 51.5,-0.12",
        "instance": "https://api.weather.gov/requests/abc",
    }
    p = ProblemResponse.model_validate(body)
    assert p.status == 404
    assert p.title == "Data Unavailable For Requested Point"
    assert "InvalidPoint" in p.type
