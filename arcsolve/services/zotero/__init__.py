from arcsolve.service import Service
from arcsolve.services.zotero.tools import register

SERVICE = Service(
    name="zotero",
    register=register,
    docs_url="https://www.zotero.org/support/dev/web_api/v3/basics",
    summary="Zotero 라이브러리 읽기(Web API v3 + 로컬 데스크톱 API)",
    # 사전발급 API 키(헤더) 방식 — 인터랙티브 OAuth 아님(line과 동형) → make_auth_client 없음.
)
