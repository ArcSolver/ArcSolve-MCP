# Changelog

이 프로젝트의 주요 변경 사항. Keep a Changelog 형식 · SemVer 준수.

<!-- BEGIN UNRELEASED -->
## [Unreleased]

- **core**: 레지스트리 지연·격리 로딩(한 서비스 오류가 전체를 죽이지 않음, 선택 서비스만 import)
- **core**: auth 레지스트리 일반화(`Service.make_auth_client`) — 새 OAuth 서비스가 코어 수정 없이 인증
- **core**: OAuth PKCE(S256) + 토큰 파일 0600/디렉토리 0700
- **core**: 공통 HTTP 동사 추가(`get_json`/`post_json`) + 의존성 격리 규칙
- **core**: provenance 강제 테스트 + GitHub Actions CI(pytest·ruff·카탈로그/체인지로그 drift)
- **core**: LICENSE(Apache-2.0)·CONTRIBUTING 추가
- **discord**: Webhook 메시지 전송 MCP 추가 — `discord_send_message`
- **kakao**: '나에게 보내기' MCP 추가 — `kakao_send_text_to_me`, `kakao_send_link_to_me`
- **line**: LINE Messaging API push 텍스트 MCP 추가 — `line_send_text`
- **repo**: README 상단 배지(CI · License · Python) 추가, 저장소 public 공개
- **telegram**: sendMessage 기반 telegram_send_message 추가
<!-- END UNRELEASED -->
