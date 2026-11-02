import pytest
import uuid
from httpx import ASGITransport, AsyncClient

from app.main import app


async def get_authenticated_client():
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    unique_email = f"journalist_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPassword123!"

    # 1. Register
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": password},
    )
    assert reg_res.status_code == 201

    # 2. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers, unique_email


@pytest.mark.asyncio
async def test_editorial_full_workflow():
    client, headers, email = await get_authenticated_client()

    # 1. Create Draft Article
    create_payload = {
        "title": "Enquête exclusive sur la désinformation climatique",
        "summary": "Un décryptage complet des récentes fausses rumeurs sur le réchauffement.",
        "content": "## Introduction\n\nVoici le contenu détaillé de l'enquête éditoriale avec preuves à l'appui.",
        "fact_check_claim": "Le réchauffement climatique est un complot d'organisations secrètes.",
        "editorial_rating": "false",
        "category": "environnement",
        "tags": "climat,factcheck,science",
        "is_featured": True,
    }

    create_res = await client.post(
        "/api/v1/editorial/articles",
        json=create_payload,
        headers=headers,
    )
    assert create_res.status_code == 201
    article_data = create_res.json()
    article_id = article_data["id"]
    slug = article_data["slug"]

    assert article_data["status"] == "draft"
    assert "desinformation-climatique" in slug
    assert article_data["views_count"] == 0

    # 2. Update Draft Article
    update_res = await client.put(
        f"/api/v1/editorial/articles/{article_id}",
        json={"summary": "Résumé mis à jour par le journaliste."},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["summary"] == "Résumé mis à jour par le journaliste."

    # 3. Add an editorial review comment/note
    comment_res = await client.post(
        f"/api/v1/editorial/articles/{article_id}/comments",
        json={"comment": "Merci de vérifier les chiffres du second paragraphe."},
        headers=headers,
    )
    assert comment_res.status_code == 201
    assert comment_res.json()["comment"] == "Merci de vérifier les chiffres du second paragraphe."

    # 4. Check comments history
    get_comments_res = await client.get(
        f"/api/v1/editorial/articles/{article_id}/comments",
        headers=headers,
    )
    assert get_comments_res.status_code == 200
    comments_list = get_comments_res.json()
    assert len(comments_list) >= 1

    # 5. Submit for Review
    submit_res = await client.post(
        f"/api/v1/editorial/articles/{article_id}/submit",
        headers=headers,
    )
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "in_review"

    # 6. Review: Approve
    review_res = await client.post(
        f"/api/v1/editorial/articles/{article_id}/review",
        json={"decision": "approve", "feedback": "Excellent travail, prêt pour publication."},
        headers=headers,
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "approved"

    # 7. Publish
    publish_res = await client.post(
        f"/api/v1/editorial/articles/{article_id}/publish",
        headers=headers,
    )
    assert publish_res.status_code == 200
    assert publish_res.json()["status"] == "published"
    assert publish_res.json()["published_at"] is not None

    # 8. Public Access (without auth token) to published article
    public_res = await client.get(f"/api/v1/editorial/articles/{slug}")
    assert public_res.status_code == 200
    assert public_res.json()["id"] == article_id
    # Views count should increment
    assert public_res.json()["views_count"] >= 1

    # 9. List published articles (public)
    public_list_res = await client.get("/api/v1/editorial/articles")
    assert public_list_res.status_code == 200
    list_data = public_list_res.json()
    assert list_data["total"] >= 1
    assert any(a["id"] == article_id for a in list_data["articles"])

    # 10. Search filter
    search_res = await client.get("/api/v1/editorial/articles?search=climatique")
    assert search_res.status_code == 200
    assert any(a["id"] == article_id for a in search_res.json()["articles"])

    # 11. Editorial Stats
    stats_res = await client.get("/api/v1/editorial/stats", headers=headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_articles"] >= 1
    assert stats["published_count"] >= 1


@pytest.mark.asyncio
async def test_editorial_draft_generation_and_delete():
    client, headers, email = await get_authenticated_client()

    # Test auto draft generation with a topic
    gen_res = await client.post(
        "/api/v1/editorial/generate-draft",
        json={
            "topic": "Madagascar cyclone alert facts",
            "category": "environnement",
        },
        headers=headers,
    )
    assert gen_res.status_code == 201
    article = gen_res.json()
    art_id = article["id"]
    assert article["status"] == "draft"
    assert "Madagascar" in article["title"]

    # Delete draft
    del_res = await client.delete(
        f"/api/v1/editorial/articles/{art_id}",
        headers=headers,
    )
    assert del_res.status_code == 204

    # Verify deleted
    get_res = await client.get(f"/api/v1/editorial/articles/{art_id}", headers=headers)
    assert get_res.status_code == 404
