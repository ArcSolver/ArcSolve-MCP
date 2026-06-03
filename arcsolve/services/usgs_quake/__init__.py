from arcsolve.service import Service
from arcsolve.services.usgs_quake.tools import register

SERVICE = Service(
    name="usgs_quake",
    register=register,
    docs_url="https://earthquake.usgs.gov/fdsnws/event/1/",
    summary="USGS 지진 정보 읽기(FDSN Event API — 검색·건수, GeoJSON)",
    # 무인증(키 없음). 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
