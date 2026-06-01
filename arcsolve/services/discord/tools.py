"""Discord Webhook MCP 도구 + 런타임 배선(자격증명).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층.

이 서비스는 인터랙티브 OAuth가 아니다 — Webhook URL 자체가 시크릿이므로
make_auth_client/oauth.py를 쓰지 않는다.
"""

from __future__ import annotations

from fastmcp import FastMCP
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, post_json
from arcsolve.services.discord import contract as d


class DiscordSettings(BaseSettings):
    """DISCORD_* 환경변수에서 자격증명을 로드한다.

    webhook_url: Discord 채널 설정 → 연동 → 웹후크에서 발급한 전체 URL.
                 URL path에 webhook id/token이 포함되어 있어 별도 인증 헤더가 없다.
    """

    model_config = SettingsConfigDict(env_prefix="DISCORD_", env_file=".env", extra="ignore")
    webhook_url: str | None = None


def _explain(e: UpstreamError) -> str:
    payload = e.payload if isinstance(e.payload, dict) else {}
    if e.status == 401 or e.status == 404:
        return (
            "Discord webhook URL이 무효이거나 삭제되었습니다. "
            "DISCORD_WEBHOOK_URL을 다시 확인하세요."
        )
    if e.status == 429:
        retry = payload.get("retry_after")
        return f"Discord 레이트 리밋. {retry}초 후 재시도하세요." if retry else "Discord 레이트 리밋."
    return f"Discord API 오류 {e.status}: {e.payload}"


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def discord_send_message(
        content: str,
        username: str | None = None,
        avatar_url: str | None = None,
        tts: bool = False,
    ) -> str:
        """Discord 채널에 Webhook으로 메시지를 전송한다.

        Args:
            content: 보낼 본문. 최대 2000자.
            username: 지정하면 이 메시지에 한해 웹후크 표시 이름을 덮어쓴다.
            avatar_url: 지정하면 이 메시지에 한해 웹후크 아바타를 덮어쓴다.
            tts: True면 TTS(읽어주기) 메시지로 전송한다.
        """
        s = DiscordSettings()
        if not s.webhook_url:
            return "설정 오류: DISCORD_WEBHOOK_URL 환경변수가 비어 있습니다."

        try:
            req = d.ExecuteWebhookRequest(
                content=content,
                username=username,
                avatar_url=avatar_url,
                tts=tts or None,
            )
        except ValidationError as e:
            return f"입력 오류: {e.errors()[0]['msg']}"

        # wait=true로 보내 서버 확인 + 생성된 Message 오브젝트를 받는다.
        # (기본 wait=false는 204 No Content라 확인이 어렵다.)
        # 출처: https://discord.com/developers/docs/resources/webhook#execute-webhook
        try:
            raw = await post_json(
                f"{s.webhook_url}?{d.WAIT_PARAM}=true",
                json=req.model_dump(exclude_none=True),
            )
        except UpstreamError as e:
            return _explain(e)

        msg = d.MessageResult.model_validate(raw)
        return f"전송 완료 (message id: {msg.id})" if msg.id else "전송 완료"
