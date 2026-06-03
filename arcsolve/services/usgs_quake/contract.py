"""USGS FDSN Event Web Service 지진 정보 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 쿼리 제약/빌더, GeoJSON 응답 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·읽기. **무인증**(키 없음). 응답은 `format=geojson`으로 고정한다 →
검색은 GeoJSON FeatureCollection, 건수는 `{count, maxAllowed}` JSON이라 코어 `get_json`만으로 충분하다.

출처(공식 문서 — earthquake.usgs.gov, WebFetch + 라이브 응답 확인 2026-06-03):
  - FDSN Event API 명세(엔드포인트·전체 쿼리 파라미터·기본/제약·orderby·format·시간형식·에러):
    https://earthquake.usgs.gov/fdsnws/event/1/
  - 실시간 피드(GeoJSON) 안내(properties 필드 의미 — mag/place/time/url 등):
    https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
  - 라이브 응답 확인:
    /query?format=geojson (FeatureCollection{metadata,features[]}) ·
    /count?format=geojson ({"count":N,"maxAllowed":20000})
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처: FDSN Event API 명세
#   base "https://earthquake.usgs.gov/fdsnws/event/1/"
#   methods "/query"(데이터 요청) · "/count"(건수)
BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1"
QUERY = "/query"
COUNT = "/count"

# 응답 포맷은 geojson으로 고정한다(QuakeML/CSV/KML/text는 범위 밖).
# 출처: 명세 format 값 "csv, geojson, kml, quakeml, text, xml" → geojson만 사용.
FORMAT_GEOJSON = "geojson"

# ─── 쿼리 파라미터 제약(공식) ───────────────────────────────
# limit: "The service limits queries to 20000, and any that exceed this limit will
#         generate a HTTP response code '400 Bad Request'." 범위 [1, 20000].
# 출처: 명세 Results 파라미터 + 라이브(limit=20001 → 400 'Bad limit value ... 0 <= limit <= 20000').
DEFAULT_LIMIT = 20
MIN_LIMIT = 1
MAX_LIMIT = 20000

# orderby 허용값(공식). 출처: 명세
#   time(내림차순 시간) · time-asc · magnitude(내림차순 규모) · magnitude-asc
ORDERBY_TIME = "time"
ORDERBY_TIME_ASC = "time-asc"
ORDERBY_MAGNITUDE = "magnitude"
ORDERBY_MAGNITUDE_ASC = "magnitude-asc"
VALID_ORDERBY = (ORDERBY_TIME, ORDERBY_TIME_ASC, ORDERBY_MAGNITUDE, ORDERBY_MAGNITUDE_ASC)

# 위치(원형) 검색 제약(공식). 출처: 명세 Circle 파라미터
#   latitude [-90,90] · longitude [-180,180] · maxradiuskm [0, 20001.6]
MAX_RADIUS_KM = 20001.6

# 공식 쿼리 파라미터명(정확한 철자). 출처: 명세 파라미터 표
PARAM_FORMAT = "format"
PARAM_STARTTIME = "starttime"
PARAM_ENDTIME = "endtime"
PARAM_MINMAGNITUDE = "minmagnitude"
PARAM_MAXMAGNITUDE = "maxmagnitude"
PARAM_LATITUDE = "latitude"
PARAM_LONGITUDE = "longitude"
PARAM_MAXRADIUSKM = "maxradiuskm"
PARAM_LIMIT = "limit"
PARAM_ORDERBY = "orderby"


def validate_limit(limit: int) -> int:
    """limit를 1..20000 범위로 검증한다(공식 제약).

    위반 시 ValueError(상류가 400 'Bad limit value "N". Valid values are 0 <= limit <= 20000'을
    주기 전에 미리 막는다 — 라이브 확인).
    출처: 명세 Results limit ([1, 20000]; max 20000) + 라이브(limit=20001 → 400).
    """
    if limit < MIN_LIMIT or limit > MAX_LIMIT:
        raise ValueError(f"limit는 {MIN_LIMIT}..{MAX_LIMIT} 범위여야 합니다(현재 {limit}).")
    return limit


def validate_orderby(orderby: str) -> str:
    """orderby를 공식 4종으로 검증한다. 출처: 명세(time/time-asc/magnitude/magnitude-asc)."""
    if orderby not in VALID_ORDERBY:
        raise ValueError(f"orderby는 {VALID_ORDERBY} 중 하나여야 합니다(현재 {orderby!r}).")
    return orderby


def validate_radius(
    latitude: float | None, longitude: float | None, maxradiuskm: float | None
) -> None:
    """원형 위치 검색 제약을 검증한다(공식).

    - latitude [-90,90] · longitude [-180,180] · maxradiuskm [0, 20001.6]
    - maxradiuskm를 줄 때는 중심점(latitude+longitude)이 함께 있어야 의미가 있다(공식 Circle 파라미터).
    위반 시 ValueError(HTTP 전에 차단).
    출처: 명세 Circle 파라미터 표.
    """
    if latitude is not None and not (-90 <= latitude <= 90):
        raise ValueError(f"latitude는 -90..90 범위여야 합니다(현재 {latitude}).")
    if longitude is not None and not (-180 <= longitude <= 180):
        raise ValueError(f"longitude는 -180..180 범위여야 합니다(현재 {longitude}).")
    if maxradiuskm is not None:
        if not (0 <= maxradiuskm <= MAX_RADIUS_KM):
            raise ValueError(f"maxradiuskm는 0..{MAX_RADIUS_KM} 범위여야 합니다(현재 {maxradiuskm}).")
        if latitude is None or longitude is None:
            raise ValueError("maxradiuskm를 쓰려면 latitude와 longitude(중심점)가 함께 필요합니다.")


def build_params(
    *,
    starttime: str | None = None,
    endtime: str | None = None,
    minmagnitude: float | None = None,
    maxmagnitude: float | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    maxradiuskm: float | None = None,
    limit: int | None = None,
    orderby: str | None = None,
) -> dict[str, str | int | float]:
    """검색/건수 쿼리스트링을 만든다(format=geojson 고정). None/빈값은 생략한다.

    - starttime/endtime → ISO8601 문자열 그대로(검증은 상류에 위임 — 형식이 다양함)
    - minmagnitude/maxmagnitude → 규모 하한/상한
    - latitude+longitude+maxradiuskm → 원형 위치 검색(셋이 한 묶음, validate_radius로 검증)
    - limit → 1..20000 검증
    - orderby → time/time-asc/magnitude/magnitude-asc 검증
    출처: 명세 파라미터 표(starttime·endtime·minmagnitude·maxmagnitude·latitude·longitude·
    maxradiuskm·limit·orderby) + format geojson 고정.
    """
    validate_radius(latitude, longitude, maxradiuskm)
    params: dict[str, str | int | float] = {PARAM_FORMAT: FORMAT_GEOJSON}
    if starttime:
        params[PARAM_STARTTIME] = starttime
    if endtime:
        params[PARAM_ENDTIME] = endtime
    if minmagnitude is not None:
        params[PARAM_MINMAGNITUDE] = minmagnitude
    if maxmagnitude is not None:
        params[PARAM_MAXMAGNITUDE] = maxmagnitude
    if latitude is not None:
        params[PARAM_LATITUDE] = latitude
    if longitude is not None:
        params[PARAM_LONGITUDE] = longitude
    if maxradiuskm is not None:
        params[PARAM_MAXRADIUSKM] = maxradiuskm
    if limit is not None:
        params[PARAM_LIMIT] = validate_limit(limit)
    if orderby is not None:
        params[PARAM_ORDERBY] = validate_orderby(orderby)
    return params


# ─── 응답 모델 ──────────────────────────────────────────────
# /query?format=geojson → GeoJSON FeatureCollection:
#   {"type":"FeatureCollection","metadata":{...},"features":[{type,properties,geometry,id},...]}
# /count?format=geojson → {"count": N, "maxAllowed": 20000}
# extra="ignore"로 느슨히 받고(부분 모델), 확신하는 필드만 모델링한다.
# 출처: 라이브(/query·/count, format=geojson) + GeoJSON 피드 안내(properties 의미).


class FeatureProperties(BaseModel):
    """Feature의 properties(부분).

    공식 GeoJSON 피드 필드: mag(규모, Decimal) · place(위치 설명, String) ·
    time(발생 시각, **밀리초 epoch** Long) · updated(갱신 시각, ms epoch) ·
    url(이벤트 페이지 URL) · magType(규모 종류) · type(이벤트 종류, 보통 "earthquake") ·
    title(예: "M 5.1 - ...") · status(reviewed/automatic) · tsunami(0/1) · sig(유의도).
    출처: GeoJSON 피드 안내 + 라이브(/query features[].properties).
    """

    model_config = {"extra": "ignore"}

    mag: float | None = None
    place: str | None = None
    time: int | None = None  # 밀리초 epoch
    updated: int | None = None  # 밀리초 epoch
    url: str | None = None
    detail: str | None = None
    status: str | None = None
    tsunami: int | None = None
    sig: int | None = None
    magType: str | None = None  # noqa: N815 (공식 필드명 그대로)
    type: str | None = None
    title: str | None = None


class FeatureGeometry(BaseModel):
    """Feature의 geometry(GeoJSON Point).

    coordinates = **[longitude, lat, depth(km)]** 순서(GeoJSON 규약 — 경도 먼저).
    출처: 라이브(/query features[].geometry) + GeoJSON 피드 안내.
    """

    model_config = {"extra": "ignore"}

    type: str | None = None
    coordinates: list[float] | None = None  # [lon, lat, depth_km]


class Feature(BaseModel):
    """단일 지진 Feature.

    {type:"Feature", properties:{...}, geometry:{...}, id:"<eventid>"}.
    출처: 라이브(/query features[]).
    """

    model_config = {"extra": "ignore"}

    type: str | None = None
    properties: FeatureProperties | None = None
    geometry: FeatureGeometry | None = None
    id: str | None = None


class Metadata(BaseModel):
    """FeatureCollection metadata(부분).

    generated(생성 ms epoch) · url · title("USGS Earthquakes") · status(HTTP 상태) ·
    api(서비스 버전) · count(이번 응답 feature 수, 라이브 확인) · limit · offset.
    출처: 라이브(/query metadata).
    """

    model_config = {"extra": "ignore"}

    title: str | None = None
    status: int | None = None
    count: int | None = None
    limit: int | None = None


class FeatureCollection(BaseModel):
    """/query?format=geojson 응답 봉투(GeoJSON FeatureCollection).

    {"type":"FeatureCollection","metadata":{...},"features":[...]}. 결과가 없으면
    features는 빈 배열이고 HTTP 200이다(라이브 확인 — geojson은 nodata 204를 쓰지 않음).
    출처: 라이브(/query?format=geojson).
    """

    model_config = {"extra": "ignore"}

    type: str | None = None
    metadata: Metadata | None = None
    features: list[Feature] = []


class CountResult(BaseModel):
    """/count?format=geojson 응답.

    {"count": N, "maxAllowed": 20000} — 조건에 매칭되는 이벤트 건수와 서버 상한.
    출처: 라이브(/count?format=geojson).
    """

    model_config = {"extra": "ignore"}

    count: int | None = None
    maxAllowed: int | None = Field(default=None)  # noqa: N815 (공식 필드명 그대로)
