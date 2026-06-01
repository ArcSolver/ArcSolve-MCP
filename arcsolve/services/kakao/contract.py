"""카카오톡 메시지 REST API 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트, 인증 요건, 요청/응답 스키마.
MCP에 대한 의존성 없음(순수 상수 + pydantic 모델).

출처(공식 문서):
  - 메시지 REST API   : https://developers.kakao.com/docs/latest/ko/kakaotalk-message/rest-api
  - 메시지 템플릿      : https://developers.kakao.com/docs/latest/ko/message-template/common
  - 카카오 로그인(토큰): https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ─── 인증 (카카오 로그인 OAuth 2.0) ──────────────────────────
AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SCOPES = ["talk_message"]  # 동의항목: '카카오톡 메시지 전송'

# ─── 메시지 API ─────────────────────────────────────────────
BASE_URL = "https://kapi.kakao.com"

# '나에게 보내기'(memo) — 추가 권한 신청 불필요
MEMO_DEFAULT = "/v2/api/talk/memo/default/send"  # body: template_object=<json>
MEMO_CUSTOM = "/v2/api/talk/memo/send"           # body: template_id, template_args=<json>?
MEMO_SCRAP = "/v2/api/talk/memo/scrap/send"      # body: request_url, template_id?, template_args?

# 기본 템플릿 object_type 6종: feed | list | location | commerce | text | calendar
# MVP는 text만 모델링한다. 나머지는 아래 TextTemplate와 동일한 패턴으로 추가하면 된다.


class Link(BaseModel):
    """콘텐츠/버튼 클릭 시 이동할 링크. 링크를 적용하려면 한 필드 이상 채운다."""

    web_url: str | None = None
    mobile_web_url: str | None = None
    android_execution_params: str | None = None
    ios_execution_params: str | None = None


class Button(BaseModel):
    """메시지 하단 버튼. title + 클릭 시 이동할 link."""

    title: str
    link: Link


class TextTemplate(BaseModel):
    """텍스트 기본 템플릿.

    공식 필드: text(필수, ≤200자) · link(선택) · button_title(선택, 8자 권장) ·
    buttons(선택, 최대 2개). link을 주지 않으면 버튼이 표시되지 않는다.
    """

    object_type: Literal["text"] = "text"
    text: str = Field(max_length=200)
    link: Link | None = None
    button_title: str | None = None
    buttons: list[Button] | None = Field(default=None, max_length=2)


class ScrapRequest(BaseModel):
    """스크랩(미리보기) 전송 요청. request_url 필수, 템플릿은 선택."""

    request_url: str
    template_id: int | None = None
    template_args: str | None = None  # JSON 문자열


class MemoResult(BaseModel):
    """'나에게 보내기' 응답. result_code == 0 이면 성공."""

    result_code: int
