"""Telegram 도구 런타임 기능 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑을 확인.

http 동사는 RecordingHTTP로 monkeypatch, 자격증명은 monkeypatch.setenv로 주입한다.
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.telegram.contract import FILE_UPLOAD_MAX_BYTES, PHOTO_UPLOAD_MAX_BYTES
from arcsolve.services.telegram.tools import _build_upload, is_local_file, register

MOD = "arcsolve.services.telegram.tools"
OK_MSG = {"ok": True, "result": {"message_id": 9, "date": 1, "chat": {"id": 42, "type": "private"}}}


@pytest.fixture
def tg(monkeypatch, load_tools):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    return load_tools(register)


async def test_send_message_builds_request_and_formats_output(tg, monkeypatch, recording_http):
    http = recording_http(ret=OK_MSG)
    monkeypatch.setattr(f"{MOD}.post_json", http)

    out = await tg["telegram_send_message"](text="hi")

    assert out == "전송 완료 (message_id=9)"
    assert http.last["url"] == "https://api.telegram.org/botT/sendMessage"
    assert http.last["json"] == {"chat_id": "42", "text": "hi"}  # None 제외, 토큰은 URL 경로


async def test_send_message_missing_token(monkeypatch, load_tools):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    tools = load_tools(register)
    out = await tools["telegram_send_message"](text="hi", chat_id="1")
    assert "TELEGRAM_BOT_TOKEN" in out


async def test_send_message_maps_401_error(tg, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(401, {"ok": False, "error_code": 401,
                                                  "description": "Unauthorized"}))
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await tg["telegram_send_message"](text="hi")
    assert "토큰" in out  # 사람이 읽을 안내로 매핑


async def test_get_me_parses_user(tg, monkeypatch, recording_http):
    http = recording_http(ret={"ok": True, "result": {"id": 1, "is_bot": True,
                                                       "first_name": "Bot", "username": "mybot"}})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tg["telegram_get_me"]()
    assert "@mybot" in out and "id=1" in out
    assert http.last["url"] == "https://api.telegram.org/botT/getMe"


async def test_send_photo_url_uses_json_path(tg, monkeypatch, recording_http):
    http = recording_http(ret=OK_MSG)
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await tg["telegram_send_photo"](photo="https://x/p.jpg", caption="c")
    assert "사진 전송 완료" in out
    assert http.last["url"].endswith("/sendPhoto")
    assert http.last["json"]["photo"] == "https://x/p.jpg"
    assert http.last["json"]["caption"] == "c"


async def test_send_photo_local_file_uses_multipart(tg, monkeypatch, recording_http, tmp_path):
    f = tmp_path / "pic.jpg"
    f.write_bytes(b"\xff\xd8\xffdata")
    http = recording_http(ret=OK_MSG)
    monkeypatch.setattr(f"{MOD}.post_multipart", http)

    out = await tg["telegram_send_photo"](photo=str(f), caption="cap")

    assert "사진 전송 완료" in out
    assert http.last["url"].endswith("/sendPhoto")
    name, blob, mime = http.last["files"]["photo"]  # 파일은 'photo' 파트
    assert name == "pic.jpg" and blob == b"\xff\xd8\xffdata" and mime == "image/jpeg"
    assert http.last["data"] == {"chat_id": "42", "caption": "cap"}  # 나머지는 폼 필드


async def test_send_document_local_file_uses_multipart(tg, monkeypatch, recording_http, tmp_path):
    f = tmp_path / "doc.txt"
    f.write_bytes(b"hello")
    http = recording_http(ret={"ok": True, "result": {"message_id": 8, "date": 1,
                                                       "chat": {"id": 42, "type": "private"}}})
    monkeypatch.setattr(f"{MOD}.post_multipart", http)
    out = await tg["telegram_send_document"](document=str(f))
    assert "문서 전송 완료" in out
    assert "document" in http.last["files"]


async def test_edit_message_text_chat_path(tg, monkeypatch, recording_http):
    http = recording_http(ret={"ok": True, "result": {"message_id": 3, "date": 1,
                                                       "chat": {"id": 42, "type": "private"}}})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await tg["telegram_edit_message_text"](text="new", message_id=3, chat_id="42")
    assert "편집 완료" in out
    assert http.last["json"] == {"chat_id": "42", "message_id": 3, "text": "new"}


async def test_edit_message_text_rejects_no_target(monkeypatch, load_tools, recording_http):
    http = recording_http(ret={"ok": True})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)  # chat 기본값 없음
    tools = load_tools(register)
    out = await tools["telegram_edit_message_text"](text="new")  # 대상 경로 없음
    assert "입력 오류" in out
    assert not http.calls  # HTTP 호출 전에 막힘


async def test_delete_message_request_shape(tg, monkeypatch, recording_http):
    http = recording_http(ret={"ok": True, "result": True})
    monkeypatch.setattr(f"{MOD}.post_json", http)
    out = await tg["telegram_delete_message"](chat_id="42", message_id=3)
    assert "삭제" in out
    assert http.last["json"] == {"chat_id": "42", "message_id": 3}


# ─── 업로드 헬퍼(tools 레이어) ──────────────────────────────


def test_is_local_file_detects_path_vs_url_or_file_id(tmp_path):
    f = tmp_path / "pic.jpg"
    f.write_bytes(b"data")
    assert is_local_file(str(f)) is True
    assert is_local_file("https://example.com/a.jpg") is False
    assert is_local_file("AgACAgID-some-file-id") is False
    assert is_local_file("") is False


def test_build_upload_packs_filename_bytes_and_mime(tmp_path):
    f = tmp_path / "pic.jpg"
    f.write_bytes(b"\xff\xd8\xffdata")
    files = _build_upload(str(f), "photo", PHOTO_UPLOAD_MAX_BYTES)
    assert isinstance(files, dict)
    name, blob, mime = files["photo"]
    assert name == "pic.jpg"
    assert blob == b"\xff\xd8\xffdata"
    assert mime == "image/jpeg"


def test_build_upload_size_guard_returns_error(tmp_path):
    f = tmp_path / "big.bin"
    f.write_bytes(b"0123456789")  # 10 bytes
    out = _build_upload(str(f), "document", 5)  # 한도 5바이트
    assert isinstance(out, str)
    assert "한도" in out


def test_file_upload_max_constant_used_for_documents():
    assert FILE_UPLOAD_MAX_BYTES == 50 * 1024 * 1024
