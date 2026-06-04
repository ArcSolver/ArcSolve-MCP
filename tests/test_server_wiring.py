"""MCP 배선 스모크 — 전체 서버를 합성해 모든 서비스의 도구가 충돌·누락 없이 노출되는지 확인.

서비스는 자동 발견으로 계속 늘어나므로 도구 수/이름을 하드코딩하면 새 서비스마다 테스트를
손봐야 하고 드리프트가 생긴다. 대신 **불변식**을 검증한다: (1) 모든 서비스가 도구를 ≥1개 등록,
(2) 서비스 간 도구 이름이 겹치지 않음(collision), (3) 전체 서버 합성이 정확히 그 합집합을
노출(등록 누락·중복 없음). 이렇게 하면 빈·깨진 서비스, 이름 충돌, import/등록 회귀를
새 서비스가 늘어도 그대로 잡는다.
"""

from collections import Counter

from fastmcp import FastMCP

from arcsolve.server import build_server
from arcsolve.services import discover_services


async def _tool_names(register) -> list[str]:
    probe = FastMCP("probe")
    register(probe)
    return [t.name for t in await probe.list_tools()]


async def test_full_server_registers_every_service_without_collision():
    per_service = {svc.name: await _tool_names(svc.register) for svc in discover_services()}

    # (1) 모든 서비스가 도구를 최소 1개 기여해야 한다(빈/깨진 서비스 노출 차단).
    empty = sorted(name for name, tools in per_service.items() if not tools)
    assert not empty, f"도구를 등록하지 않은 서비스: {empty}"

    # (2) 서비스 간 도구 이름 충돌이 없어야 한다(prefix 네임스페이스 설계의 핵심 보장).
    all_names = [t for tools in per_service.values() for t in tools]
    collisions = sorted(n for n, c in Counter(all_names).items() if c > 1)
    assert not collisions, f"서비스 간 도구 이름 충돌: {collisions}"

    # (3) 전체 서버 합성이 정확히 각 서비스 도구의 합집합을 노출해야 한다(등록 누락·중복 없음).
    server = build_server()
    served = [t.name for t in await server.list_tools()]
    assert Counter(served) == Counter(all_names)
