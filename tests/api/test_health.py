"""
Tests for health check endpoints.

Tests basic API availability and health status.
"""

import pytest


class TestHealthEndpoints:
    """Test health check and basic API endpoints."""

    def test_root_endpoint(self, test_client):
        """Test that the root endpoint returns a response."""
        response = test_client.get("/")
        assert response.status_code == 200

    def test_health_check(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy" or "status" in str(data).lower()

    def test_api_docs_available(self, test_client):
        """Test that API documentation is accessible."""
        response = test_client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json(self, test_client):
        """Test that OpenAPI schema is available."""
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        assert "info" in data
