from arcsolve.service import Service
from arcsolve.services.kakao.tools import make_oauth_client, register

SERVICE = Service(
    name="kakao",
    register=register,
    docs_url="https://developers.kakao.com/docs/latest/ko/kakaotalk-message/rest-api",
    summary="카카오톡 메시지 — 나에게 보내기",
    make_auth_client=make_oauth_client,
)
