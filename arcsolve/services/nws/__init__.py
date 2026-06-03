from arcsolve.service import Service
from arcsolve.services.nws.tools import register

SERVICE = Service(
    name="nws",
    register=register,
    docs_url="https://www.weather.gov/documentation/services-web-api",
    summary="NWS 미국 날씨 읽기(예보·시간별 예보·활성 기상특보)",
    # 무인증(키 없음) — 단 User-Agent 헤더 필수(기본값 contract.DEFAULT_USER_AGENT, NWS_USER_AGENT로 덮어씀).
    # 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
