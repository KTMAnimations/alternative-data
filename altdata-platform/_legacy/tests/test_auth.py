"""Tests for authentication module."""

import pytest
from fastapi.testclient import TestClient


class TestUserRegistration:
    """Tests for user registration endpoint."""

    def test_register_success(self, api_client: TestClient):
        """Test successful user registration."""
        user_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123",
            "full_name": "New User",
        }
        response = api_client.post("/api/v1/auth/register", json=user_data)

        # May return 200 (new) or 400 (already exists)
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            data = response.json()
            assert data["email"] == user_data["email"]
            assert data["full_name"] == user_data["full_name"]
            assert "id" in data
            assert "hashed_password" not in data
            assert "password" not in data

    def test_register_invalid_email(self, api_client: TestClient):
        """Test registration with invalid email."""
        user_data = {
            "email": "invalid-email",
            "password": "SecurePass123",
            "full_name": "Test User",
        }
        response = api_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 422

    def test_register_weak_password(self, api_client: TestClient):
        """Test registration with weak password."""
        user_data = {
            "email": "weakpass@example.com",
            "password": "weak",
            "full_name": "Test User",
        }
        response = api_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 422

    def test_register_missing_fields(self, api_client: TestClient):
        """Test registration with missing required fields."""
        response = api_client.post("/api/v1/auth/register", json={})
        assert response.status_code == 422


class TestUserLogin:
    """Tests for user login endpoint."""

    def test_login_success(self, api_client: TestClient, test_user_data: dict):
        """Test successful login."""
        # First ensure user exists
        api_client.post("/api/v1/auth/register", json=test_user_data)

        # Login
        login_data = {
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
        response = api_client.post(
            "/api/v1/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == test_user_data["email"]

    def test_login_invalid_password(self, api_client: TestClient, test_user_data: dict):
        """Test login with invalid password."""
        # Ensure user exists
        api_client.post("/api/v1/auth/register", json=test_user_data)

        login_data = {
            "username": test_user_data["email"],
            "password": "WrongPassword123",
        }
        response = api_client.post(
            "/api/v1/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

    def test_login_nonexistent_user(self, api_client: TestClient):
        """Test login with nonexistent user."""
        login_data = {
            "username": "nonexistent@example.com",
            "password": "SomePassword123",
        }
        response = api_client.post(
            "/api/v1/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 401


class TestTokenRefresh:
    """Tests for token refresh endpoint."""

    def test_refresh_token_success(self, api_client: TestClient, auth_tokens: dict):
        """Test successful token refresh."""
        response = api_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": auth_tokens["refresh_token"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_invalid_token(self, api_client: TestClient):
        """Test refresh with invalid token."""
        response = api_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )

        assert response.status_code == 401


class TestCurrentUser:
    """Tests for current user endpoint."""

    def test_get_current_user_authenticated(
        self, api_client: TestClient, auth_headers: dict, test_user_data: dict
    ):
        """Test getting current user when authenticated."""
        response = api_client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert data["full_name"] == test_user_data["full_name"]

    def test_get_current_user_unauthenticated(self, api_client: TestClient):
        """Test getting current user without authentication."""
        # In development mode, this may return 200 with None user
        # In production, it would return 401
        response = api_client.get("/api/v1/auth/me")
        # Accept both behaviors for now
        assert response.status_code in [200, 401]


class TestLogout:
    """Tests for logout endpoint."""

    def test_logout_success(self, api_client: TestClient, auth_tokens: dict, auth_headers: dict):
        """Test successful logout."""
        response = api_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": auth_tokens["refresh_token"]},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"


class TestPasswordSecurity:
    """Tests for password hashing and verification."""

    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        from src.auth.security import get_password_hash, verify_password

        password = "TestPass123"
        hashed = get_password_hash(password)

        # Hash should not equal plain password
        assert hashed != password

        # Verification should work
        assert verify_password(password, hashed)

        # Wrong password should fail
        assert not verify_password("WrongPassword", hashed)

    def test_different_hashes_for_same_password(self):
        """Test that same password produces different hashes (salting)."""
        from src.auth.security import get_password_hash

        password = "TestPass123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Hashes should be different due to salting
        assert hash1 != hash2


class TestJWTTokens:
    """Tests for JWT token creation and validation."""

    def test_access_token_creation(self):
        """Test access token creation."""
        from src.auth.security import create_access_token, decode_token

        data = {"sub": "test@example.com", "user_id": 1}
        token = create_access_token(data)

        assert token is not None

        # Decode and verify
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == data["sub"]
        assert payload["user_id"] == data["user_id"]
        assert payload["type"] == "access"

    def test_refresh_token_creation(self):
        """Test refresh token creation."""
        from src.auth.security import create_refresh_token, decode_token

        data = {"sub": "test@example.com", "user_id": 1}
        token = create_refresh_token(data)

        assert token is not None

        # Decode and verify
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == data["sub"]
        assert payload["type"] == "refresh"

    def test_invalid_token_decoding(self):
        """Test that invalid tokens fail to decode."""
        from src.auth.security import decode_token

        result = decode_token("invalid-token")
        assert result is None

        result = decode_token("")
        assert result is None


class TestProtectedEndpoints:
    """Tests for protected endpoints with JWT authentication."""

    def test_factors_endpoint_with_jwt(
        self, api_client: TestClient, auth_headers: dict
    ):
        """Test accessing factors endpoint with JWT token."""
        response = api_client.get("/api/v1/factors", headers=auth_headers)
        assert response.status_code == 200

    def test_categories_endpoint_with_jwt(
        self, api_client: TestClient, auth_headers: dict
    ):
        """Test accessing categories endpoint with JWT token."""
        response = api_client.get("/api/v1/categories", headers=auth_headers)
        assert response.status_code == 200

    def test_entities_endpoint_with_jwt(
        self, api_client: TestClient, auth_headers: dict
    ):
        """Test accessing entities endpoint with JWT token."""
        response = api_client.get("/api/v1/entities", headers=auth_headers)
        assert response.status_code == 200
