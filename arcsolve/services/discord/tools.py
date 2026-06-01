"""Discord MCP 도구 + 런타임 배선(자격증명).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층.

두 인증 경로를 제공한다:
  (A) Webhook 경로 — DISCORD_WEBHOOK_URL. URL 자체가 시크릿이라 인터랙티브 OAuth가 불필요하다.
  (B) Bot 토큰 경로 — DISCORD_BOT_TOKEN. `Authorization: Bot <token>` 헤더로 임의 채널 접근.
"""

from __future__ import annotations

from fastmcp import FastMCP
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, delete_json, get_json, patch_json, post_json
from arcsolve.services.discord import contract as d


class DiscordSettings(BaseSettings):
    """DISCORD_* 환경변수에서 자격증명을 로드한다.

    webhook_url: Discord 채널 설정 → 연동 → 웹후크에서 발급한 전체 URL.
                 URL path에 webhook id/token이 포함되어 있어 별도 인증 헤더가 없다.
    bot_token:   Discord 개발자 포털에서 발급한 Bot 토큰(선택).
                 `Authorization: Bot <token>` 헤더로 임의 채널에 메시지 전송/조회할 때 쓴다.
    """

    model_config = SettingsConfigDict(env_prefix="DISCORD_", env_file=".env", extra="ignore")
    webhook_url: str | None = None
    bot_token: str | None = None


def _bot_headers(token: str) -> dict[str, str]:
    """Bot 토큰 인증 헤더. Bearer가 아니라 `Bot <token>` 스킴을 쓴다.

    출처: https://discord.com/developers/docs/reference#authentication
    """
    return {"Authorization": f"Bot {token}"}


def _explain(e: UpstreamError) -> str:
    payload = e.payload if isinstance(e.payload, dict) else {}
    code = payload.get("code")
    # Discord JSON 에러 코드(공식):
    #   50001 Missing access · 50013 You lack permissions to perform that action
    #   10003 Unknown channel
    # 출처: https://discord.com/developers/docs/topics/opcodes-and-status-codes#json-json-error-codes
    if code == 50001:
        return "Discord 권한 부족(Missing access): 봇이 해당 채널/길드에 접근할 수 없습니다."
    if code == 50013:
        return "Discord 권한 부족: 봇에 이 작업 권한이 없습니다(예: View Channel/Send Messages)."
    if code == 10003:
        return "Discord 채널을 찾을 수 없습니다(Unknown channel). channel_id를 확인하세요."
    if e.status == 401:
        return (
            "Discord 인증 실패(401). Webhook URL 또는 Bot 토큰이 무효입니다. "
            "DISCORD_WEBHOOK_URL / DISCORD_BOT_TOKEN을 확인하세요."
        )
    if e.status == 403:
        return "Discord 접근 거부(403): 봇/웹후크에 해당 작업 권한이 없습니다."
    if e.status == 404:
        return (
            "Discord 리소스를 찾을 수 없습니다(404). "
            "Webhook URL이 삭제되었거나 message_id/channel_id가 잘못되었을 수 있습니다."
        )
    if e.status == 429:
        retry = payload.get("retry_after")
        return f"Discord 레이트 리밋. {retry}초 후 재시도하세요." if retry else "Discord 레이트 리밋."
    return f"Discord API 오류 {e.status}: {e.payload}"


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    # ─── (A) Webhook 경로 ───────────────────────────────────

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

    @mcp.tool
    async def discord_send_embed(
        title: str | None = None,
        description: str | None = None,
        url: str | None = None,
        color: int | None = None,
        footer: str | None = None,
    ) -> str:
        """Discord 채널에 Webhook으로 리치 임베드(카드) 1개를 전송한다.

        Args:
            title: 임베드 제목.
            description: 임베드 본문 설명.
            url: 제목에 걸리는 하이퍼링크 URL.
            color: 임베드 좌측 띠 색상(RGB 정수, 예: 빨강=0xFF0000=16711680).
            footer: 임베드 하단 푸터 텍스트.

        주의: title/description/url/color/footer 중 최소 하나는 지정해야 한다.
        """
        s = DiscordSettings()
        if not s.webhook_url:
            return "설정 오류: DISCORD_WEBHOOK_URL 환경변수가 비어 있습니다."

        if not any(v is not None for v in (title, description, url, color, footer)):
            return (
                "입력 오류: 임베드에 표시할 필드를 최소 하나"
                "(title/description/url/color/footer) 지정하세요."
            )

        try:
            embed = d.Embed(
                title=title,
                description=description,
                url=url,
                color=color,
                footer=d.EmbedFooter(text=footer) if footer else None,
            )
            req = d.ExecuteWebhookRequest(embeds=[embed])
        except ValidationError as e:
            return f"입력 오류: {e.errors()[0]['msg']}"

        # wait=true로 생성된 Message를 받아 message id를 회신한다(편집/삭제에 필요).
        # 출처: https://discord.com/developers/docs/resources/webhook#execute-webhook
        try:
            raw = await post_json(
                f"{s.webhook_url}?{d.WAIT_PARAM}=true",
                json=req.model_dump(exclude_none=True),
            )
        except UpstreamError as e:
            return _explain(e)

        msg = d.MessageResult.model_validate(raw)
        return f"임베드 전송 완료 (message id: {msg.id})" if msg.id else "임베드 전송 완료"

    @mcp.tool
    async def discord_edit_message(
        message_id: str,
        content: str | None = None,
    ) -> str:
        """Webhook이 보낸 기존 메시지를 편집한다(본문 교체).

        PATCH /webhooks/{id}/{token}/messages/{message_id} 를 호출한다.
        편집은 동일 Webhook이 보낸 메시지에만 가능하다.

        Args:
            message_id: 편집할 메시지 id. (전송 시 회신된 message id)
            content: 새 본문. 최대 2000자.
        """
        s = DiscordSettings()
        if not s.webhook_url:
            return "설정 오류: DISCORD_WEBHOOK_URL 환경변수가 비어 있습니다."
        if content is None:
            return "입력 오류: 편집할 content를 지정하세요."

        try:
            req = d.EditWebhookMessageRequest(content=content)
        except ValidationError as e:
            return f"입력 오류: {e.errors()[0]['msg']}"

        # Webhook URL 뒤에 /messages/{message_id}를 덧붙여 경로를 파생한다.
        # 출처: https://discord.com/developers/docs/resources/webhook#edit-webhook-message
        url = s.webhook_url.rstrip("/") + d.WEBHOOK_MESSAGE_SUFFIX.format(message_id=message_id)
        try:
            raw = await patch_json(url, json=req.model_dump(exclude_none=True))
        except UpstreamError as e:
            return _explain(e)

        msg = d.MessageResult.model_validate(raw)
        return f"편집 완료 (message id: {msg.id})" if msg.id else "편집 완료"

    @mcp.tool
    async def discord_delete_message(message_id: str) -> str:
        """Webhook이 보낸 기존 메시지를 삭제한다.

        DELETE /webhooks/{id}/{token}/messages/{message_id} 를 호출한다(성공 시 204 No Content).

        Args:
            message_id: 삭제할 메시지 id.
        """
        s = DiscordSettings()
        if not s.webhook_url:
            return "설정 오류: DISCORD_WEBHOOK_URL 환경변수가 비어 있습니다."

        # 출처: https://discord.com/developers/docs/resources/webhook#delete-webhook-message
        url = s.webhook_url.rstrip("/") + d.WEBHOOK_MESSAGE_SUFFIX.format(message_id=message_id)
        try:
            await delete_json(url)
        except UpstreamError as e:
            return _explain(e)

        return f"삭제 완료 (message id: {message_id})"

    # ─── (B) Bot 토큰 경로 ──────────────────────────────────

    @mcp.tool
    async def discord_create_message(channel_id: str, content: str) -> str:
        """Bot 토큰으로 임의 채널에 메시지를 전송한다.

        POST /channels/{channel_id}/messages, 헤더 `Authorization: Bot <token>`.
        DISCORD_BOT_TOKEN이 설정돼 있어야 한다.

        Args:
            channel_id: 대상 채널 id(snowflake).
            content: 보낼 본문. 최대 2000자.
        """
        s = DiscordSettings()
        if not s.bot_token:
            return (
                "설정 오류: DISCORD_BOT_TOKEN 환경변수가 비어 있습니다. "
                "Discord 개발자 포털에서 봇 토큰을 발급해 .env에 DISCORD_BOT_TOKEN으로 넣으세요."
            )

        try:
            req = d.CreateMessageRequest(content=content)
        except ValidationError as e:
            return f"입력 오류: {e.errors()[0]['msg']}"

        # 출처: https://discord.com/developers/docs/resources/message#create-message
        url = d.API_BASE_URL + d.CHANNEL_MESSAGES_ROUTE.format(channel_id=channel_id)
        try:
            raw = await post_json(
                url,
                headers=_bot_headers(s.bot_token),
                json=req.model_dump(exclude_none=True),
            )
        except UpstreamError as e:
            return _explain(e)

        msg = d.MessageResult.model_validate(raw)
        return f"전송 완료 (message id: {msg.id})" if msg.id else "전송 완료"

    @mcp.tool
    async def discord_list_messages(
        channel_id: str,
        limit: int = d.MESSAGES_LIMIT_DEFAULT,
    ) -> str:
        """Bot 토큰으로 채널의 최근 메시지를 조회한다.

        GET /channels/{channel_id}/messages?limit=N, 헤더 `Authorization: Bot <token>`.
        DISCORD_BOT_TOKEN이 설정돼 있어야 한다.

        Args:
            channel_id: 대상 채널 id(snowflake).
            limit: 가져올 개수(1–100, 기본 50).
        """
        s = DiscordSettings()
        if not s.bot_token:
            return (
                "설정 오류: DISCORD_BOT_TOKEN 환경변수가 비어 있습니다. "
                "Discord 개발자 포털에서 봇 토큰을 발급해 .env에 DISCORD_BOT_TOKEN으로 넣으세요."
            )
        if not (d.MESSAGES_LIMIT_MIN <= limit <= d.MESSAGES_LIMIT_MAX):
            return f"입력 오류: limit은 {d.MESSAGES_LIMIT_MIN}–{d.MESSAGES_LIMIT_MAX} 범위여야 합니다."

        # 출처: https://discord.com/developers/docs/resources/message#get-channel-messages
        url = d.API_BASE_URL + d.CHANNEL_MESSAGES_ROUTE.format(channel_id=channel_id)
        try:
            raw = await get_json(
                url,
                headers=_bot_headers(s.bot_token),
                params={"limit": limit},
            )
        except UpstreamError as e:
            return _explain(e)

        # 응답은 Message 배열(get_json은 -> dict 힌트지만 JSON 배열이면 list를 그대로 반환).
        if not isinstance(raw, list):
            return f"예상치 못한 응답: {raw}"
        msgs = [d.MessageResult.model_validate(m) for m in raw if isinstance(m, dict)]
        if not msgs:
            return "메시지가 없습니다."
        lines = []
        for m in msgs:
            who = m.author.username if m.author and m.author.username else "?"
            body = (m.content or "").replace("\n", " ")
            lines.append(f"- [{m.id}] {who}: {body}")
        return f"{len(msgs)}개 메시지:\n" + "\n".join(lines)
