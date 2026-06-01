"""MCP 배선 스모크 — 모든 서비스의 register(mcp)가 오류 없이 기대 도구 전체를 등록하는지 확인.

FakeMCP로 등록만 수행(무거운 FastMCP 서버 빌드 없이). build_server 합성 검증은 test_server_selection 참고.
"""

from arcsolve.services.discord.tools import register as discord_register
from arcsolve.services.kakao.tools import register as kakao_register
from arcsolve.services.line.tools import register as line_register
from arcsolve.services.openalex.tools import register as openalex_register
from arcsolve.services.telegram.tools import register as telegram_register
from arcsolve.services.zotero.tools import register as zotero_register

EXPECTED = {
    # telegram (6)
    "telegram_send_message", "telegram_get_me", "telegram_send_photo",
    "telegram_send_document", "telegram_edit_message_text", "telegram_delete_message",
    # discord (6)
    "discord_send_message", "discord_send_embed", "discord_edit_message",
    "discord_delete_message", "discord_create_message", "discord_list_messages",
    # line (5)
    "line_send_text", "line_reply_text", "line_multicast_text",
    "line_broadcast_text", "line_get_profile",
    # kakao (2)
    "kakao_send_text_to_me", "kakao_send_link_to_me",
    # zotero (8)
    "zotero_search_items", "zotero_get_item", "zotero_get_item_children",
    "zotero_list_collections", "zotero_get_collection_items", "zotero_list_tags",
    "zotero_get_fulltext", "zotero_health",
    # openalex (4)
    "openalex_search_works", "openalex_get_work",
    "openalex_search_authors", "openalex_get_author",
}


def test_all_services_register_expected_tools(load_tools):
    names: set[str] = set()
    for register in (
        telegram_register, discord_register, line_register, kakao_register,
        zotero_register, openalex_register,
    ):
        tools = load_tools(register)
        # 도구 이름 prefix가 서비스명과 일치하고, 서비스 내 중복이 없어야 한다.
        assert tools, f"{register.__module__}이 도구를 하나도 등록하지 않음"
        names |= set(tools)

    assert names == EXPECTED
    assert len(EXPECTED) == 31  # 카탈로그(6서비스·31도구)와 일치
