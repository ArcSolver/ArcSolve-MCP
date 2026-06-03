from arcsolve.service import Service
from arcsolve.services.wikipedia.tools import register

SERVICE = Service(
    name="wikipedia",
    register=register,
    docs_url="https://www.mediawiki.org/wiki/API:REST_API/Reference",
    summary="위키백과 읽기(검색·요약·본문·링크)",
    # 무인증으로 전체 읽기 동작 — 단 식별용 User-Agent 헤더 요구(기본값 contract.DEFAULT_USER_AGENT,
    # WIKIPEDIA_USER_AGENT로 덮어씀). (선택) WIKIPEDIA_API_TOKEN으로 레이트리밋 완화.
    # 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
