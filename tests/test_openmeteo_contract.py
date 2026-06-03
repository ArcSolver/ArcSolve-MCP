"""Open-Meteo 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수·쿼리 빌더(count/forecast_days 검증·콤마 변수 전달)·
응답 모델 파싱(예보/지오코딩 봉투·results 키 부재·current 스칼라·에러 봉투). HTTP 호출 없음.
"""

import pytest

from arcsolve.services.openmeteo.contract import (
    FORECAST,
    FORECAST_BASE_URL,
    FORECAST_DEFAULT_DAYS,
    FORECAST_MAX_DAYS,
    FORECAST_MIN_DAYS,
    GEOCODING_BASE_URL,
    GEOCODING_DEFAULT_COUNT,
    GEOCODING_MAX_COUNT,
    GEOCODING_MIN_COUNT,
    GEOCODING_SEARCH,
    ErrorResponse,
    ForecastResponse,
    GeocodingResponse,
    GeocodingResult,
    build_forecast_params,
    build_geocoding_params,
    validate_count,
    validate_forecast_days,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert FORECAST_BASE_URL == "https://api.open-meteo.com/v1"
    assert GEOCODING_BASE_URL == "https://geocoding-api.open-meteo.com/v1"
    assert FORECAST == "/forecast"
    assert GEOCODING_SEARCH == "/search"
    assert GEOCODING_DEFAULT_COUNT == 10
    assert GEOCODING_MIN_COUNT == 1
    assert GEOCODING_MAX_COUNT == 100
    assert FORECAST_DEFAULT_DAYS == 7
    assert FORECAST_MIN_DAYS == 0
    assert FORECAST_MAX_DAYS == 16


# ─── count / forecast_days 검증 ─────────────────────────────


def test_validate_count_bounds():
    assert validate_count(GEOCODING_MIN_COUNT) == 1
    assert validate_count(GEOCODING_MAX_COUNT) == 100
    with pytest.raises(ValueError):
        validate_count(0)
    with pytest.raises(ValueError):
        validate_count(GEOCODING_MAX_COUNT + 1)


def test_validate_forecast_days_bounds():
    assert validate_forecast_days(FORECAST_MIN_DAYS) == 0
    assert validate_forecast_days(FORECAST_MAX_DAYS) == 16
    with pytest.raises(ValueError):
        validate_forecast_days(-1)
    with pytest.raises(ValueError):
        validate_forecast_days(FORECAST_MAX_DAYS + 1)


# ─── build_geocoding_params ────────────────────────────────


def test_build_geocoding_params_minimal():
    assert build_geocoding_params(name="Berlin") == {"name": "Berlin"}


def test_build_geocoding_params_full():
    params = build_geocoding_params(name="Seoul", count=5, language="ko", country_code="KR")
    assert params["name"] == "Seoul"
    assert params["count"] == 5
    assert params["language"] == "ko"
    assert params["countryCode"] == "KR"  # camelCase 파라미터명


def test_build_geocoding_params_omits_empty():
    params = build_geocoding_params(name="x", language=None, country_code=None)
    assert params == {"name": "x"}


def test_build_geocoding_params_rejects_bad_count():
    with pytest.raises(ValueError):
        build_geocoding_params(name="x", count=GEOCODING_MAX_COUNT + 1)


# ─── build_forecast_params ─────────────────────────────────


def test_build_forecast_params_minimal():
    params = build_forecast_params(latitude=52.52, longitude=13.41)
    assert params == {"latitude": 52.52, "longitude": 13.41}


def test_build_forecast_params_passes_comma_separated_variables_verbatim():
    params = build_forecast_params(
        latitude=52.52,
        longitude=13.41,
        hourly="temperature_2m,precipitation",
        daily="temperature_2m_max,temperature_2m_min",
        current="temperature_2m,weather_code",
        timezone="auto",
        forecast_days=3,
    )
    # 변수 문자열은 그대로 전달(가공 없음).
    assert params["hourly"] == "temperature_2m,precipitation"
    assert params["daily"] == "temperature_2m_max,temperature_2m_min"
    assert params["current"] == "temperature_2m,weather_code"
    assert params["timezone"] == "auto"
    assert params["forecast_days"] == 3


def test_build_forecast_params_omits_empty():
    params = build_forecast_params(latitude=1.0, longitude=2.0, hourly=None, daily="")
    assert "hourly" not in params
    assert "daily" not in params


def test_build_forecast_params_rejects_bad_forecast_days():
    with pytest.raises(ValueError):
        build_forecast_params(latitude=1.0, longitude=2.0, forecast_days=FORECAST_MAX_DAYS + 1)


# ─── 응답 모델 ─────────────────────────────────────────────


def test_geocoding_result_partial_fields():
    r = GeocodingResult.model_validate(
        {
            "id": 2950159,
            "name": "Berlin",
            "latitude": 52.52437,
            "longitude": 13.41053,
            "elevation": 74.0,
            "timezone": "Europe/Berlin",
            "feature_code": "PPLC",
            "country_code": "DE",
            "country": "Germany",
            "population": 3426354,
            "admin1": "State of Berlin",
            "unexpected": "ignored",
        }
    )
    assert r.name == "Berlin"
    assert r.latitude == 52.52437
    assert r.country == "Germany"
    assert r.timezone == "Europe/Berlin"
    assert r.admin1 == "State of Berlin"


def test_geocoding_response_with_results():
    body = {
        "results": [
            {"name": "Berlin", "latitude": 52.5, "longitude": 13.4, "country": "Germany"},
            {"name": "Berlin", "latitude": 44.4, "longitude": -71.1, "country": "United States"},
        ],
        "generationtime_ms": 0.34,
    }
    r = GeocodingResponse.model_validate(body)
    assert len(r.results) == 2
    assert r.results[0].name == "Berlin"
    assert r.results[1].country == "United States"


def test_geocoding_response_missing_results_key_defaults_empty():
    # 라이브: 매칭 없으면 results 키 자체가 없다(빈 배열 아님).
    r = GeocodingResponse.model_validate({"generationtime_ms": 0.71})
    assert r.results == []


def test_forecast_response_top_level_and_dynamic_blocks():
    body = {
        "latitude": 52.52,
        "longitude": 13.419998,
        "elevation": 38.0,
        "generationtime_ms": 0.09,
        "utc_offset_seconds": 7200,
        "timezone": "Europe/Berlin",
        "timezone_abbreviation": "GMT+2",
        "current_units": {"time": "iso8601", "interval": "seconds", "temperature_2m": "°C"},
        "current": {"time": "2026-06-03T14:30", "interval": 900, "temperature_2m": 20.1},
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C", "precipitation": "mm"},
        "hourly": {
            "time": ["2026-06-03T00:00", "2026-06-03T01:00"],
            "temperature_2m": [20.4, 19.5],
            "precipitation": [0.0, 0.1],
        },
        "daily_units": {"time": "iso8601", "temperature_2m_max": "°C"},
        "daily": {"time": ["2026-06-03"], "temperature_2m_max": [24.0]},
        "ignored_extra": 1,
    }
    r = ForecastResponse.model_validate(body)
    assert r.latitude == 52.52
    assert r.timezone == "Europe/Berlin"
    assert r.elevation == 38.0
    # 동적 변수 블록은 dict로 받는다.
    assert r.current["temperature_2m"] == 20.1
    assert r.hourly["temperature_2m"] == [20.4, 19.5]
    assert r.hourly_units["precipitation"] == "mm"
    assert r.daily["temperature_2m_max"] == [24.0]


def test_error_response_envelope():
    e = ErrorResponse.model_validate(
        {"error": True, "reason": "Parameter 'latitude' and 'longitude' must have the same number"}
    )
    assert e.error is True
    assert "latitude" in e.reason
