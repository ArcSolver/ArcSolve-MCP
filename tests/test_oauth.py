"""OAuth PKCE + 토큰 저장소 권한 검증 (네트워크 없음)."""

import json
import os
import stat
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from arcsolve.oauth import OAuthClient, TokenStore


def _client(tmp_path, handler) -> OAuthClient:
    return OAuthClient(
        service="x",
        token_url="https://t/token",
        authorize_url="https://a/authorize",
        client_id="cid",
        scopes=["s"],
        store=TokenStore(tmp_path / "cred.json"),
        transport=httpx.MockTransport(handler),
    )


async def _ok_token(req):
    return httpx.Response(200, json={"access_token": "AT", "expires_in": 3600})


async def test_exchange_code_uses_pkce_and_saves(tmp_path):
    seen = {}

    async def handler(req):
        seen.update({k: v[0] for k, v in parse_qs(req.content.decode()).items()})
        return httpx.Response(
            200, json={"access_token": "AT", "refresh_token": "RT", "expires_in": 3600}
        )

    store = TokenStore(tmp_path / "cred.json")
    client = OAuthClient(
        service="x",
        token_url="https://t/token",
        authorize_url="https://a/authorize",
        client_id="cid",
        scopes=["s"],
        store=store,
        transport=httpx.MockTransport(handler),
    )

    url = client.authorize_url_for_login()
    assert "code_challenge=" in url and "code_challenge_method=S256" in url
    state = parse_qs(urlparse(url).query)["state"][0]

    await client.exchange_code("CODE", state=state)
    assert seen.get("grant_type") == "authorization_code"
    assert seen.get("code_verifier")  # PKCE verifier가 토큰 교환에 포함됨

    saved = json.loads((tmp_path / "cred.json").read_text())
    assert saved["x"]["access_token"] == "AT"
    assert saved["x"]["refresh_token"] == "RT"


async def test_exchange_code_rejects_mismatched_state(tmp_path):
    client = _client(tmp_path, _ok_token)
    client.authorize_url_for_login()  # 내부 _state 생성
    with pytest.raises(RuntimeError, match="state"):
        await client.exchange_code("CODE", state="not-the-real-state")


async def test_exchange_code_accepts_matching_state(tmp_path):
    client = _client(tmp_path, _ok_token)
    url = client.authorize_url_for_login()
    state = parse_qs(urlparse(url).query)["state"][0]  # authorize URL에 실린 state
    tok = await client.exchange_code("CODE", state=state)  # 일치 → 통과
    assert tok["access_token"] == "AT"


async def test_exchange_code_requires_state_when_generated(tmp_path):
    # authorize URL을 만들면 state가 필수 — code만 넘기면(state 누락) 거부(CSRF 방어 강화).
    client = _client(tmp_path, _ok_token)
    client.authorize_url_for_login()
    with pytest.raises(RuntimeError, match="state"):
        await client.exchange_code("CODE")


async def test_exchange_code_skips_state_when_not_generated(tmp_path):
    # authorize URL을 만들지 않은 흐름(self._state 없음)에서는 state 검증을 생략한다.
    client = _client(tmp_path, _ok_token)
    tok = await client.exchange_code("CODE")
    assert tok["access_token"] == "AT"


async def test_post_token_rejects_response_without_access_token(tmp_path):
    async def bad(req):
        return httpx.Response(200, json={"error": "invalid_grant"})

    client = _client(tmp_path, bad)
    url = client.authorize_url_for_login()
    state = parse_qs(urlparse(url).query)["state"][0]
    with pytest.raises(RuntimeError, match="access_token"):
        await client.exchange_code("CODE", state=state)


def test_token_store_recovers_from_corrupted_file(tmp_path):
    path = tmp_path / "cred.json"
    path.write_text("{ not valid json")
    store = TokenStore(path)
    assert store.get("svc") == {}  # 손상 → 빈 폴백(크래시 없음)
    assert (tmp_path / "cred.json.bak").exists()  # 손상본은 .bak으로 비킴
    store.update("svc", access_token="AT")  # 이후 정상 동작
    assert store.get("svc")["access_token"] == "AT"


def test_token_store_file_is_0600(tmp_path):
    path = tmp_path / "sub" / "cred.json"
    TokenStore(path).update("svc", access_token="AT")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_token_store_update_is_atomic_and_leaves_no_temp(tmp_path):
    d = tmp_path / "sub"
    store = TokenStore(d / "cred.json")
    store.update("svc", access_token="AT")
    store.update("svc2", refresh_token="RT")  # 두 번째 갱신은 기존과 병합
    files = sorted(p.name for p in d.iterdir())
    assert files == ["cred.json"]  # 임시 파일(.credentials-*.tmp) 잔재 없음
    saved = json.loads((d / "cred.json").read_text())
    assert saved["svc"]["access_token"] == "AT"
    assert saved["svc2"]["refresh_token"] == "RT"
