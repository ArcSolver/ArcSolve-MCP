"""서비스의 균일 계약.

모든 서비스(kakao, github, ...)는 이 `Service` 하나로 표현된다.
서버는 서비스의 내부 구현을 모르고, `register`만 호출해 도구를 받는다.
OAuth가 필요한 서비스는 `make_auth_client`를 노출하면 `arcsolve auth <name>`이
코어 수정 없이 동작한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from arcsolve.oauth import OAuthClient

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 import 회피(서버만 fastmcp가 필요)


@dataclass(frozen=True)
class Service:
    name: str                              # 예: "kakao"
    register: Callable[[FastMCP], None]    # 서버에 @mcp.tool 들을 붙이는 함수
    docs_url: str                          # 공식 API 문서(출처/provenance) — 필수
    summary: str = ""                      # 한 줄 설명
    make_auth_client: Callable[[], OAuthClient] | None = None  # OAuth 쓰는 서비스만
