"""USGS quake 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑 확인.

get_json은 본문 dict를 돌려주므로 RecordingHTTP의 ret도 dict로 준다.
format=geojson이 항상 들어가고, 계약 위반(limit/orderby/위치)은 HTTP 전에 막히는지 확인한다.
USGS 에러 본문은 text/plain이므로 _explain이 첫 의미 줄만 노출하는지도 검증한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.usgs_quake.tools import register

MOD = "arcsolve.services.usgs_quake.tools"


@pytest.fixture
def tools(load_tools):
    return load_tools(register)


# ─── 검색 ───────────────────────────────────────────────────


async def test_search_request_and_output(tools, monkeypatch, recording_http):
    body = {
        "type": "FeatureCollection",
        "metadata": {"count": 1},
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "mag": 5.1,
                    "place": "73 km WSW of Sado, Japan",
                    "time": 1704102326217,
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us6000m0yg",
                },
                "geometry": {"type": "Point", "coordinates": [137.5664, 37.8107, 10]},
                "id": "us6000m0yg",
            }
        ],
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["usgs_search_earthquakes"](
        starttime="2024-01-01", minmagnitude=5, orderby="magnitude"
    )
    assert http.last["url"] == "https://earthquake.usgs.gov/fdsnws/event/1/query"
    # format은 항상 geojson.
    assert http.last["params"]["format"] == "geojson"
    assert http.last["params"]["starttime"] == "2024-01-01"
    assert http.last["params"]["minmagnitude"] == 5
    assert http.last["params"]["limit"] == 20  # 기본
    assert http.last["params"]["orderby"] == "magnitude"
    # User-Agent 식별 헤더.
    assert "arcsolve" in http.last["headers"]["User-Agent"]
    # 출력: 규모·위치·이벤트 URL.
    assert "1건" in out
    assert "M5.1" in out
    assert "Sado, Japan" in out
    assert "us6000m0yg" in out
    # time(ms epoch)이 UTC ISO8601로 변환된다.
    assert "2024-01-01T09:45:26Z" in out
    # 좌표는 사람용으로 위도, 경도 (depth) 재배열.
    assert "37.8107, 137.5664" in out
    assert "depth 10.0 km" in out


async def test_search_circle_location_params(tools, monkeypatch, recording_http):
    http = recording_http(ret={"type": "FeatureCollection", "features": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["usgs_search_earthquakes"](
        latitude=35.0, longitude=139.0, maxradiuskm=300.0
    )
    assert http.last["params"]["latitude"] == 35.0
    assert http.last["params"]["longitude"] == 139.0
    assert http.last["params"]["maxradiuskm"] == 300.0
    assert "검색 결과 없음" in out


async def test_search_empty_features(tools, monkeypatch, recording_http):
    http = recording_http(ret={"type": "FeatureCollection", "metadata": {"count": 0}, "features": []})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["usgs_search_earthquakes"](minmagnitude=9.9)
    assert "검색 결과 없음" in out


async def test_search_no_network_when_limit_invalid(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["usgs_search_earthquakes"](limit=20001)
    assert "limit" in out and "20000" in out
    assert not http.calls  # 계약 위반은 HTTP 전에 막힘


async def test_search_no_network_when_orderby_invalid(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["usgs_search_earthquakes"](orderby="time-desc")
    assert "orderby" in out
    assert not http.calls


async def test_search_no_network_when_radius_without_center(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["usgs_search_earthquakes"](maxradiuskm=100.0)
    assert "maxradiuskm" in out
    assert not http.calls


# ─── 건수 ───────────────────────────────────────────────────


async def test_count_request_and_output(tools, monkeypatch, recording_http):
    http = recording_http(ret={"count": 92, "maxAllowed": 20000})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["usgs_count_earthquakes"](
        starttime="2024-01-01", endtime="2024-01-02", minmagnitude=4
    )
    assert http.last["url"] == "https://earthquake.usgs.gov/fdsnws/event/1/count"
    assert http.last["params"]["format"] == "geojson"
    assert http.last["params"]["minmagnitude"] == 4
    assert "92건" in out


async def test_count_no_network_when_radius_without_center(tools, monkeypatch, recording_http):
    http = recording_http(ret={})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["usgs_count_earthquakes"](maxradiuskm=100.0)
    assert "maxradiuskm" in out
    assert not http.calls


# ─── 에러 매핑 ──────────────────────────────────────────────


async def test_maps_400_text_plain_first_meaningful_line(tools, monkeypatch, recording_http):
    # 라이브: 400 본문은 text/plain — 'Error 400: Bad Request' 다음 첫 의미 줄만 노출.
    payload = (
        'Error 400: Bad Request\n\n'
        'Bad limit value "20001". Valid values are 0 <= limit <= 20000\n\n'
        'Usage details are available from https://earthquake.usgs.gov/fdsnws/event/1\n'
    )
    http = recording_http(exc=UpstreamError(400, payload))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["usgs_search_earthquakes"](starttime="bad")
    assert "400" in out
    assert "Bad limit value" in out  # 첫 의미 줄 노출
    assert "Usage details" not in out  # 푸터는 잘림


async def test_maps_204_nodata_as_empty(tools, monkeypatch, recording_http):
    # nodata 기본 204(비-geojson 경로) → 빈 결과 안내로 매핑.
    http = recording_http(exc=UpstreamError(204, ""))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["usgs_count_earthquakes"](minmagnitude=9.9)
    assert "없습니다" in out


async def test_maps_503_service_unavailable(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(503, "Service Unavailable"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["usgs_search_earthquakes"](minmagnitude=4)
    assert "503" in out
