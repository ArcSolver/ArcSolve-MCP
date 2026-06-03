"""USGS quake 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수·limit/orderby/radius 검증·build_params(format 고정·None 생략)·
GeoJSON 응답 모델 파싱(FeatureCollection/Feature/properties/geometry/count). HTTP 호출 없음.
"""

import pytest

from arcsolve.services.usgs_quake.contract import (
    BASE_URL,
    COUNT,
    DEFAULT_LIMIT,
    FORMAT_GEOJSON,
    MAX_LIMIT,
    MAX_RADIUS_KM,
    MIN_LIMIT,
    QUERY,
    VALID_ORDERBY,
    CountResult,
    Feature,
    FeatureCollection,
    build_params,
    validate_limit,
    validate_orderby,
    validate_radius,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert BASE_URL == "https://earthquake.usgs.gov/fdsnws/event/1"
    assert QUERY == "/query"
    assert COUNT == "/count"
    assert FORMAT_GEOJSON == "geojson"
    assert DEFAULT_LIMIT == 20
    assert MIN_LIMIT == 1
    assert MAX_LIMIT == 20000
    assert MAX_RADIUS_KM == 20001.6
    assert VALID_ORDERBY == ("time", "time-asc", "magnitude", "magnitude-asc")


# ─── limit / orderby / radius 검증 ─────────────────────────


def test_validate_limit_bounds():
    assert validate_limit(MIN_LIMIT) == 1
    assert validate_limit(MAX_LIMIT) == 20000
    with pytest.raises(ValueError):
        validate_limit(0)
    with pytest.raises(ValueError):
        validate_limit(MAX_LIMIT + 1)


def test_validate_orderby():
    for ok in VALID_ORDERBY:
        assert validate_orderby(ok) == ok
    with pytest.raises(ValueError):
        validate_orderby("time-desc")


def test_validate_radius_ranges():
    # 정상 범위.
    validate_radius(35.0, 139.0, 500.0)
    # 위도/경도/반경 범위 위반.
    with pytest.raises(ValueError):
        validate_radius(91.0, 0.0, None)
    with pytest.raises(ValueError):
        validate_radius(0.0, 181.0, None)
    with pytest.raises(ValueError):
        validate_radius(0.0, 0.0, MAX_RADIUS_KM + 1)


def test_validate_radius_requires_center():
    # maxradiuskm는 중심점(lat+lon) 없이 단독으로 쓸 수 없다.
    with pytest.raises(ValueError):
        validate_radius(None, None, 100.0)
    with pytest.raises(ValueError):
        validate_radius(35.0, None, 100.0)


# ─── build_params ──────────────────────────────────────────


def test_build_params_always_sets_geojson_format():
    assert build_params() == {"format": "geojson"}


def test_build_params_omits_none_and_keeps_given():
    params = build_params(
        starttime="2024-01-01",
        endtime="2024-01-02",
        minmagnitude=4.5,
        limit=50,
        orderby="magnitude",
    )
    assert params["format"] == "geojson"
    assert params["starttime"] == "2024-01-01"
    assert params["endtime"] == "2024-01-02"
    assert params["minmagnitude"] == 4.5
    assert params["limit"] == 50
    assert params["orderby"] == "magnitude"
    assert "maxmagnitude" not in params
    assert "latitude" not in params


def test_build_params_circle_location():
    params = build_params(latitude=35.0, longitude=139.0, maxradiuskm=300.0)
    assert params["latitude"] == 35.0
    assert params["longitude"] == 139.0
    assert params["maxradiuskm"] == 300.0


def test_build_params_rejects_bad_limit():
    with pytest.raises(ValueError):
        build_params(limit=MAX_LIMIT + 1)


def test_build_params_rejects_bad_orderby():
    with pytest.raises(ValueError):
        build_params(orderby="size")


def test_build_params_rejects_radius_without_center():
    with pytest.raises(ValueError):
        build_params(maxradiuskm=100.0)


# ─── 응답 모델 ──────────────────────────────────────────────


def test_feature_collection_parses_full_feature():
    body = {
        "type": "FeatureCollection",
        "metadata": {"title": "USGS Earthquakes", "status": 200, "count": 1, "limit": 20},
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "mag": 5.1,
                    "place": "73 km WSW of Sado, Japan",
                    "time": 1704102326217,
                    "updated": 1710020303040,
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us6000m0yg",
                    "magType": "mb",
                    "type": "earthquake",
                    "title": "M 5.1 - 73 km WSW of Sado, Japan",
                    "status": "reviewed",
                    "tsunami": 0,
                    "sig": 400,
                    "ignored": "x",
                },
                "geometry": {"type": "Point", "coordinates": [137.5664, 37.8107, 10]},
                "id": "us6000m0yg",
            }
        ],
    }
    fc = FeatureCollection.model_validate(body)
    assert fc.type == "FeatureCollection"
    assert fc.metadata.count == 1
    assert len(fc.features) == 1
    f = fc.features[0]
    assert f.id == "us6000m0yg"
    assert f.properties.mag == 5.1
    assert f.properties.place == "73 km WSW of Sado, Japan"
    assert f.properties.time == 1704102326217  # 밀리초 epoch 그대로
    assert f.properties.magType == "mb"
    # coordinates는 [lon, lat, depth] 순서.
    assert f.geometry.coordinates == [137.5664, 37.8107, 10]


def test_feature_collection_empty_features():
    fc = FeatureCollection.model_validate(
        {"type": "FeatureCollection", "metadata": {"count": 0}, "features": []}
    )
    assert fc.features == []


def test_feature_partial_missing_geometry():
    # geometry/properties가 없어도 느슨히 받는다.
    f = Feature.model_validate({"type": "Feature", "id": "x"})
    assert f.id == "x"
    assert f.properties is None
    assert f.geometry is None


def test_count_result_parses():
    r = CountResult.model_validate({"count": 92, "maxAllowed": 20000})
    assert r.count == 92
    assert r.maxAllowed == 20000
