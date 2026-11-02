import pytest
import uuid
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_auth_full_flow():
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecretPassword123!"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Inscription réussie
        res_reg = await client.post(
            "/api/v1/auth/register",
            json={"email": unique_email, "password": password},
        )
        assert res_reg.status_code == 201
        reg_data = res_reg.json()
        assert reg_data["email"] == unique_email
        assert reg_data["role"] == "journalist"
        assert reg_data["is_active"] is True
        assert "id" in reg_data

        # 2. Inscription avec email déjà existant (doit retourner 409)
        res_dup = await client.post(
            "/api/v1/auth/register",
            json={"email": unique_email, "password": password},
        )
        assert res_dup.status_code == 409

        # 3. Connexion réussie avec JSON
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"email": unique_email, "password": password},
        )
        assert res_login.status_code == 200
        login_data = res_login.json()
        assert "access_token" in login_data
        assert login_data["token_type"] == "bearer"
        assert login_data["user"]["email"] == unique_email
        token = login_data["access_token"]

        # 4. Connexion avec mot de passe incorrect (doit retourner 401)
        res_bad_pw = await client.post(
            "/api/v1/auth/login",
            json={"email": unique_email, "password": "WrongPassword!"},
        )
        assert res_bad_pw.status_code == 401

        # 5. Connexion via formulaire OAuth2 /token (Swagger UI)
        res_token = await client.post(
            "/api/v1/auth/token",
            data={"username": unique_email, "password": password},
        )
        assert res_token.status_code == 200
        assert "access_token" in res_token.json()

        # 6. Récupération du profil /me avec le Bearer token
        res_me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_me.status_code == 200
        assert res_me.json()["email"] == unique_email

        # 7. Tolérance préfixe "Bearer Bearer ..."
        res_me_tolerant = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer Bearer {token}"},
        )
        assert res_me_tolerant.status_code == 200

        # 8. Accès à /me sans token (401)
        res_me_unauth = await client.get("/api/v1/auth/me")
        assert res_me_unauth.status_code == 401


@pytest.mark.asyncio
async def test_cors_preflight():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") in ["*", "http://localhost:3000"]
