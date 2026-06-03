from arcsolve.service import Service
from arcsolve.services.notion.tools import register

SERVICE = Service(
    name="notion",
    register=register,
    docs_url="https://developers.notion.com/reference/intro",
    summary="Notion 워크스페이스 읽기(search·pages·blocks·databases·data sources)",
    # Bearer 토큰(NOTION_TOKEN) — 사전발급 토큰이라 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
