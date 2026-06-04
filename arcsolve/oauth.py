"""범용 OAuth 2.0 (authorization code + PKCE + refresh) 클라이언트 + 토큰 저장소.

서비스별 URL/스코프/자격증명만 주입하면 그대로 재사용된다.
※ 여기서 다루는 것은 '상류 서비스(카카오 등)에 대한 인증'이다.
   MCP 클라이언트↔서버 간 transport 인증(스펙의 OAuth 2.1)과 혼동하지 말 것.

보안:
- 토큰 저장 파일은 0600, 디렉토리는 0700으로 권한을 좁힌다(평문 저장이므로 최소 방어).
- 공개 클라이언트(client_secret 없음) 인가코드 흐름에 PKCE(S256)를 적용한다.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import httpx

DEFAULT_STORE = Path.home() / ".arcsolve" / "credentials.json"
_TIMEOUT = 10.0


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


class TokenStore:
    """서비스별 토큰을 JSON 파일 하나에 보관한다(평문, 권한 0600)."""

    def __init__(self, path: Path = DEFAULT_STORE):
        self.path = path

    def _read(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {}

    def get(self, service: str) -> dict:
        return self._read().get(service, {})

    def update(self, service: str, **fields) -> None:
        data = self._read()
        data.setdefault(service, {}).update(fields)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass


@dataclass
class OAuthClient:
    service: str
    token_url: str
    authorize_url: str
    client_id: str
    scopes: list[str]
    redirect_uri: str = "https://localhost"
    client_secret: str | None = None
    env_refresh_token: str | None = None  # 환경변수로 직접 주입된 refresh token
    store: TokenStore = field(default_factory=TokenStore)
    transport: httpx.BaseTransport | None = None  # 테스트 주입용
    _verifier: str | None = field(default=None, init=False, repr=False)

    async def access_token(self) -> str:
        """유효한 access token을 반환한다. 만료(또는 부재) 시 refresh로 자동 갱신."""
        rec = self.store.get(self.service)
        if rec.get("access_token") and rec.get("expires_at", 0) > time.time() + 60:
            return rec["access_token"]

        refresh = rec.get("refresh_token") or self.env_refresh_token
        if not refresh:
            raise RuntimeError(
                f"{self.service}: 인증이 필요합니다. `arcsolve auth {self.service}`를 실행하세요."
            )
        tok = await self._post_token(
            {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": refresh,
            }
        )
        self._save(tok, fallback_refresh=refresh)
        return tok["access_token"]

    async def exchange_code(self, code: str) -> dict:
        """authorization code를 토큰으로 교환하고 저장한다(최초 1회 인증)."""
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        if self._verifier:  # PKCE
            data["code_verifier"] = self._verifier
        tok = await self._post_token(data)
        self._save(tok)
        return tok

    def authorize_url_for_login(self) -> str:
        verifier, challenge = _pkce_pair()
        self._verifier = verifier
        query = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.scopes),
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": secrets.token_urlsafe(16),
            }
        )
        return f"{self.authorize_url}?{query}"

    async def _post_token(self, data: dict) -> dict:
        if self.client_secret:
            data = {**data, "client_secret": self.client_secret}
        async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self.transport) as client:
            r = await client.post(self.token_url, data=data)
        r.raise_for_status()
        return r.json()

    def _save(self, tok: dict, fallback_refresh: str | None = None) -> None:
        # 일부 제공자는 refresh 시 새 refresh_token을 주지 않는다 → 기존 값 유지.
        self.store.update(
            self.service,
            access_token=tok["access_token"],
            refresh_token=tok.get("refresh_token", fallback_refresh),
            expires_at=time.time() + tok.get("expires_in", 0),
        )
