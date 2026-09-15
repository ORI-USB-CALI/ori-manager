import pytest

from backend.core.security import get_password_hash
from backend.models.session import Session as DBSessionModel
from backend.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("secret123"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def inactive_user(db):
    user = User(
        email="inactive@example.com",
        hashed_password=get_password_hash("secret123"),
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_login_success(client, test_user):
    """CA-01: Authenticate with valid credentials."""
    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "secret123"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Login successful"}
    assert "session_id" in response.cookies


def test_login_invalid_credentials(client, test_user):
    """CA-02: Reject with invalid credentials."""
    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "session_id" not in response.cookies


def test_login_inactive_user(client, inactive_user):
    """CA-04: Prevent access if user is inactive."""
    response = client.post(
        "/api/auth/login",
        json={"email": "inactive@example.com", "password": "secret123"},
    )
    assert response.status_code == 403
    assert "session_id" not in response.cookies


def test_access_protected_route_success(client, test_user):
    # Login first
    client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "secret123"},
    )
    
    # Access protected route
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["is_active"] is True


def test_access_protected_route_invalid_session(client):
    """CA-07: Reject access with invalid session."""
    client.cookies.set("session_id", "invalid-token")
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_logout(client, test_user, db):
    """CA-08: Terminate session on logout and invalidate it."""
    # Login
    client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "secret123"},
    )
    
    token = client.cookies.get("session_id")
    assert token is not None
    
    # Logout
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    
    # Verify session is invalid in DB
    session_db = db.query(DBSessionModel).filter_by(token=token).first()
    assert session_db is not None
    assert session_db.is_valid is False
    
    # Try accessing protected route
    response = client.get("/api/auth/me")
    assert response.status_code == 401
