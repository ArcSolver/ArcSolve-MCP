"""Telegram 메시지 전송 MCP 도구 + 런타임 배선(자격증명).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층.
이 서비스는 인터랙티브 OAuth가 아니라 봇 토큰(env)을 URL 경로에 넣는 방식이므로
oauth.py / make_auth_client 를 쓰지 않는다.
"""

from __future__ import annotations

from fastmcp import FastMCP
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, post_json
from arcsolve.services.telegram import contract as t


class TelegramSettings(BaseSettings):
    """TELEGRAM_* 환경변수에서 자격증명을 로드한다.

    - bot_token: @BotFather에서 발급한 봇 토큰(필수).
    - chat_id: '나에게 보내기' 결을 위한 기본 대상. 도구 인자로 덮어쓸 수 있다(선택).
    """

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_", env_file=".env", extra="ignore")
    bot_token: str | None = None
    chat_id: str | None = None


def _explain(e: UpstreamError) -> str:
    """Telegram의 ok=false/error_code/description을 사람이 읽을 메시지로 매핑."""
    payload = e.payload if isinstance(e.payload, dict) else {}
    code = payload.get("error_code", e.status)
    desc = payload.get("description") or e.payload
    if code == 401:
        return "텔레그램 봇 토큰이 무효입니다. TELEGRAM_BOT_TOKEN을 확인하세요."
    if code == 400 and isinstance(desc, str) and "chat not found" in desc.lower():
        return "대상 chat_id를 찾을 수 없습니다. 봇과 먼저 대화를 시작했는지 확인하세요."
    if code == 403:
        return f"전송이 차단되었습니다(봇이 차단되었거나 권한 없음): {desc}"
    return f"텔레그램 API 오류 {code}: {desc}"


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def telegram_send_message(
        text: str,
        chat_id: str | None = None,
        parse_mode: str | None = None,
        disable_link_preview: bool = False,
        disable_notification: bool = False,
    ) -> str:
        """Telegram 봇으로 텍스트 메시지를 전송한다(sendMessage).

        Args:
            text: 보낼 본문. 1-4096자.
            chat_id: 대상 채팅 ID 또는 "@channelusername". 미지정 시 TELEGRAM_CHAT_ID 사용.
            parse_mode: 서식 모드. "MarkdownV2" 또는 "HTML". 미지정 시 평문.
            disable_link_preview: True면 본문 링크의 미리보기를 끈다.
            disable_notification: True면 알림 없이 조용히 전송한다.
        """
        settings = TelegramSettings()
        if not settings.bot_token:
            return "TELEGRAM_BOT_TOKEN이 설정되지 않았습니다."

        target = chat_id or settings.chat_id
        if not target:
            return "chat_id가 없습니다. 인자로 주거나 TELEGRAM_CHAT_ID를 설정하세요."

        try:
            req = t.SendMessage(
                chat_id=target,
                text=text,
                parse_mode=parse_mode,
                link_preview_options=(
                    t.LinkPreviewOptions(is_disabled=True) if disable_link_preview else None
                ),
                disable_notification=disable_notification or None,
            )
        except ValidationError as e:
            return f"입력 오류: {e.errors()[0]['msg']}"

        url = t.BASE_URL + t.method_path(settings.bot_token, t.SEND_MESSAGE)
        try:
            raw = await post_json(url, json=req.model_dump(exclude_none=True))
        except UpstreamError as e:
            return _explain(e)

        resp = t.ApiResponse.model_validate(raw)
        if not resp.ok or resp.result is None:
            return f"전송 실패: {resp.description or raw}"
        msg = t.Message.model_validate(resp.result)
        return f"전송 완료 (message_id={msg.message_id})"
