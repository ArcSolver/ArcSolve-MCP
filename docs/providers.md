# 구현 대상 매니페스트 (Providers)

구현할 MCP의 **단일 진실 목록**. 각 블록이 한 서비스이고, 그 안의 공식 문서 링크가 계약 구현의
근거가 된다. 병렬 작업 시 에이전트는 **자기 블록만 읽고**, 구현은 자기 `services/<name>/` 폴더에만 쓴다.

> 작성 규칙은 [AGENTS.md](../AGENTS.md). 새 대상은 아래 **블록 템플릿**을 복사해 추가한다.

**상태 범례**: `planned`(대상 확정) · `in-progress`(구현 중) · `done`(검증 완료)

---

## kakao — 카카오톡 메시지(나에게 보내기)
- 상태: `done`
- 인증: OAuth 2.0 (scope: `talk_message`)
- 공식 문서:
  - 메시지 REST API: https://developers.kakao.com/docs/latest/ko/kakaotalk-message/rest-api
  - 메시지 템플릿(text 등): https://developers.kakao.com/docs/latest/ko/message-template/common
  - 카카오 로그인(토큰): https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api
- 도구:
  - `kakao_send_text_to_me` — 텍스트(≤200자) 나에게 전송
  - `kakao_send_link_to_me` — URL 스크랩(미리보기) 나에게 전송
- 스코프(MVP): 포함 = '나에게 보내기'(memo). 제외 = '친구에게'(권한 신청 + 소셜 API 필요 → v2)

---

## 블록 템플릿 (복사해서 새 대상 추가)

```markdown
## <name> — <한 줄 설명>
- 상태: planned
- 인증: OAuth(scope: ...) | API key | none
- 공식 문서:
  - API 레퍼런스: <url>
  - 인증/토큰: <url>
  - 스키마/오브젝트: <url>
- 도구:
  - `<name>_<action>` — <설명>
- 스코프(MVP): 포함 = ... / 제외 = ...
```

> 채울 때 주의: 모든 링크는 **공식 provider 문서**여야 한다(블로그·서드파티 금지). 엔드포인트·필드
> 규격이 그 링크에서 확인되지 않으면 `planned` 상태로 두고 비워둔다 — 구현 단계에서 환각 방지.
