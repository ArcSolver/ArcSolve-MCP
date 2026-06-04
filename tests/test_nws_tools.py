"""NWS 도구 런타임 검증 — 네트워크 없이 요청 조립·2단계 조회·응답 파싱·에러 매핑 확인.

get_json은 본문 dict를 돌려준다. nws_forecast/nws_hourly_forecast는 **2단계**(/points →
/gridpoints) 호출이라, 호출 순서대로 다른 본문을 돌려주는 SequencedHTTP를 쓴다. User-Agent 헤더가
항상 실리는지(필수), 미국 밖 좌표(InvalidPoint 404)가 안내로 매핑되는지 확인한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.nws.tools import register

MOD = "arcsolve.services.nws.tools"


class SequencedHTTP:
    """호출마다 미리 정한 응답(dict)을 순서대로 돌려주는 get_json 대역.

    리스트의 한 항목이 Exception이면 그 호출에서 raise한다(2단계 중 특정 단계 실패 모사).
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        item = self.responses[len(self.calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def last(self):
        assert self.calls, "get_json이 호출되지 않았습니다."
        return self.calls[-1]


POINT_BODY = {
    "type": "Feature",
    "properties": {
        "cwa": "TOP",
        "gridId": "TOP",
        "gridX": 32,
        "gridY": 81,
        "forecast": "https://api.weather.gov:80/gridpoints/TOP/32,81/forecast",
        "forecastHourly": "https://api.weather.gov:80/gridpoints/TOP/32,81/forecast/hourly",
    },
}

FORECAST_BODY = {
    "type": "Feature",
    "properties": {
        "updateTime": "2026-06-03T11:00:00+00:00",
        "periods": [
            {
                "number": 1,
                "name": "Today",
                "temperature": 80,
                "temperatureUnit": "F",
                "windSpeed": "5 to 15 mph",
                "windDirection": "SE",
                "shortForecast": "Chance Showers And Thunderstorms",
            },
            {
                "number": 2,
                "name": "Tonight",
                "temperature": 62,
                "temperatureUnit": "F",
                "windSpeed": "5 mph",
                "windDirection": "S",
                "shortForecast": "Mostly Cloudy",
            },
        ],
    },
}


@pytest.fixture
def tools(monkeypatch, load_tools):
    """기본 환경(무인증·기본 User-Agent)."""
    monkeypatch.delenv("NWS_USER_AGENT", raising=False)
    return load_tools(register)


# ─── 예보: 2단계 조회 ───────────────────────────────────────


async def test_forecast_two_step_request_and_output(tools, monkeypatch):
    http = SequencedHTTP([POINT_BODY, FORECAST_BODY])
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["nws_forecast"](latitude=39.7456, longitude=-97.0892)

    # 1단계: /points/{lat},{lon}
    assert http.calls[0]["url"] == "https://api.weather.gov/points/39.7456,-97.0892"
    # 2단계: gridId·gridX·gridY로 재조립한 /gridpoints 경로(응답의 :80 URL을 쓰지 않음)
    assert http.calls[1]["url"] == "https://api.weather.gov/gridpoints/TOP/32,81/forecast"
    assert ":80" not in http.calls[1]["url"]
    # User-Agent는 두 호출 모두에 실린다(필수).
    assert "User-Agent" in http.calls[0]["headers"]
    assert "User-Agent" in http.calls[1]["headers"]
    # 출력에 기간별 온도·바람·요약.
    assert "Today" in out and "80°F" in out and "Chance Showers" in out
    assert "Tonight" in out and "62°F" in out


async def test_hourly_forecast_uses_hourly_path(tools, monkeypatch):
    http = SequencedHTTP([POINT_BODY, FORECAST_BODY])
    monkeypatch.setattr(f"{MOD}.get_json", http)

    await tools["nws_hourly_forecast"](latitude=39.7456, longitude=-97.0892)
    assert http.calls[1]["url"] == "https://api.weather.gov/gridpoints/TOP/32,81/forecast/hourly"


async def test_default_user_agent_present(tools, monkeypatch):
    http = SequencedHTTP([POINT_BODY, FORECAST_BODY])
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["nws_forecast"](latitude=39.7, longitude=-97.0)
    ua = http.calls[0]["headers"]["User-Agent"]
    assert "arcsolve" in ua


async def test_user_agent_override_from_env(monkeypatch, load_tools):
    monkeypatch.setenv("NWS_USER_AGENT", "(myapp.com, me@example.com)")
    tools = load_tools(register)
    http = SequencedHTTP([POINT_BODY, FORECAST_BODY])
    monkeypatch.setattr(f"{MOD}.get_json", http)
    await tools["nws_forecast"](latitude=39.7, longitude=-97.0)
    assert http.calls[0]["headers"]["User-Agent"] == "(myapp.com, me@example.com)"


async def test_forecast_invalid_lat_no_network(tools, monkeypatch):
    http = SequencedHTTP([POINT_BODY, FORECAST_BODY])
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["nws_forecast"](latitude=99.0, longitude=-97.0)
    assert "latitude" in out
    assert not http.calls  # 좌표 검증은 HTTP 전에 막힘


async def test_forecast_non_us_point_maps_to_friendly_404(tools, monkeypatch):
    # 1단계 /points에서 미국 밖 좌표 → 404 InvalidPoint.
    err = UpstreamError(
        404,
        {
            "title": "Data Unavailable For Requested Point",
            "type": "https://api.weather.gov/problems/InvalidPoint",
            "status": 404,
            "detail": "Unable to provide data for requested point 51.5,-0.12",
        },
    )
    http = SequencedHTTP([err])
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["nws_forecast"](latitude=51.5, longitude=-0.12)
    assert "404" in out and "미국" in out
    assert len(http.calls) == 1  # 2단계로 진행하지 않음


async def test_forecast_grid_step_error_mapped(tools, monkeypatch):
    # 1단계는 성공, 2단계 /gridpoints에서 500.
    http = SequencedHTTP([POINT_BODY, UpstreamError(500, {"detail": "boom"})])
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["nws_forecast"](latitude=39.7, longitude=-97.0)
    assert "500" in out
    assert len(http.calls) == 2


# ─── 특보 ───────────────────────────────────────────────────


async def test_alerts_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "type": "FeatureCollection",
        "title": "Current watches, warnings, and advisories for Texas",
        "features": [
            {
                "properties": {
                    "event": "Flash Flood Warning",
                    "severity": "Severe",
                    "areaDesc": "Crane, TX; Pecos, TX",
                    "expires": "2026-06-03T08:45:00-05:00",
                }
            }
        ],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["nws_alerts"](area="tx")  # 소문자도 정규화
    assert http.last["url"] == "https://api.weather.gov/alerts/active"
    assert http.last["params"]["area"] == "TX"  # 대문자 정규화
    assert "User-Agent" in http.last["headers"]
    assert "활성 특보 1건" in out
    assert "Flash Flood Warning" in out and "Severe" in out
    assert "Crane, TX" in out


async def test_alerts_empty(tools, monkeypatch, recording_http):
    body = {
        "type": "FeatureCollection",
        "title": "Current watches, warnings, and advisories for Kansas",
        "features": [],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["nws_alerts"](area="KS")
    assert "활성 기상특보가 없습니다" in out


async def test_alerts_invalid_area_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["nws_alerts"](area="ZZ")
    assert "area" in out
    assert not http.calls  # 잘못된 코드는 HTTP 전에 막힘


async def test_alerts_maps_400(tools, monkeypatch, recording_http):
    # 검증을 통과한 코드라도 상류가 400을 줄 수 있다(방어적).
    http = recording_http(
        exc=UpstreamError(400, {"title": "Bad Request", "detail": "Bad Request"})
    )
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["nws_alerts"](area="CA")
    assert "400" in out


async def test_alerts_maps_403_user_agent(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(403, "Forbidden"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["nws_alerts"](area="CA")
    assert "403" in out and "User-Agent" in out
