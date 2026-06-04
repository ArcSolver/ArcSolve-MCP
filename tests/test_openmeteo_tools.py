"""Open-Meteo 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑 확인.

get_json은 본문 dict를 돌려주므로 RecordingHTTP의 ret도 dict로 준다. 무인증이라
자격증명 누락 시나리오 대신 User-Agent 헤더 전송·범위 검증 사전 차단을 확인한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.openmeteo.tools import register

MOD = "arcsolve.services.openmeteo.tools"


@pytest.fixture
def tools(load_tools):
    return load_tools(register)


# ─── 지오코딩 ───────────────────────────────────────────────


async def test_geocode_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "results": [
            {
                "name": "Berlin",
                "latitude": 52.52437,
                "longitude": 13.41053,
                "country": "Germany",
                "admin1": "State of Berlin",
                "timezone": "Europe/Berlin",
            }
        ],
        "generationtime_ms": 0.34,
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["openmeteo_geocode"](name="Berlin", count=5, language="en")
    assert http.last["url"] == "https://geocoding-api.open-meteo.com/v1/search"
    assert http.last["params"]["name"] == "Berlin"
    assert http.last["params"]["count"] == 5
    assert http.last["params"]["language"] == "en"
    # 무인증 — 식별용 User-Agent 헤더만 전송.
    assert "arcsolve" in http.last["headers"]["User-Agent"]
    assert "Berlin" in out and "Germany" in out
    assert "52.5244" in out and "13.4105" in out
    assert "Europe/Berlin" in out


async def test_geocode_no_results_when_results_key_absent(tools, monkeypatch, recording_http):
    # 라이브: 매칭 없으면 results 키가 아예 없다.
    http = recording_http(ret={"generationtime_ms": 0.71})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openmeteo_geocode"](name="zzzznoplace")
    assert "검색 결과 없음" in out
    assert "zzzznoplace" in out


async def test_geocode_no_network_when_count_invalid(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openmeteo_geocode"](name="x", count=101)
    assert "count" in out and "100" in out  # 계약 위반은 HTTP 전에 막힘
    assert not http.calls


# ─── 예보 ───────────────────────────────────────────────────


async def test_forecast_request_assembly_passes_variables_verbatim(tools, monkeypatch, recording_http):
    body = {
        "latitude": 52.52,
        "longitude": 13.419998,
        "timezone": "Europe/Berlin",
        "elevation": 38.0,
        "current_units": {"temperature_2m": "°C"},
        "current": {"time": "2026-06-03T14:30", "interval": 900, "temperature_2m": 20.1},
        "hourly_units": {"temperature_2m": "°C", "precipitation": "mm"},
        "hourly": {
            "time": ["2026-06-03T00:00", "2026-06-03T01:00"],
            "temperature_2m": [20.4, 19.5],
            "precipitation": [0.0, 0.1],
        },
        "daily_units": {"temperature_2m_max": "°C"},
        "daily": {"time": ["2026-06-03"], "temperature_2m_max": [24.0]},
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["openmeteo_forecast"](
        latitude=52.52,
        longitude=13.41,
        hourly="temperature_2m,precipitation",
        daily="temperature_2m_max",
        current="temperature_2m",
        timezone="auto",
        forecast_days=1,
    )
    assert http.last["url"] == "https://api.open-meteo.com/v1/forecast"
    assert http.last["params"]["latitude"] == 52.52
    assert http.last["params"]["longitude"] == 13.41
    # 콤마 구분 변수 문자열은 그대로 전달.
    assert http.last["params"]["hourly"] == "temperature_2m,precipitation"
    assert http.last["params"]["daily"] == "temperature_2m_max"
    assert http.last["params"]["current"] == "temperature_2m"
    assert http.last["params"]["timezone"] == "auto"
    assert http.last["params"]["forecast_days"] == 1
    assert "arcsolve" in http.last["headers"]["User-Agent"]
    # 출력: 헤더 + current + hourly + daily.
    assert "Europe/Berlin" in out
    assert "temperature_2m = 20.1°C" in out
    assert "temperature_2m=20.4°C" in out  # hourly 첫 값
    assert "precipitation=0.0mm" in out
    assert "temperature_2m_max=24.0°C" in out  # daily


async def test_forecast_no_variables_hint(tools, monkeypatch, recording_http):
    body = {"latitude": 1.0, "longitude": 2.0, "timezone": "GMT"}
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openmeteo_forecast"](latitude=1.0, longitude=2.0)
    assert "hourly/daily/current" in out  # 안내 메시지


async def test_forecast_no_network_when_days_invalid(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openmeteo_forecast"](latitude=1.0, longitude=2.0, forecast_days=17)
    assert "forecast_days" in out and "16" in out
    assert not http.calls


# ─── 에러 매핑 ──────────────────────────────────────────────


async def test_forecast_maps_400_reason(tools, monkeypatch, recording_http):
    # 라이브: 좌표 누락 → 400 {"error":true,"reason":"..."}.
    http = recording_http(
        exc=UpstreamError(
            400,
            {"error": True, "reason": "Parameter 'latitude' and 'longitude' must have ..."},
        )
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openmeteo_forecast"](latitude=1.0, longitude=2.0, hourly="temperature_2m")
    assert "400" in out
    assert "latitude" in out  # reason 노출


async def test_geocode_maps_400(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(400, {"error": True, "reason": "bad request"}))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openmeteo_geocode"](name="x")
    assert "400" in out and "bad request" in out


async def test_maps_429_rate_limit(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(429, "Too Many Requests"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openmeteo_geocode"](name="x")
    assert "429" in out and "한도" in out


async def test_400_does_not_leak_non_json_body(tools, monkeypatch, recording_http):
    # payload가 dict가 아니면(비-JSON) 원문을 노출하지 않는다.
    http = recording_http(exc=UpstreamError(400, "Bad Request plain text"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["openmeteo_forecast"](latitude=1.0, longitude=2.0, hourly="temperature_2m")
    assert "400" in out
    assert "Bad Request plain text" not in out
