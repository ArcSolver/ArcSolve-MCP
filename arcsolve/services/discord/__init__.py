from arcsolve.service import Service
from arcsolve.services.discord.tools import register

SERVICE = Service(
    name="discord",
    register=register,
    docs_url="https://discord.com/developers/docs/resources/webhook",
    summary="Discord — Webhook으로 채널에 메시지 전송",
    # make_auth_client 없음: Webhook URL 자체가 시크릿이라 인터랙티브 OAuth가 불필요하다.
)
