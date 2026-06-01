from arcsolve.service import Service
from arcsolve.services.line.tools import register

SERVICE = Service(
    name="line",
    register=register,
    docs_url="https://developers.line.biz/en/reference/messaging-api/",
    summary="LINE Messaging API — 텍스트 메시지 전송(push/reply/multicast/broadcast) + 프로필 조회",
    # 채널 액세스 토큰(Bearer) 방식 — 인터랙티브 OAuth 아님 → make_auth_client 없음.
)
