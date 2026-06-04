# messaging-routing (메시징 라우팅)

알림/메시지를 **적절한 채널로 라우팅**하고 플랫폼별로 포맷하는 **다중 서비스 오케스트레이션** 스킬:
Kakao(나에게)·Telegram(텍스트/사진/문서)·Discord(메시지/임베드)·LINE(push/multicast/broadcast)를
청중 모델에 맞춰 고른다. 이 도구들은 **전송**하므로 경계(확인 후 전송)를 지킨다.

> 이 스킬은 상류 API를 직접 치지 않고 **ArcSolve MCP 도구를 오케스트레이션**한다(AGENTS.md 규칙 2-2).
> 검증된 계약은 각 서비스의 `contract.py`에 단일 출처로 남는다.

## 계약 출처 (공식 문서)
스킬이 기대는 MCP 서비스들의 검증된 계약:
- Kakao 메시지(나에게 보내기): https://developers.kakao.com/docs/latest/ko/kakaotalk-message/rest-api
- Telegram Bot API: https://core.telegram.org/bots/api
- Discord Webhook: https://discord.com/developers/docs/resources/webhook
- LINE Messaging API: https://developers.line.biz/en/reference/messaging-api/

## 필요 MCP 도구
ArcSolve MCP 서버에서 아래 도구가 노출돼 있어야 한다(`SKILL.md`의 `allowed-tools`와 일치):
- Kakao — `kakao_send_text_to_me`, `kakao_send_link_to_me`
- Telegram — `telegram_send_message`, `telegram_send_photo`, `telegram_send_document`
- Discord — `discord_send_message`, `discord_send_embed`
- LINE — `line_send_text`, `line_multicast_text`, `line_broadcast_text`

> 셋업: `arcsolve serve kakao telegram discord line`(쓰는 채널만 선택해도 됨). 각 서비스 자격증명이
> 필요하다(각 서비스 README의 환경변수 참고). 자격증명이 없는 채널은 라우팅 후보에서 제외된다.

## 범위 / 경계
- **포함**: 청중에 맞는 채널 선택 + 플랫폼별 포맷(Discord 임베드·Telegram 미디어 첨부·길이 제한 준수) + (확인된) 다채널 fan-out.
- **전송 행위 — 사전 확인 필수**: 수신자/채널·내용을 확인하고 전송한다. **broadcast/multicast(LINE broadcast는 전 구독자)는 반드시 사용자 확인 후**. 무단·대량(스팸) 전송 금지.
- **인바운드/리플라이 없음**: 능동 전송만. 웹훅 수신·reply token 흐름은 다루지 않는다.
- **플랫폼 스코프 준수**: Kakao MVP는 '나에게 보내기' 한정(친구에게 X). 사용자가 준 내용을 포맷·라우팅할 뿐 카피를 창작하거나 수신자를 지어내지 않는다.

## 품질 검증
- 정적 테스트: [`tests/test_messaging_routing_skill.py`](../../tests/test_messaging_routing_skill.py)
  — frontmatter·`allowed-tools`↔실재 도구·다중 채널 교차 불변식.
- eval: [`evals/`](evals/) — skill-creator 하니스(비결정적, pytest CI와 별개).
