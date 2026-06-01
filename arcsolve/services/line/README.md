# LINE 서비스

LINE Messaging API의 **텍스트 메시지 전송(push/reply/multicast/broadcast) + 프로필 조회** 래퍼.

## 계약 출처 (공식 문서)
- Messaging API 레퍼런스: https://developers.line.biz/en/reference/messaging-api/
- Send push message: https://developers.line.biz/en/reference/messaging-api/#send-push-message
- Send reply message: https://developers.line.biz/en/reference/messaging-api/#send-reply-message
- Send multicast message: https://developers.line.biz/en/reference/messaging-api/#send-multicast-message
- Send broadcast message: https://developers.line.biz/en/reference/messaging-api/#send-broadcast-message
- Get profile: https://developers.line.biz/en/reference/messaging-api/#get-profile
- Text message object: https://developers.line.biz/en/reference/messaging-api/#text-message
- 채널 액세스 토큰: https://developers.line.biz/en/docs/messaging-api/channel-access-tokens/

> 계약 본체는 [`contract.py`](contract.py)에 코드로 박제되어 있다(엔드포인트·요청/응답 모델·제약).

## 엔드포인트
| 종류 | METHOD · PATH | 성공 응답 |
|------|------|------|
| push 메시지 | `POST /v2/bot/message/push` | `{sentMessages:[…]}` |
| reply 메시지 | `POST /v2/bot/message/reply` | `{sentMessages:[…]}` |
| multicast 메시지 | `POST /v2/bot/message/multicast` | 빈 객체 `{}` |
| broadcast 메시지 | `POST /v2/bot/message/broadcast` | 빈 객체 `{}` |
| 프로필 조회 | `GET /v2/bot/profile/{userId}` | `Profile` 객체 |

Base: `https://api.line.me` · 인증: `Authorization: Bearer {channel access token}` · Content-Type: `application/json`(POST)

> **응답 형태는 엔드포인트별로 공식 확인**: push/reply는 `sentMessages[]`, multicast/broadcast는 빈 객체 `{}`를 반환한다(문서 "Returns status code 200 and an empty JSON object").

## 셋업
1. [LINE Developers 콘솔](https://developers.line.biz)에서 **Messaging API 채널** 생성
2. **채널 액세스 토큰**(long-lived) 발급
3. `.env`에 작성:
   - `LINE_CHANNEL_ACCESS_TOKEN=<발급한 토큰>`
   - `LINE_TO=<기본 수신자 userId/groupId/roomId>` (선택 — 인자로 덮어쓰기 가능)

> 인터랙티브 OAuth가 아니므로 `arcsolve-mcp auth line` 단계는 없다(토큰을 env로 직접 받는다).

## 도구
| 도구 | 설명 |
|------|------|
| `line_send_text(text, to?)` | 텍스트(≤5000자) push 1건. `to` 미지정 시 `LINE_TO` 사용 |
| `line_reply_text(reply_token, text)` | webhook의 reply_token으로 텍스트 회신. 토큰은 1회용·곧 만료 |
| `line_multicast_text(to, text)` | userId 배열(1~**500**개)에 동일 텍스트 전송. groupId/roomId 불가 |
| `line_broadcast_text(text)` | 모든 친구에게 텍스트 전송 |
| `line_get_profile(user_id)` | userId의 프로필(displayName/userId/+선택 필드) 조회 |

## 범위 / 제약
- 텍스트 메시지의 **push/reply/multicast/broadcast** + **프로필 조회**까지 지원. 그 외 메시지 타입(이미지·스티커 등)·narrowcast·그룹 멤버 프로필 등은 추후 동일 패턴으로 확장.
- `reply_token`은 webhook 이벤트에서만 얻을 수 있다(우리 webhook 서버는 범위 밖 — 호출자가 전달).

### 요청/텍스트 필드 (공식 계약)
| 필드 | 적용 | 필수 | 비고 |
|------|------|------|------|
| `to` | push | 필수 | 수신자 `userId`/`groupId`/`roomId` |
| `to` | multicast | 필수 | `userId` 배열, 최대 **500개**(groupId/roomId 불가) |
| `replyToken` | reply | 필수 | webhook 이벤트의 1회용 토큰 |
| `messages` | push/reply/multicast/broadcast | 필수 | 메시지 배열, 최대 **5개** |
| `notificationDisabled` | 전부(broadcast 포함) | 선택 | `true`면 푸시 알림 미수신 |
| `messages[].type` | 전부 | 필수 | `"text"` 고정 |
| `messages[].text` | 전부 | 필수 | 최대 **5000자**(UTF-16 코드 유닛 기준) |

### Profile 응답 필드 (공식 계약, Get profile)
| 필드 | 항상 포함 | 비고 |
|------|------|------|
| `displayName` | 예 | 표시 이름 |
| `userId` | 예 | 사용자 ID |
| `pictureUrl` | 아니오 | 프로필 이미지 URL(없으면 미포함) |
| `statusMessage` | 아니오 | 상태 메시지(없으면 미포함) |
| `language` | 아니오 | BCP 47 언어 태그(개인정보 미동의 시 미포함) |

## 확장 포인트
- 다른 메시지 타입(image / sticker / location / template 등): `contract.py`에 모델 추가 → `tools.py`에 도구 추가.
- narrowcast(`/v2/bot/message/narrowcast`), 그룹/멀티퍼슨 멤버 프로필(`/v2/bot/group|room/.../member/...`) 등: 동일 패턴으로 엔드포인트·도구 추가.
- `customAggregationUnits`, `emojis`, `quoteToken` 등 선택 필드 노출.
