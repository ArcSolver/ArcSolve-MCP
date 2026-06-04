"""카카오 '나에게 보내기' MCP 도구 + 런타임 배선(자격증명·인증).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, post_form
from arcsolve.oauth import OAuthClient
from arcsolve.services.kakao import contract as k

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class KakaoSettings(BaseSettings):
    """KAKAO_* 환경변수에서 자격증명을 로드한다."""

    model_config = SettingsConfigDict(env_prefix="KAKAO_", env_file=".env", extra="ignore")
    rest_api_key: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None
    redirect_uri: str = "https://localhost"


def make_oauth_client() -> OAuthClient:
    s = KakaoSettings()
    return OAuthClient(
        service="kakao",
        token_url=k.TOKEN_URL,
        authorize_url=k.AUTHORIZE_URL,
        client_id=s.rest_api_key or "",
        client_secret=s.client_secret,
        scopes=k.SCOPES,
        redirect_uri=s.redirect_uri,
        env_refresh_token=s.refresh_token,
    )


def _explain(e: UpstreamError) -> str:
    payload = e.payload if isinstance(e.payload, dict) else {}
    code = payload.get("code")
    if code == -401:
        return "카카오 토큰이 만료/무효입니다. `arcsolve auth kakao`로 다시 인증하세요."
    if code == -402:
        return "동의항목 부족: 카카오 앱에서 talk_message(메시지 전송) 권한을 켜세요."
    return f"카카오 API 오류 {e.status}: {e.payload}"


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def kakao_send_text_to_me(
        text: str,
        link_url: str | None = None,
        button_title: str | None = None,
    ) -> str:
        """카카오톡 '나에게 보내기'로 텍스트 메시지를 전송한다.

        Args:
            text: 보낼 본문. 최대 200자.
            link_url: 지정하면 메시지에 바로가기 링크/버튼이 붙는다.
            button_title: 버튼 라벨(미지정 시 기본값). link_url이 있을 때만 의미가 있다.
        """
        try:
            template = k.TextTemplate(
                text=text,
                link=k.Link(web_url=link_url, mobile_web_url=link_url) if link_url else None,
                button_title=button_title,
            )
        except ValidationError as e:
            return f"입력 오류: {e.errors()[0]['msg']}"

        token = await make_oauth_client().access_token()
        try:
            raw = await post_form(
                k.BASE_URL + k.MEMO_DEFAULT,
                token=token,
                data={"template_object": template.model_dump_json(exclude_none=True)},
            )
        except UpstreamError as e:
            return _explain(e)

        return "전송 완료" if k.MemoResult.model_validate(raw).result_code == 0 else f"응답: {raw}"

    @mcp.tool
    async def kakao_send_link_to_me(url: str) -> str:
        """카카오톡 '나에게 보내기'로 URL을 스크랩(미리보기 카드) 형태로 전송한다.

        Args:
            url: 미리보기로 보낼 웹 페이지 주소.
        """
        req = k.ScrapRequest(request_url=url)
        token = await make_oauth_client().access_token()
        try:
            raw = await post_form(
                k.BASE_URL + k.MEMO_SCRAP,
                token=token,
                data=req.model_dump(exclude_none=True),
            )
        except UpstreamError as e:
            return _explain(e)

        return "전송 완료" if k.MemoResult.model_validate(raw).result_code == 0 else f"응답: {raw}"
