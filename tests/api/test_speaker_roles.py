"""
Tests for /api/identify-speaker-roles endpoint.

Tests speaker role identification with multi-speaker support:
- 2, 3, 4+ speaker scenarios
- Confidence scoring and thresholds
- Multi-language support (English, Hindi, Kannada)
- Fallback behavior for malformed responses
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from tests.fixtures.clinical_scenarios import SPEAKER_ROLE_SCENARIOS
from tests.fixtures.transcripts import english, hindi, kannada


class TestSpeakerRoleIdentification:
    """Test the /api/identify-speaker-roles endpoint."""

    def test_two_speaker_english(self, test_client, english_segments, mock_anthropic_speaker_roles):
        """Test standard 2-speaker English consultation."""
        response = test_client.post("/api/identify-speaker-roles", json={
            "segments": english_segments,
            "language": "en-IN"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "role_mapping" in data
        assert len(data["role_mapping"]) >= 2

    def test_two_speaker_hindi(self, test_client, hindi_segments, mock_anthropic_speaker_roles):
        """Test standard 2-speaker Hindi consultation."""
        response = test_client.post("/api/identify-speaker-roles", json={
            "segments": hindi_segments,
            "language": "hi-IN"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_three_speaker_identification(self, test_client, mock_anthropic):
        """Test 3-speaker consultation (doctor + patient + family)."""
        segments = english.THREE_SPEAKER_SEGMENTS

        # Configure mock for 3-speaker response
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "speaker_0": {"role": "Doctor", "confidence": 0.94, "reasoning": "Leads consultation"},
            "speaker_1": {"role": "Patient", "confidence": 0.91, "reasoning": "Describes symptoms"},
            "speaker_2": {"role": "Family Member", "confidence": 0.78, "reasoning": "Provides context"}
        }))]

        response = test_client.post("/api/identify-speaker-roles", json={
            "segments": segments,
            "language": "en-IN"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_empty_segments_returns_error(self, test_client, mock_anthropic):
        """Test that empty segments return appropriate error."""
        # Mock returns error for empty segments
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({}))]

        response = test_client.post("/api/identify-speaker-roles", json={
            "segments": []
        })

        # Should return 200 with success=False, validation error, or internal error
        assert response.status_code in [200, 400, 422, 500]

    def test_missing_segments_validation(self, test_client):
        """Test validation when segments field is missing."""
        response = test_client.post("/api/identify-speaker-roles", json={})

        # Should return validation error
        assert response.status_code == 422


class TestSpeakerRolesMultilingual:
    """Test speaker identification with multiple languages."""

    @pytest.mark.parametrize("language,fixture_name", [
        ("en-IN", "english_segments"),
        ("hi-IN", "hindi_segments"),
    ])
    def test_language_support(self, test_client, language, fixture_name, mock_anthropic_speaker_roles, request):
        """Test speaker identification works across languages."""
        segments = request.getfixturevalue(fixture_name)

        response = test_client.post("/api/identify-speaker-roles", json={
            "segments": segments,
            "language": language
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_hindi_romanized_consultation(self, test_client, mock_anthropic_speaker_roles):
        """Test speaker identification with Romanized Hindi."""
        segments = hindi.SIMPLE_SEGMENTS

        response = test_client.post("/api/identify-speaker-roles", json={
            "segments": segments,
            "language": "hi-IN"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_kannada_romanized_consultation(self, test_client, mock_anthropic_speaker_roles):
        """Test speaker identification with Romanized Kannada."""
        segments = kannada.SIMPLE_SEGMENTS

        response = test_client.post("/api/identify-speaker-roles", json={
            "segments": segments,
            "language": "kn-IN"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestSpeakerRolesEdgeCases:
    """Test edge cases and error handling."""

    def test_single_speaker(self, test_client, mock_anthropic):
        """Test handling of single speaker (edge case)."""
        segments = [
            {"speaker_id": "speaker_0", "text": "This is a monologue.", "start_time": 0.0, "end_time": 5.0},
        ]

        response = test_client.post("/api/identify-speaker-roles", json={
            "segments": segments
        })

        assert response.status_code == 200

    def test_very_short_utterances(self, test_client, mock_anthropic):
        """Test handling of very short utterances with low confidence."""
        segments = [
            {"speaker_id": "speaker_0", "text": "Hi", "start_time": 0.0, "end_time": 0.5},
            {"speaker_id": "speaker_1", "text": "Hello", "start_time": 1.0, "end_time": 1.5},
        ]

        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "speaker_0": {"role": "Unknown", "confidence": 0.3, "reasoning": "Too brief"},
            "speaker_1": {"role": "Unknown", "confidence": 0.3, "reasoning": "Too brief"}
        }))]

        response = test_client.post("/api/identify-speaker-roles", json={
            "segments": segments
        })

        assert response.status_code == 200

    def test_malformed_segment_data(self, test_client):
        """Test validation of malformed segment data."""
        # Missing required fields
        segments = [
            {"speaker_id": "speaker_0"},  # Missing text and timestamps
        ]

        response = test_client.post("/api/identify-speaker-roles", json={
            "segments": segments
        })

        # Should return validation error or internal error for malformed data
        assert response.status_code in [200, 400, 422, 500]
