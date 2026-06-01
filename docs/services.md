# 서비스 카탈로그

> ⚙️ 자동 생성 — 직접 수정하지 마세요. `arcsolve-mcp catalog`로 재생성됩니다.

현재 **5개 서비스 · 총 27개 도구**.

## discord — Discord — Webhook으로 채널에 메시지 전송
공식 문서: https://discord.com/developers/docs/resources/webhook

| 도구 | 설명 |
|------|------|
| `discord_create_message` | Bot 토큰으로 임의 채널에 메시지를 전송한다. |
| `discord_delete_message` | Webhook이 보낸 기존 메시지를 삭제한다. |
| `discord_edit_message` | Webhook이 보낸 기존 메시지를 편집한다(본문 교체). |
| `discord_list_messages` | Bot 토큰으로 채널의 최근 메시지를 조회한다. |
| `discord_send_embed` | Discord 채널에 Webhook으로 리치 임베드(카드) 1개를 전송한다. |
| `discord_send_message` | Discord 채널에 Webhook으로 메시지를 전송한다. |

## kakao — 카카오톡 메시지 — 나에게 보내기
공식 문서: https://developers.kakao.com/docs/latest/ko/kakaotalk-message/rest-api

| 도구 | 설명 |
|------|------|
| `kakao_send_link_to_me` | 카카오톡 '나에게 보내기'로 URL을 스크랩(미리보기 카드) 형태로 전송한다. |
| `kakao_send_text_to_me` | 카카오톡 '나에게 보내기'로 텍스트 메시지를 전송한다. |

## line — LINE Messaging API — 텍스트 메시지 전송(push/reply/multicast/broadcast) + 프로필 조회
공식 문서: https://developers.line.biz/en/reference/messaging-api/

| 도구 | 설명 |
|------|------|
| `line_broadcast_text` | LINE Messaging API broadcast로 모든 친구에게 텍스트 1건을 전송한다. |
| `line_get_profile` | LINE Messaging API로 사용자 프로필 정보를 조회한다. |
| `line_multicast_text` | LINE Messaging API multicast로 동일 텍스트를 여러 userId에게 전송한다. |
| `line_reply_text` | LINE Messaging API reply로 텍스트 메시지 1건을 회신한다. |
| `line_send_text` | LINE Messaging API push로 텍스트 메시지 1건을 전송한다. |

## telegram — Telegram Bot API — 텍스트/사진/문서 전송, 메시지 편집·삭제, getMe 헬스체크
공식 문서: https://core.telegram.org/bots/api

| 도구 | 설명 |
|------|------|
| `telegram_delete_message` | 봇이 접근 가능한 메시지를 삭제한다(deleteMessage). |
| `telegram_edit_message_text` | 메시지의 텍스트를 편집한다(editMessageText). |
| `telegram_get_me` | 봇 신원/토큰 유효성을 확인한다(getMe). 헬스체크용. 파라미터 없음. |
| `telegram_send_document` | Telegram 봇으로 문서(파일)를 전송한다(sendDocument). |
| `telegram_send_message` | Telegram 봇으로 텍스트 메시지를 전송한다(sendMessage). |
| `telegram_send_photo` | Telegram 봇으로 사진을 전송한다(sendPhoto). |

## zotero — Zotero 라이브러리 읽기(Web API v3 + 로컬 데스크톱 API)
공식 문서: https://www.zotero.org/support/dev/web_api/v3/basics

| 도구 | 설명 |
|------|------|
| `zotero_get_collection_items` | 컬렉션의 아이템을 나열한다(GET /{prefix}/collections/{collectionKey}/items). |
| `zotero_get_fulltext` | 첨부 아이템의 전문(full-text)을 조회한다(GET /{prefix}/items/{itemKey}/fulltext). |
| `zotero_get_item` | 단일 아이템을 조회한다(GET /{prefix}/items/{itemKey}). |
| `zotero_get_item_children` | 아이템의 자식(노트/첨부)을 나열한다(GET /{prefix}/items/{itemKey}/children). |
| `zotero_health` | 백엔드 연결/설정 상태를 점검한다. |
| `zotero_list_collections` | 컬렉션을 나열한다(GET /{prefix}/collections, top=True면 /collections/top). |
| `zotero_list_tags` | 라이브러리의 태그를 나열한다(GET /{prefix}/tags). |
| `zotero_search_items` | Zotero 라이브러리에서 아이템을 검색/나열한다(GET /{prefix}/items). |

