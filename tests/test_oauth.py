"""OAuth PKCE + 토큰 저장소 권한 검증 (네트워크 없음)."""

import json
import os
import stat
from urllib.parse import parse_qs

import httpx

from arcsolve.oauth import OAuthClient, TokenStore


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

    await client.exchange_code("CODE")
    assert seen.get("grant_type") == "authorization_code"
    assert seen.get("code_verifier")  # PKCE verifier가 토큰 교환에 포함됨

    saved = json.loads((tmp_path / "cred.json").read_text())
    assert saved["x"]["access_token"] == "AT"
    assert saved["x"]["refresh_token"] == "RT"


def test_token_store_file_is_0600(tmp_path):
    path = tmp_path / "sub" / "cred.json"
    TokenStore(path).update("svc", access_token="AT")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
