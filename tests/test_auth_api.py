import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
def test_auth_api_register_and_login():
    client = APIClient()

    # 1. Register new user
    res = client.post(
        "/api/v1/auth/register/",
        {
            "username": "student1",
            "email": "student1@example.com",
            "password": "strongpassword123",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "student1"
    assert data["email"] == "student1@example.com"

    # 2. Check /auth/me/
    res_me = client.get("/api/v1/auth/me/")
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "student1"

    # 3. Logout
    res_logout = client.post("/api/v1/auth/logout/")
    assert res_logout.status_code == 200

    # 4. /auth/me/ now 403
    res_me2 = client.get("/api/v1/auth/me/")
    assert res_me2.status_code == 403

    # 5. Login
    res_login = client.post(
        "/api/v1/auth/login/",
        {"username": "student1", "password": "strongpassword123"},
    )
    assert res_login.status_code == 200
    assert res_login.json()["username"] == "student1"


@pytest.mark.django_db
def test_auth_api_invalid_login():
    client = APIClient()
    res = client.post(
        "/api/v1/auth/login/",
        {"username": "nonexistent", "password": "wrongpassword"},
    )
    assert res.status_code == 401
