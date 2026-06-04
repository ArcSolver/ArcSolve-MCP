"""hackernews 계약 검증 — Firebase/Algolia 모델·랭킹 매핑·검증·텍스트 정리, 네트워크 없음."""

import pytest

from arcsolve.services.hackernews import contract as c

STORY = {
    "id": 8863,
    "type": "story",
    "by": "dhouston",
    "time": 1175714200,
    "title": "My YC app: Dropbox",
    "url": "http://www.getdropbox.com/u/2/screencast.html",
    "score": 111,
    "descendants": 71,
    "kids": [9224, 8917],
}


def test_hnitem_story():
    it = c.HNItem.model_validate(STORY)
    assert it.id == 8863 and it.type == "story" and it.score == 111
    assert it.descendants == 71 and it.kids == [9224, 8917]
    assert it.by == "dhouston"


def test_hnitem_partial_comment():
    it = c.HNItem.model_validate({"id": 1, "type": "comment", "parent": 9, "text": "hi"})
    assert it.type == "comment" and it.parent == 9 and it.title is None


def test_hnuser():
    u = c.HNUser.model_validate(
        {"id": "pg", "created": 1160418092, "karma": 155111, "submitted": [1, 2, 3]}
    )
    assert u.id == "pg" and u.karma == 155111 and len(u.submitted) == 3


def test_algolia_result():
    body = {
        "hits": [
            {"objectID": "8863", "title": "Dropbox", "author": "dhouston",
             "points": 111, "num_comments": 71}
        ],
        "nbHits": 1,
        "nbPages": 1,
    }
    r = c.AlgoliaResult.model_validate(body)
    assert r.nbHits == 1 and len(r.hits) == 1
    assert r.hits[0].objectID == "8863" and r.hits[0].points == 111


def test_ranking_mapping():
    assert c.ranking_url("top").endswith("/topstories.json")
    assert c.ranking_url("ask").endswith("/askstories.json")
    assert c.ranking_url("job").endswith("/jobstories.json")
    assert c.validate_ranking("best") == "best"
    with pytest.raises(ValueError):
        c.validate_ranking("nope")


def test_validate_limit():
    assert c.validate_limit(10, maximum=50) == 10
    with pytest.raises(ValueError):
        c.validate_limit(0, maximum=50)
    with pytest.raises(ValueError):
        c.validate_limit(51, maximum=50)


def test_clean_html():
    assert c.clean_html("<p>a &amp; b</p>") == "a & b"
    assert c.clean_html(None) is None
    assert c.clean_html("   ") is None
    long = "y" * 600
    assert c.clean_html(long, limit=500).endswith("…")


def test_urls():
    assert c.item_url(8863).endswith("/item/8863.json")
    assert c.user_url("pg").endswith("/user/pg.json")
    assert "id=8863" in c.item_permalink(8863)
