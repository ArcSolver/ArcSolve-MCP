"""도구 런타임 기능 테스트용 공유 헬퍼(픽스처).

실제 `@mcp.tool` 함수를 FastMCP 없이 꺼내 직접 호출하고(FakeMCP), `arcsolve.http` 동사를
RecordingHTTP로 monkeypatch해 네트워크 없이 "요청 조립 → 응답 파싱 → 출력/에러 매핑"을 검증한다.
도구 모듈은 fastmcp를 런타임 import하지 않으므로(타입힌트는 TYPE_CHECKING) 가볍게 로드된다.
"""

from __future__ import annotations

import pytest


class FakeMCP:
    """register(mcp)가 `@mcp.tool`로 등록하는 함수를 그대로 수집하는 스텁."""

    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self, fn):  # 코드베이스는 `@mcp.tool`(괄호 없음)로 사용한다
        self.tools[fn.__name__] = fn
        return fn


class RecordingHTTP:
    """async HTTP 동사 대역: 호출 인자를 기록하고 정해진 응답을 반환(또는 예외를 raise)한다."""

    def __init__(self, ret=None, exc: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._ret = {} if ret is None else ret
        self._exc = exc

    async def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self._exc is not None:
            raise self._exc
        return self._ret

    @property
    def last(self) -> dict:
        assert self.calls, "HTTP 동사가 호출되지 않았습니다."
        return self.calls[-1]


@pytest.fixture
def load_tools():
    """register(mcp)를 FakeMCP에 적용해 {도구이름: 함수} 딕셔너리를 돌려주는 헬퍼."""

    def _load(register) -> dict:
        fake = FakeMCP()
        register(fake)
        return fake.tools

    return _load


@pytest.fixture
def recording_http():
    """RecordingHTTP 클래스를 그대로 노출(테스트에서 ret/exc로 인스턴스화)."""
    return RecordingHTTP
