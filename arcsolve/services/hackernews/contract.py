"""Hacker News 읽기 계약(contract) — Firebase(공식 데이터) + Algolia(검색).

상류 API의 '진실'만 담는다 — 엔드포인트 상수·랭킹 매핑·검증·JSON→pydantic 모델.
MCP/네트워크 무의존(순수 상수 + pydantic + stdlib). 전부 GET·읽기·**무인증**(키 없음).

두 공식 API를 합성한다:
  - **Firebase**(구조적 데이터): 아이템 단건·사용자·프론트페이지 랭킹. JSON.
  - **Algolia HN Search**(전문 검색): 관련도순/시간순 검색. JSON.

출처(공식 문서):
  - Firebase API: https://github.com/HackerNews/API
  - Algolia HN Search API: https://hn.algolia.com/api
"""

from __future__ import annotations

import html as _htmllib
import re

from pydantic import BaseModel

# ─── Firebase 엔드포인트(공식) ──────────────────────────────
# 출처: HackerNews/API README ("https://hacker-news.firebaseio.com/v0/...").
FIREBASE_BASE = "https://hacker-news.firebaseio.com/v0"


def item_url(item_id: int) -> str:
    """아이템 단건 — GET /v0/item/{id}.json. 출처: README ("Items")."""
    return f"{FIREBASE_BASE}/item/{item_id}.json"


def user_url(user_id: str) -> str:
    """사용자 — GET /v0/user/{id}.json. 출처: README ("Users")."""
    return f"{FIREBASE_BASE}/user/{user_id}.json"


# 랭킹 종류 → 엔드포인트 파일명. 출처: README (topstories/newstories/beststories/
# askstories/showstories/jobstories; top/new ≤500, ask/show/job ≤200).
RANKINGS: dict[str, str] = {
    "top": "topstories",
    "new": "newstories",
    "best": "beststories",
    "ask": "askstories",
    "show": "showstories",
    "job": "jobstories",
}


def ranking_url(kind: str) -> str:
    """랭킹 리스트 — GET /v0/{kind}stories.json (id 배열). 출처: README."""
    return f"{FIREBASE_BASE}/{RANKINGS[kind]}.json"


# ─── Algolia HN Search 엔드포인트(공식) ─────────────────────
# 출처: hn.algolia.com/api ("/search" relevance, "/search_by_date" date desc).
ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
ALGOLIA_SEARCH = f"{ALGOLIA_BASE}/search"  # 관련도(→점수→댓글수)순
ALGOLIA_SEARCH_BY_DATE = f"{ALGOLIA_BASE}/search_by_date"  # 최신순

# Algolia 쿼리 파라미터명(공식). 출처: hn.algolia.com/api.
PARAM_QUERY = "query"
PARAM_TAGS = "tags"
PARAM_HITS_PER_PAGE = "hitsPerPage"
PARAM_PAGE = "page"

# ─── 제약 상수 ──────────────────────────────────────────────
DEFAULT_LIMIT = 10
MAX_SEARCH_LIMIT = 50  # Algolia hitsPerPage 상한(보수적)
MAX_RANK_LIMIT = 50  # 랭킹은 N+1 fetch라 상한 보수적(top/new 원천은 ≤500)


def validate_ranking(kind: str) -> str:
    """랭킹 종류를 top/new/best/ask/show/job로 검증한다(위반 시 ValueError)."""
    if kind not in RANKINGS:
        raise ValueError(
            f"kind는 {tuple(RANKINGS)} 중 하나여야 합니다(현재 {kind!r})."
        )
    return kind


def validate_limit(limit: int, *, maximum: int) -> int:
    """limit를 1..maximum로 검증한다(위반 시 ValueError)."""
    if limit < 1 or limit > maximum:
        raise ValueError(f"limit는 1..{maximum} 범위여야 합니다(현재 {limit}).")
    return limit


# ─── 텍스트 헬퍼 ─────────────────────────────────────────────
# HN의 title/text/about은 HTML(엔티티·<p>·<a>)을 담는다 → 평문화.
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_html(raw: str | None, *, limit: int | None = None) -> str | None:
    """HTML 태그 제거 + 엔티티 복원 + 공백 정리. limit 넘으면 자른다(없으면 None)."""
    if not raw:
        return None
    text = _TAG_RE.sub(" ", raw)
    text = _htmllib.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return None
    if limit and len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


# ─── Firebase 응답 모델 ─────────────────────────────────────
# 출처: README (item/user 필드표). extra는 무시, 확신 필드만 모델링.


class HNItem(BaseModel):
    """아이템(story/comment/job/poll/pollopt) — 부분 모델.

    출처: README item 필드(id·type·by·time·text·title·url·score·descendants·kids·parent·
    deleted·dead).
    """

    id: int
    type: str | None = None
    by: str | None = None
    time: int | None = None  # unix timestamp
    text: str | None = None  # HTML
    title: str | None = None  # HTML
    url: str | None = None
    score: int | None = None
    descendants: int | None = None  # 총 댓글 수(story/poll)
    kids: list[int] = []
    parent: int | None = None
    deleted: bool | None = None
    dead: bool | None = None


class HNUser(BaseModel):
    """사용자 — 부분 모델. 출처: README user 필드(id·created·karma·about·submitted)."""

    id: str
    created: int | None = None  # unix timestamp
    karma: int | None = None
    about: str | None = None  # HTML
    submitted: list[int] = []


# ─── Algolia 응답 모델 ──────────────────────────────────────
# 출처: hn.algolia.com/api (hit 필드: objectID·title·url·author·points·num_comments·
# created_at·created_at_i·story_text·comment_text·_tags).


class AlgoliaHit(BaseModel):
    """검색 결과 1건 — 부분 모델."""

    objectID: str
    title: str | None = None
    url: str | None = None
    author: str | None = None
    points: int | None = None
    num_comments: int | None = None
    created_at: str | None = None  # ISO8601 문자열
    story_text: str | None = None
    comment_text: str | None = None


class AlgoliaResult(BaseModel):
    """검색 응답 — hits + 페이지 메타."""

    hits: list[AlgoliaHit] = []
    nbHits: int | None = None
    page: int | None = None
    nbPages: int | None = None


def item_permalink(item_id: int | str) -> str:
    """HN 웹 퍼머링크(news.ycombinator.com/item?id=). 출처: HN 사이트 URL 규칙."""
    return f"https://news.ycombinator.com/item?id={item_id}"
