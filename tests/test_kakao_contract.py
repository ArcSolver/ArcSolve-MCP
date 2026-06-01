"""카카오 계약 검증 — 네트워크 없이 contract.py만 테스트."""

import json

import pytest
from pydantic import ValidationError

from arcsolve.services.kakao.contract import (
    MEMO_DEFAULT,
    MEMO_SCRAP,
    SCOPES,
    Button,
    Link,
    MemoResult,
    TextTemplate,
)


def test_text_template_serialization():
    t = TextTemplate(text="안녕", link=Link(web_url="https://a.b", mobile_web_url="https://a.b"))
    payload = json.loads(t.model_dump_json(exclude_none=True))
    assert payload["object_type"] == "text"
    assert payload["text"] == "안녕"
    assert payload["link"]["web_url"] == "https://a.b"
    assert "button_title" not in payload  # None은 제외되어야 함


def test_text_template_omits_optional_when_absent():
    # link은 선택 — 없으면 전송 페이로드에서 아예 제외되어야 한다(빈 {} 보내지 않음).
    t = TextTemplate(text="링크 없음")
    payload = json.loads(t.model_dump_json(exclude_none=True))
    assert "link" not in payload
    assert "buttons" not in payload
    assert "button_title" not in payload


def test_text_max_length_enforced():
    with pytest.raises(ValidationError):
        TextTemplate(text="가" * 201)


def test_buttons_max_two_enforced():
    btn = Button(title="확인", link=Link(web_url="https://a.b"))
    TextTemplate(text="ok", buttons=[btn, btn])  # 2개는 허용
    with pytest.raises(ValidationError):
        TextTemplate(text="too many", buttons=[btn, btn, btn])  # 3개는 거부


def test_memo_result():
    assert MemoResult.model_validate({"result_code": 0}).result_code == 0


def test_contract_constants():
    assert MEMO_DEFAULT == "/v2/api/talk/memo/default/send"
    assert MEMO_SCRAP == "/v2/api/talk/memo/scrap/send"
    assert SCOPES == ["talk_message"]
