"""
Integration tests for external services.

These tests hit real APIs and verify connectivity and API key validity.
Run with: pytest tests/integration/ -v -m integration

Note: These tests consume API credits. Run sparingly.
"""

import os
import pytest
import httpx


@pytest.mark.integration
@pytest.mark.external_service
class TestSarvamAPI:
    """Test Sarvam AI API connectivity and key validity."""

    @pytest.fixture
    def sarvam_api_key(self):
        """Get Sarvam API key from environment."""
        key = os.getenv("SARVAM_API_KEY")
        if not key:
            pytest.skip("SARVAM_API_KEY not set")
        return key

    def test_sarvam_api_key_valid(self, sarvam_api_key):
        """Test that the Sarvam API key is valid using transliteration endpoint."""
        # Use the transliterate endpoint - it's lightweight and cheap
        response = httpx.post(
            "https://api.sarvam.ai/transliterate",
            headers={
                "api-subscription-key": sarvam_api_key,
                "Content-Type": "application/json"
            },
            json={
                "input": "namaste",
                "source_language_code": "en-IN",
                "target_language_code": "hi-IN"
            },
            timeout=30.0
        )

        # Check response
        assert response.status_code == 200, f"API returned {response.status_code}: {response.text}"
        data = response.json()
        assert "transliterated_text" in data or "output" in data, f"Unexpected response: {data}"
        print(f"Sarvam API working - transliterated 'namaste' to: {data}")

    def test_sarvam_hindi_transliteration(self, sarvam_api_key):
        """Test Sarvam transliteration from Devanagari to Roman."""
        response = httpx.post(
            "https://api.sarvam.ai/transliterate",
            headers={
                "api-subscription-key": sarvam_api_key,
                "Content-Type": "application/json"
            },
            json={
                "input": "नमस्ते",
                "source_language_code": "hi-IN",
                "target_language_code": "en-IN"
            },
            timeout=30.0
        )

        assert response.status_code == 200, f"API returned {response.status_code}: {response.text}"
        data = response.json()
        assert "transliterated_text" in data, f"Unexpected response: {data}"
        print(f"Hindi to Roman transliteration: नमस्ते -> {data['transliterated_text']}")

    def test_sarvam_translation(self, sarvam_api_key):
        """Test Sarvam translation endpoint."""
        response = httpx.post(
            "https://api.sarvam.ai/translate",
            headers={
                "api-subscription-key": sarvam_api_key,
                "Content-Type": "application/json"
            },
            json={
                "input": "Hello, how are you?",
                "source_language_code": "en-IN",
                "target_language_code": "hi-IN"
            },
            timeout=30.0
        )

        assert response.status_code == 200, f"API returned {response.status_code}: {response.text}"
        data = response.json()
        assert "translated_text" in data, f"Unexpected response: {data}"
        print(f"Sarvam translation: 'Hello, how are you?' -> {data['translated_text']}")


@pytest.mark.integration
@pytest.mark.external_service
class TestAnthropicAPI:
    """Test Anthropic API connectivity and key validity."""

    @pytest.fixture
    def anthropic_api_key(self):
        """Get Anthropic API key from environment."""
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            pytest.skip("ANTHROPIC_API_KEY not set")
        return key

    def test_anthropic_api_key_valid(self, anthropic_api_key):
        """Test that the Anthropic API key is valid with a minimal request."""
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hi"}]
            },
            timeout=30.0
        )

        assert response.status_code == 200, f"API returned {response.status_code}: {response.text}"
        data = response.json()
        assert "content" in data, f"Unexpected response: {data}"
        print(f"Anthropic API working - response: {data['content'][0]['text']}")


@pytest.mark.integration
@pytest.mark.external_service
class TestElevenLabsAPI:
    """Test ElevenLabs API connectivity and key validity."""

    @pytest.fixture
    def elevenlabs_api_key(self):
        """Get ElevenLabs API key from environment."""
        key = os.getenv("ELEVENLABS_API_KEY")
        if not key:
            pytest.skip("ELEVENLABS_API_KEY not set")
        return key

    def test_elevenlabs_api_key_valid(self, elevenlabs_api_key):
        """Test that the ElevenLabs API key is valid by listing models."""
        # Use models endpoint which has broader permissions
        response = httpx.get(
            "https://api.elevenlabs.io/v1/models",
            headers={
                "xi-api-key": elevenlabs_api_key
            },
            timeout=30.0
        )

        # 200 = success, 401 with "missing_permissions" means key is valid but limited
        if response.status_code == 401:
            data = response.json()
            if "missing_permissions" in str(data):
                print(f"ElevenLabs API key is valid but has limited permissions: {data}")
                # Key is valid, just limited permissions - this is OK for scoped keys
                return
            else:
                pytest.fail(f"ElevenLabs API key is invalid: {data}")

        assert response.status_code == 200, f"API returned {response.status_code}: {response.text}"
        data = response.json()
        print(f"ElevenLabs models available: {len(data) if isinstance(data, list) else 'unknown'}")

    def test_elevenlabs_subscription_info(self, elevenlabs_api_key):
        """Test fetching subscription info (may fail if key lacks user_read permission)."""
        response = httpx.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={
                "xi-api-key": elevenlabs_api_key
            },
            timeout=30.0
        )

        if response.status_code == 401:
            data = response.json()
            if "missing_permissions" in str(data):
                pytest.skip(f"API key lacks user_read permission: {data}")
            pytest.fail(f"API key invalid: {data}")

        assert response.status_code == 200, f"API returned {response.status_code}: {response.text}"
        data = response.json()

        # Extract useful subscription info
        character_count = data.get("character_count", 0)
        character_limit = data.get("character_limit", 0)
        tier = data.get("tier", "unknown")

        print(f"ElevenLabs subscription: tier={tier}, used={character_count}/{character_limit} characters")
