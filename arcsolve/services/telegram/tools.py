"""Telegram 메시지 전송 MCP 도구 + 런타임 배선(자격증명).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층.
이 서비스는 인터랙티브 OAuth가 아니라 봇 토큰(env)을 URL 경로에 넣는 방식이므로
oauth.py / make_auth_client 를 쓰지 않는다.
"""

from __future__ import annotations

import mimetypes
import os
from typing import TYPE_CHECKING

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json, post_json, post_multipart
from arcsolve.services.telegram import contract as t

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


def is_local_file(value: str) -> bool:
    """입력이 로컬 파일 경로면 True(→ multipart 업로드), 아니면 False(→ URL/file_id로 JSON).

    Telegram은 사진/문서를 file_id·HTTP URL·multipart 3가지로 받는다(공식 #sending-files).
    문자열이 실제 존재하는 로컬 파일일 때만 업로드 경로를 택한다.
    """
    return bool(value) and os.path.isfile(value)


def _build_upload(path: str, field: str, max_bytes: int) -> dict | str:
    """로컬 파일을 multipart `files` 형식으로 준비한다.

    성공 시 {field: (파일명, 바이트, MIME)} 를, 한도 초과 시 사람이 읽을 오류 문자열을 돌려준다.
    크기 한도 출처: https://core.telegram.org/bots/api#sending-files
    """
    size = os.path.getsize(path)
    if size > max_bytes:
        return (
            f"파일이 너무 큽니다({size // (1024 * 1024)}MB). "
            f"업로드 한도는 {max_bytes // (1024 * 1024)}MB입니다."
        )
    with open(path, "rb") as fh:
        blob = fh.read()
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return {field: (os.path.basename(path), blob, mime)}


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

    @mcp.tool
    async def telegram_get_me() -> str:
        """봇 신원/토큰 유효성을 확인한다(getMe). 헬스체크용. 파라미터 없음.

        성공 시 봇의 User 정보(id / username / first_name / is_bot)를 돌려준다.
        """
        settings = TelegramSettings()
        if not settings.bot_token:
            return "TELEGRAM_BOT_TOKEN이 설정되지 않았습니다."

        url = t.BASE_URL + t.method_path(settings.bot_token, t.GET_ME)
        try:
            raw = await get_json(url)
        except UpstreamError as e:
            return _explain(e)

        resp = t.ApiResponse.model_validate(raw)
        if not resp.ok or not isinstance(resp.result, dict):
            return f"조회 실패: {resp.description or raw}"
        me = t.User.model_validate(resp.result)
        handle = f"@{me.username}" if me.username else me.first_name
        return f"봇 OK: {handle} (id={me.id}, is_bot={me.is_bot})"

    @mcp.tool
    async def telegram_send_photo(
        photo: str,
        caption: str | None = None,
        chat_id: str | None = None,
        parse_mode: str | None = None,
    ) -> str:
        """Telegram 봇으로 사진을 전송한다(sendPhoto).

        Args:
            photo: 사진의 **HTTP URL · file_id · 또는 로컬 파일 경로**. 로컬 파일이면
                   multipart로 업로드한다(사진 업로드 한도 10MB). ⚠️ 로컬 경로를 주면
                   서버 파일시스템의 해당 파일을 읽어 전송한다.
            caption: 사진 캡션. 0-1024자.
            chat_id: 대상 채팅 ID 또는 "@channelusername". 미지정 시 TELEGRAM_CHAT_ID 사용.
            parse_mode: 캡션 서식 모드. "MarkdownV2" 또는 "HTML". 미지정 시 평문.
        """
        settings = TelegramSettings()
        if not settings.bot_token:
            return "TELEGRAM_BOT_TOKEN이 설정되지 않았습니다."

        target = chat_id or settings.chat_id
        if not target:
            return "chat_id가 없습니다. 인자로 주거나 TELEGRAM_CHAT_ID를 설정하세요."
        if caption is not None and len(caption) > t.CAPTION_MAX_LENGTH:
            return f"입력 오류: caption은 최대 {t.CAPTION_MAX_LENGTH}자입니다."

        url = t.BASE_URL + t.method_path(settings.bot_token, t.SEND_PHOTO)
        try:
            if is_local_file(photo):
                files = _build_upload(photo, "photo", t.PHOTO_UPLOAD_MAX_BYTES)
                if isinstance(files, str):
                    return files  # 크기 한도 초과 등
                form = {"chat_id": target}
                if caption is not None:
                    form["caption"] = caption
                if parse_mode is not None:
                    form["parse_mode"] = parse_mode
                raw = await post_multipart(url, data=form, files=files)
            else:
                # URL 또는 file_id 문자열 → JSON 전송
                req = t.SendPhoto(
                    chat_id=target, photo=photo, caption=caption, parse_mode=parse_mode
                )
                raw = await post_json(url, json=req.model_dump(exclude_none=True))
        except ValidationError as e:
            return f"입력 오류: {e.errors()[0]['msg']}"
        except UpstreamError as e:
            return _explain(e)

        resp = t.ApiResponse.model_validate(raw)
        if not resp.ok or not isinstance(resp.result, dict):
            return f"전송 실패: {resp.description or raw}"
        msg = t.Message.model_validate(resp.result)
        return f"사진 전송 완료 (message_id={msg.message_id})"

    @mcp.tool
    async def telegram_send_document(
        document: str,
        caption: str | None = None,
        chat_id: str | None = None,
        parse_mode: str | None = None,
    ) -> str:
        """Telegram 봇으로 문서(파일)를 전송한다(sendDocument).

        Args:
            document: 파일의 **HTTP URL · file_id · 또는 로컬 파일 경로**. 로컬 파일이면
                      multipart로 업로드한다(파일 업로드 한도 50MB). ⚠️ 로컬 경로를 주면
                      서버 파일시스템의 해당 파일을 읽어 전송한다.
            caption: 문서 캡션. 0-1024자.
            chat_id: 대상 채팅 ID 또는 "@channelusername". 미지정 시 TELEGRAM_CHAT_ID 사용.
            parse_mode: 캡션 서식 모드. "MarkdownV2" 또는 "HTML". 미지정 시 평문.
        """
        settings = TelegramSettings()
        if not settings.bot_token:
            return "TELEGRAM_BOT_TOKEN이 설정되지 않았습니다."

        target = chat_id or settings.chat_id
        if not target:
            return "chat_id가 없습니다. 인자로 주거나 TELEGRAM_CHAT_ID를 설정하세요."
        if caption is not None and len(caption) > t.CAPTION_MAX_LENGTH:
            return f"입력 오류: caption은 최대 {t.CAPTION_MAX_LENGTH}자입니다."

        url = t.BASE_URL + t.method_path(settings.bot_token, t.SEND_DOCUMENT)
        try:
            if is_local_file(document):
                files = _build_upload(document, "document", t.FILE_UPLOAD_MAX_BYTES)
                if isinstance(files, str):
                    return files  # 크기 한도 초과 등
                form = {"chat_id": target}
                if caption is not None:
                    form["caption"] = caption
                if parse_mode is not None:
                    form["parse_mode"] = parse_mode
                raw = await post_multipart(url, data=form, files=files)
            else:
                req = t.SendDocument(
                    chat_id=target, document=document, caption=caption, parse_mode=parse_mode
                )
                raw = await post_json(url, json=req.model_dump(exclude_none=True))
        except ValidationError as e:
            return f"입력 오류: {e.errors()[0]['msg']}"
        except UpstreamError as e:
            return _explain(e)

        resp = t.ApiResponse.model_validate(raw)
        if not resp.ok or not isinstance(resp.result, dict):
            return f"전송 실패: {resp.description or raw}"
        msg = t.Message.model_validate(resp.result)
        return f"문서 전송 완료 (message_id={msg.message_id})"

    @mcp.tool
    async def telegram_edit_message_text(
        text: str,
        message_id: int | None = None,
        chat_id: str | None = None,
        inline_message_id: str | None = None,
        parse_mode: str | None = None,
    ) -> str:
        """메시지의 텍스트를 편집한다(editMessageText).

        대상 지정은 공식 계약에 따라 둘 중 하나(상호 배타):
        - chat_id + message_id : 일반 채팅 메시지 편집(chat_id 미지정 시 TELEGRAM_CHAT_ID).
        - inline_message_id    : 인라인 모드로 보낸 메시지 편집.

        Args:
            text: 새 본문. 1-4096자.
            message_id: 편집할 메시지 ID(chat 경로).
            chat_id: 대상 채팅 ID 또는 "@channelusername". 미지정 시 TELEGRAM_CHAT_ID.
            inline_message_id: 인라인 메시지 ID(지정 시 chat_id/message_id는 생략).
            parse_mode: 서식 모드. "MarkdownV2" 또는 "HTML". 미지정 시 평문.
        """
        settings = TelegramSettings()
        if not settings.bot_token:
            return "TELEGRAM_BOT_TOKEN이 설정되지 않았습니다."

        target_chat = None if inline_message_id else (chat_id or settings.chat_id)
        try:
            req = t.EditMessageText(
                chat_id=target_chat,
                message_id=message_id,
                inline_message_id=inline_message_id,
                text=text,
                parse_mode=parse_mode,
            )
        except ValidationError as e:
            return f"입력 오류: {e.errors()[0]['msg']}"

        url = t.BASE_URL + t.method_path(settings.bot_token, t.EDIT_MESSAGE_TEXT)
        try:
            raw = await post_json(url, json=req.model_dump(exclude_none=True))
        except UpstreamError as e:
            return _explain(e)

        resp = t.ApiResponse.model_validate(raw)
        if not resp.ok:
            return f"편집 실패: {resp.description or raw}"
        # editMessageText는 편집된 Message(dict) 또는 인라인의 경우 True를 반환한다.
        if isinstance(resp.result, dict):
            msg = t.Message.model_validate(resp.result)
            return f"편집 완료 (message_id={msg.message_id})"
        return "편집 완료"

    @mcp.tool
    async def telegram_delete_message(chat_id: str, message_id: int) -> str:
        """봇이 접근 가능한 메시지를 삭제한다(deleteMessage).

        Args:
            chat_id: 대상 채팅 ID 또는 "@channelusername".
            message_id: 삭제할 메시지의 ID.
        """
        settings = TelegramSettings()
        if not settings.bot_token:
            return "TELEGRAM_BOT_TOKEN이 설정되지 않았습니다."

        try:
            req = t.DeleteMessage(chat_id=chat_id, message_id=message_id)
        except ValidationError as e:
            return f"입력 오류: {e.errors()[0]['msg']}"

        url = t.BASE_URL + t.method_path(settings.bot_token, t.DELETE_MESSAGE)
        try:
            raw = await post_json(url, json=req.model_dump(exclude_none=True))
        except UpstreamError as e:
            return _explain(e)

        resp = t.ApiResponse.model_validate(raw)
        # deleteMessage는 성공 시 result=True를 반환한다.
        if not resp.ok or resp.result is not True:
            return f"삭제 실패: {resp.description or raw}"
        return f"삭제 완료 (message_id={message_id})"
