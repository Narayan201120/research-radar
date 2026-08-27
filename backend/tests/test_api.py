from tests.helpers import add_author, add_paper, add_similarity, add_topic


def _seed(client, session):
    cv = add_topic(session, "computer-vision")
    nlp = add_topic(session, "large-language-models")
    ada = add_author(session, "Ada Lovelace")
    alan = add_author(session, "Alan Turing")

    attention = add_paper(
        session,
        "Attention Is All You Need",
        abstract="The dominant sequence transduction models base on attention mechanisms.",
        year=2025,
        cited_by_count=6600,
        authors=[ada],
        topics=[nlp],
    )
    llama = add_paper(
        session,
        "LLaMA: Open and Efficient Foundation Language Models",
        abstract="We introduce LLaMA, a collection of large language models.",
        year=2023,
        cited_by_count=3942,
        authors=[alan],
        topics=[nlp],
    )
    yolo = add_paper(
        session,
        "You Only Look Once: Real-Time Object Detection",
        abstract="We present real-time object detection using a single convolutional network.",
        year=2024,
        cited_by_count=1200,
        authors=[ada, alan],
        topics=[cv],
    )
    cnn = add_paper(
        session,
        "Very Deep Convolutional Networks",
        abstract="Depth of a convolutional network improves image classification accuracy.",
        year=2023,
        authors=[],
        topics=[cv],
    )
    add_similarity(session, attention.id, llama.id, 0.87654321)
    add_similarity(session, attention.id, yolo.id, 0.12)
    session.commit()
    return {
        "attention": attention,
        "llama": llama,
        "yolo": yolo,
        "cnn": cnn,
        "cv": cv,
        "nlp": nlp,
        "ada": ada,
        "alan": alan,
    }


def test_list_defaults(client, session):
    data = _seed(client, session)
    response = client.get("/papers")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["items"]) == 4
    assert body["items"][0]["id"] == data["attention"].id  # 2025 first (year desc)
    assert [p["publication_year"] for p in body["items"]] == [2025, 2024, 2023, 2023]
    assert body["items"][2]["id"] == data["cnn"].id  # id desc breaks 2023 tie
    assert body["items"][3]["id"] == data["llama"].id


def test_list_shape(client, session):
    data = _seed(client, session)
    item = client.get("/papers?q=attention&page_size=1").json()["items"][0]
    assert item["id"] == data["attention"].id
    assert item["title"] == "Attention Is All You Need"
    assert item["publication_year"] == 2025
    assert item["cited_by_count"] == 6600
    assert item["authors"] == [{"id": data["ada"].id, "name": "Ada Lovelace"}]


def test_author_filter_client_and_multiple(client, session):
    data = _seed(client, session)
    only_alan = client.get("/papers?author=alan").json()
    assert only_alan["total"] == 2
    both = client.get("/papers?author=Lovelace").json()
    assert both["total"] == 2


def test_topic_filter(client, session):
    data = _seed(client, session)
    cv = client.get(f"/papers?topic={data['cv'].slug}").json()
    assert cv["total"] == 2
    nlp = client.get(f"/papers?topic={data['nlp'].slug}").json()
    assert nlp["total"] == 2


def test_year_filter(client, session):
    _seed(client, session)
    body = client.get("/papers?year=2024").json()
    assert body["total"] == 1
    assert [p["title"] for p in body["items"]] == [
        "You Only Look Once: Real-Time Object Detection"
    ]


def test_keyword_search_matches_title_or_abstract(client, session):
    _seed(client, session)
    by_title = client.get("/papers?q=LLaMA").json()
    assert by_title["total"] == 1
    by_abstract = client.get("/papers?q=segmentation").json()
    assert by_abstract["total"] == 0


def test_keyword_search_all_terms_required(client, session):
    _seed(client, session)
    both = client.get("/papers?q=attention+mechanisms").json()
    assert both["total"] == 1
    one = client.get("/papers?q=attention+yocto").json()
    assert one["total"] == 0


def test_combined_filters(client, session):
    data = _seed(client, session)
    body = client.get(
        f"/papers?q=attention&topic={data['nlp'].slug}&year=2025"
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Attention Is All You Need"


def test_pagination_boundaries(client, session):
    _seed(client, session)
    page_one = client.get("/papers?page=1&page_size=2").json()
    page_two = client.get("/papers?page=2&page_size=2").json()
    assert len(page_one["items"]) == 2
    assert len(page_two["items"]) == 2
    assert {i["id"] for i in page_one["items"]}.isdisjoint(
        {i["id"] for i in page_two["items"]}
    )
    assert client.get("/papers?page=3&page_size=2").json()["items"] == []


def test_validation_errors(client, session):
    _seed(client, session)
    assert client.get("/papers?page=0").status_code == 422
    assert client.get("/papers?page_size=0").status_code == 422
    assert client.get("/papers?page_size=101").status_code == 422


def test_like_escaping_percent(client, session):
    add_paper(
        session,
        "C++ Template Metaprogramming: 100% sure",
        abstract="generics and templates",
    )
    session.commit()
    wildcard = client.get("/papers?q=100%").json()
    assert wildcard["total"] == 1
    literal = client.get("/papers?q=x100x").json()
    assert literal["total"] == 0


def test_like_escaping_underscore_is_literal(client, session):
    add_paper(session, "foo_bar system", abstract="underscore in title")
    session.commit()
    body = client.get("/papers?q=foo_bar").json()
    assert body["total"] == 1


def test_detail_endpoint(client, session):
    data = _seed(client, session)
    detail = client.get(f"/papers/{data['attention'].id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == data["attention"].id
    assert body["title"] == "Attention Is All You Need"
    assert body["abstract"] is not None
    assert body["publication_year"] == 2025
    assert body["doi"] is None
    assert body["cited_by_count"] == 6600
    assert body["topics"] == [
        {"id": data["nlp"].id, "name": "Large Language Models", "slug": data["nlp"].slug}
    ]
    assert body["authors"] == [{"id": data["ada"].id, "name": "Ada Lovelace"}]


def test_detail_404_for_unknown_and_non_int(client, session):
    _seed(client, session)
    assert client.get("/papers/9999").status_code == 404
    assert client.get("/papers/abc").status_code == 404
    assert client.get("/papers/-1").status_code == 404


def test_similar_returns_sorted_and_rounded(client, session):
    data = _seed(client, session)
    assert client.get(f"/papers/{data['cnn'].id + 10}/similar").status_code == 404
    assert client.get("/papers/abc/similar").status_code == 404

    similar = client.get(f"/papers/{data['attention'].id}/similar")
    assert similar.status_code == 200
    body = similar.json()
    assert len(body) == 2
    assert body[0]["id"] == data["llama"].id
    assert body[0]["similarity_score"] == 0.8765
    assert body[0]["title"] == "LLaMA: Open and Efficient Foundation Language Models"
    assert body[1]["id"] == data["yolo"].id
    assert body[1]["similarity_score"] == 0.12


def test_similar_returns_empty_for_paper_without_neighbors(client, session):
    data = _seed(client, session)
    body = client.get(f"/papers/{data['llama'].id}/similar").json()
    assert body == []


def test_similar_falls_back_to_snapshot_where_vector_sql_unsupported(client, session):
    """Documents the dialect guard: on SQLite (no <=> operator) a stored vector
    is ignored and the legacy snapshot serves the response unchanged."""
    from sqlalchemy import text as sql_text

    data = _seed(client, session)
    session.execute(
        sql_text(
            "INSERT INTO paper_embedding (paper_id, embedding) VALUES (:pid, :emb)"
        ),
        {"pid": data["attention"].id, "emb": "[0.1,0.2]"},
    )
    session.commit()

    similar = client.get(f"/papers/{data['attention'].id}/similar")
    assert similar.status_code == 200
    body = similar.json()
    assert body[0]["similarity_score"] == 0.8765  # legacy snapshot values
    assert body[0]["id"] == data["llama"].id


def test_similar_404s_before_any_vector_lookup(client, session):
    assert client.get("/papers/999999/similar").status_code == 404
    assert client.get("/papers/abc/similar").status_code == 404


def test_ranked_requires_q(client):
    response = client.get("/papers?ranked=true")
    assert response.status_code == 422


def test_ranked_false_matches_default_behavior(client, session):
    _seed(client, session)
    default = client.get("/papers?q=attention").json()
    explicit = client.get("/papers?q=attention&ranked=false").json()
    assert default == explicit


def test_ranked_degrades_to_legacy_on_non_postgres(client, session):
    """Documents the dialect guard: SQLite has no pg_search, so ranked=true
    with q serves the legacy ILIKE result set instead of erroring."""
    data = _seed(client, session)
    legacy = client.get("/papers?q=attention").json()
    ranked = client.get("/papers?q=attention&ranked=true").json()
    assert ranked["total"] == legacy["total"]
    assert {item["id"] for item in ranked["items"]} >= {data["attention"].id}


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_503_when_database_unreachable(client):
    from app.api.deps import get_db
    from app.main import app

    class _DeadSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("connection refused")

    app.dependency_overrides[get_db] = lambda: _DeadSession()
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "unreachable"}