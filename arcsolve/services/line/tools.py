"""LINE push 메시지 MCP 도구 + 런타임 배선(자격증명).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층.
인증은 채널 액세스 토큰(Bearer) — 인터랙티브 OAuth가 아니므로 make_auth_client 없음.
"""

from __future__ import annotations

from fastmcp import FastMCP
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, bearer, post_json
from arcsolve.services.line import contract as l


class LineSettings(BaseSettings):
    """LINE_* 환경변수에서 자격증명을 로드한다."""

    model_config = SettingsConfigDict(env_prefix="LINE_", env_file=".env", extra="ignore")
    channel_access_token: str | None = None
    to: str | None = None  # 기본 수신자(userId/groupId/roomId). 인자로 덮어쓸 수 있다.


def _explain(e: UpstreamError) -> str:
    """문서화된 상태코드로 에러를 사람이 읽을 메시지에 매핑한다.

    출처(상태코드): https://developers.line.biz/en/reference/messaging-api/#error-responses
    """
    err = l.ErrorResponse.model_validate(e.payload) if isinstance(e.payload, dict) else None
    detail = err.message if err and err.message else e.payload
    if e.status == 400:
        return f"요청 오류(400): 수신자(to)/메시지 형식을 확인하세요. {detail}"
    if e.status == 401:
        return "LINE 채널 액세스 토큰이 없거나 무효입니다. LINE_CHANNEL_ACCESS_TOKEN을 확인하세요."
    if e.status == 403:
        return f"권한 없음(403): 채널 설정/플랜을 확인하세요. {detail}"
    if e.status == 409:
        return f"중복 요청(409): 동일 retry-key가 이미 처리되었을 수 있습니다. {detail}"
    if e.status == 429:
        return f"요청 한도 초과(429). 잠시 후 재시도하세요. {detail}"
    return f"LINE API 오류 {e.status}: {detail}"


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def line_send_text(text: str, to: str | None = None) -> str:
        """LINE Messaging API push로 텍스트 메시지 1건을 전송한다.

        Args:
            text: 보낼 본문. 최대 5000자.
            to: 수신자 ID(userId/groupId/roomId). 미지정 시 LINE_TO 환경변수를 쓴다.
        """
        settings = LineSettings()
        token = settings.channel_access_token
        if not token:
            return "설정 오류: LINE_CHANNEL_ACCESS_TOKEN 환경변수가 필요합니다."

        recipient = to or settings.to
        if not recipient:
            return "입력 오류: 수신자 to 를 지정하거나 LINE_TO 환경변수를 설정하세요."

        try:
            req = l.PushRequest(to=recipient, messages=[l.TextMessage(text=text)])
        except ValidationError as e:
            return f"입력 오류: {e.errors()[0]['msg']}"

        try:
            raw = await post_json(
                l.BASE_URL + l.PUSH_MESSAGE,
                headers=bearer(token),
                json=req.model_dump(exclude_none=True),
            )
        except UpstreamError as e:
            return _explain(e)

        result = l.PushResult.model_validate(raw if isinstance(raw, dict) else {})
        sent_id = result.sentMessages[0].id if result.sentMessages else None
        return f"전송 완료 (id={sent_id})" if sent_id else "전송 완료"
