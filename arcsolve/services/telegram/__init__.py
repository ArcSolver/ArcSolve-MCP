from arcsolve.service import Service
from arcsolve.services.telegram.tools import register

SERVICE = Service(
    name="telegram",
    register=register,
    docs_url="https://core.telegram.org/bots/api",
    summary="Telegram Bot API — sendMessage로 텍스트 전송",
    # OAuth 아님: 봇 토큰을 URL 경로에 넣는 방식이라 make_auth_client 없음.
)
