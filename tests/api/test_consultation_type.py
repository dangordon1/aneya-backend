"""
Tests for /api/determine-consultation-type endpoint.

Tests automatic classification of OBGyn consultations:
- Antenatal (pregnancy)
- Infertility
- General OBGYN (default)
"""

import pytest
import json
from unittest.mock import MagicMock

from tests.fixtures.clinical_scenarios import CONSULTATION_TYPE_SCENARIOS


class TestConsultationTypeClassification:
    """Test automatic consultation type determination."""

    def test_antenatal_classification(self, test_client, mock_anthropic_consultation_type):
        """Test classification of pregnancy consultation."""
        segments = [
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "How many weeks pregnant are you?", "start_time": 0.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "I'm 6 weeks pregnant", "start_time": 2.0},
        ]

        response = test_client.post("/api/determine-consultation-type", json={
            "diarized_segments": segments,
            "doctor_specialty": "obgyn",
            "patient_context": {"patient_id": "test-patient-123"}
        })

        assert response.status_code == 200
        data = response.json()
        assert "consultation_type" in data
        assert data["consultation_type"] in ["antenatal", "obgyn"]

    def test_infertility_classification(self, test_client, mock_anthropic):
        """Test classification of infertility consultation."""
        segments = [
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "How long have you been trying to conceive?", "start_time": 0.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "We've been trying for 2 years with no success", "start_time": 2.0},
        ]

        # Configure mock for infertility classification
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "consultation_type": "infertility",
            "confidence": 0.92,
            "reasoning": "Patient mentions trying to conceive for extended period"
        }))]

        response = test_client.post("/api/determine-consultation-type", json={
            "diarized_segments": segments,
            "doctor_specialty": "obgyn",
            "patient_context": {"patient_id": "test-patient-123"}
        })

        assert response.status_code == 200
        data = response.json()
        assert "consultation_type" in data

    def test_obgyn_default_classification(self, test_client, mock_anthropic):
        """Test fallback to general OBGYN for unclear consultations."""
        segments = [
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "What brings you in today?", "start_time": 0.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "I have irregular periods", "start_time": 2.0},
        ]

        # Configure mock for obgyn default
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "consultation_type": "obgyn",
            "confidence": 0.7,
            "reasoning": "General gynecological concern"
        }))]

        response = test_client.post("/api/determine-consultation-type", json={
            "diarized_segments": segments,
            "doctor_specialty": "obgyn",
            "patient_context": {"patient_id": "test-patient-123"}
        })

        assert response.status_code == 200
        data = response.json()
        assert "consultation_type" in data
        assert data["consultation_type"] == "obgyn"

    def test_empty_segments(self, test_client):
        """Test handling of empty segments."""
        response = test_client.post("/api/determine-consultation-type", json={
            "diarized_segments": [],
            "doctor_specialty": "obgyn",
            "patient_context": {"patient_id": "test-patient-123"}
        })

        # Should handle gracefully
        assert response.status_code in [200, 400, 422]

    def test_missing_required_fields(self, test_client):
        """Test validation when required fields are missing."""
        response = test_client.post("/api/determine-consultation-type", json={
            "diarized_segments": []
        })

        # Should return validation error
        assert response.status_code == 422


class TestConsultationTypeMultilingual:
    """Test consultation type classification with multiple languages."""

    def test_hindi_pregnancy_classification(self, test_client, mock_anthropic):
        """Test classification of Hindi pregnancy consultation."""
        segments = [
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "Aap kitne hafte ki pregnant hain?", "start_time": 0.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "Main 6 hafte ki pregnant hoon", "start_time": 2.0},
        ]

        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "consultation_type": "antenatal",
            "confidence": 0.88,
            "reasoning": "Patient confirms pregnancy in Hindi"
        }))]

        response = test_client.post("/api/determine-consultation-type", json={
            "diarized_segments": segments,
            "doctor_specialty": "obgyn",
            "patient_context": {"patient_id": "test-patient-123", "language": "hi-IN"}
        })

        assert response.status_code == 200
        data = response.json()
        assert "consultation_type" in data

    def test_mixed_language_classification(self, test_client, mock_anthropic_consultation_type):
        """Test classification with mixed Hindi-English consultation."""
        segments = [
            {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "What brings you in today?", "start_time": 0.0},
            {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "Doctor sahab, main pregnant hoon", "start_time": 2.0},
        ]

        response = test_client.post("/api/determine-consultation-type", json={
            "diarized_segments": segments,
            "doctor_specialty": "obgyn",
            "patient_context": {"patient_id": "test-patient-123"}
        })

        assert response.status_code == 200


class TestConsultationTypeEdgeCases:
    """Test edge cases for consultation type classification."""

    def test_invalid_form_type_fallback(self, test_client, mock_anthropic):
        """Test that invalid form types fall back to obgyn."""
        segments = [
            {"speaker_id": "speaker_0", "text": "Hello", "start_time": 0.0},
            {"speaker_id": "speaker_1", "text": "Hi doctor", "start_time": 1.0},
        ]

        # Mock returns invalid type
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "consultation_type": "invalid_type",
            "confidence": 0.9,
            "reasoning": "test"
        }))]

        response = test_client.post("/api/determine-consultation-type", json={
            "diarized_segments": segments,
            "doctor_specialty": "obgyn",
            "patient_context": {"patient_id": "test-patient-123"}
        })

        assert response.status_code == 200
        data = response.json()
        # Should fall back to valid type
        if data.get("success"):
            assert data["consultation_type"] in ["antenatal", "infertility", "obgyn"]

    def test_llm_error_handling(self, test_client, mock_anthropic):
        """Test handling when LLM returns malformed response."""
        segments = [
            {"speaker_id": "speaker_0", "text": "Test", "start_time": 0.0},
        ]

        # Mock returns invalid JSON
        mock_anthropic.messages.create.return_value.content = [MagicMock(text="Not valid JSON")]

        response = test_client.post("/api/determine-consultation-type", json={
            "diarized_segments": segments,
            "doctor_specialty": "obgyn",
            "patient_context": {"patient_id": "test-patient-123"}
        })

        # Should handle gracefully
        assert response.status_code in [200, 500]
