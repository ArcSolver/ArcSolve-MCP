from arcsolve.service import Service
from arcsolve.services.openmeteo.tools import register

SERVICE = Service(
    name="openmeteo",
    register=register,
    docs_url="https://open-meteo.com/en/docs",
    summary="Open-Meteo 날씨·기후 읽기(예보·지오코딩)",
    # 무인증(키 없음·env 불필요). 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
