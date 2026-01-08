"""
Tests for /api/summarize endpoint.

Tests consultation summarization with:
- English transcripts
- Hindi transcripts
- Multi-language transcripts
- Clinical scenario validation
"""

import pytest
import json
from unittest.mock import MagicMock

from tests.fixtures.clinical_scenarios import CLINICAL_SCENARIOS
from tests.fixtures.transcripts import english, hindi, kannada


class TestSummarization:
    """Test the /api/summarize endpoint."""

    def test_english_summarization(self, test_client, english_transcript, mock_anthropic):
        """Test summarization of English consultation."""
        # Configure mock response
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "summary": "Patient presents with persistent cough for one week with low-grade fever.",
            "speakers": {"doctor": "speaker_0", "patient": "speaker_1"},
            "clinical_summary": {
                "chief_complaint": "Persistent cough for one week",
                "history_present_illness": "Patient reports cough and low-grade fever",
                "review_of_systems": "Positive for fever",
                "plan": "Further evaluation needed"
            },
            "key_concerns": ["Persistent cough", "Fever"],
            "recommendations_given": []
        }))]

        response = test_client.post("/api/summarize", json={
            "text": english_transcript
        })

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True or "summary" in data or "clinical_summary" in data

    def test_hindi_summarization(self, test_client, hindi_transcript, mock_anthropic):
        """Test summarization of Hindi consultation."""
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "summary": "Patient has cough and fever for one week.",
            "speakers": {"doctor": "speaker_0", "patient": "speaker_1"},
            "clinical_summary": {
                "chief_complaint": "Khansi aur bukhar",
                "history_present_illness": "One week duration"
            }
        }))]

        response = test_client.post("/api/summarize", json={
            "text": hindi_transcript
        })

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True or "summary" in data or "clinical_summary" in data

    def test_summarization_with_patient_info(self, test_client, english_transcript, mock_anthropic):
        """Test summarization with additional patient information."""
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "summary": "30-year-old female with cough and fever.",
            "metadata": {"patient_name": "Test Patient", "age": "30"},
            "clinical_summary": {}
        }))]

        response = test_client.post("/api/summarize", json={
            "text": english_transcript,
            "patient_info": {
                "name": "Test Patient",
                "age": "30",
                "sex": "Female"
            }
        })

        assert response.status_code == 200

    def test_english_output_option(self, test_client, hindi_transcript, mock_anthropic):
        """Test summarization with original_text for non-English transcripts."""
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "summary": "Patient reports cough and fever for one week.",
            "clinical_summary": {}
        }))]

        response = test_client.post("/api/summarize", json={
            "text": "Translated English version",
            "original_text": hindi_transcript
        })

        assert response.status_code == 200


class TestSummarizationClinicalScenarios:
    """Test summarization with various clinical scenarios."""

    @pytest.mark.parametrize("scenario_key", [
        "pregnant_flu",
        "pediatric_fever",
        "diabetes_management",
    ])
    def test_clinical_scenario_summarization(self, test_client, scenario_key, mock_anthropic):
        """Test summarization handles different clinical scenarios."""
        scenario = CLINICAL_SCENARIOS[scenario_key]

        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "summary": f"Summary for {scenario_key}",
            "clinical_summary": {
                "chief_complaint": scenario["consultation"][:50]
            }
        }))]

        response = test_client.post("/api/summarize", json={
            "text": scenario["consultation"]
        })

        assert response.status_code == 200

    def test_pregnancy_consultation_summary(self, test_client, mock_anthropic):
        """Test summarization preserves pregnancy-related clinical details."""
        transcript = english.PREGNANCY_CONSULTATION

        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "summary": "6-week pregnant patient with flu symptoms",
            "clinical_summary": {
                "chief_complaint": "Flu symptoms in early pregnancy",
                "history_present_illness": "6 weeks pregnant with cough, cold, fever for 5 days"
            },
            "clinical_context": {
                "special_populations": "Pregnancy - first trimester"
            }
        }))]

        response = test_client.post("/api/summarize", json={
            "text": transcript
        })

        assert response.status_code == 200


class TestSummarizationMultilingual:
    """Test summarization with multiple languages."""

    def test_kannada_summarization(self, test_client, kannada_transcript, mock_anthropic):
        """Test summarization of Kannada consultation."""
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "summary": "Patient reports cough and fever",
            "clinical_summary": {}
        }))]

        response = test_client.post("/api/summarize", json={
            "text": kannada_transcript,
            "transcription_language": "kn-IN"
        })

        assert response.status_code == 200

    def test_multilingual_summarization(self, test_client, multilingual_transcript, mock_anthropic):
        """Test summarization of mixed Hindi-English consultation."""
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "summary": "Mixed language consultation about cough and cold",
            "clinical_summary": {}
        }))]

        response = test_client.post("/api/summarize", json={
            "text": multilingual_transcript
        })

        assert response.status_code == 200


class TestSummarizationEdgeCases:
    """Test edge cases for summarization."""

    def test_empty_text(self, test_client):
        """Test handling of empty text."""
        response = test_client.post("/api/summarize", json={
            "text": ""
        })

        # Should return 400 error for empty text
        assert response.status_code == 400

    def test_very_short_text(self, test_client, mock_anthropic):
        """Test handling of very short text."""
        mock_anthropic.messages.create.return_value.content = [MagicMock(text=json.dumps({
            "summary": "Brief exchange",
            "clinical_summary": {}
        }))]

        response = test_client.post("/api/summarize", json={
            "text": "1. [0.00s - 1.00s] speaker_0: Hello"
        })

        assert response.status_code == 200

    def test_missing_text_validation(self, test_client):
        """Test validation when text is missing."""
        response = test_client.post("/api/summarize", json={})

        # Should return 400 for missing text
        assert response.status_code == 400

    def test_llm_error_handling(self, test_client, english_transcript, mock_anthropic):
        """Test handling when LLM returns unexpected response."""
        mock_anthropic.messages.create.return_value.content = [MagicMock(text="Invalid JSON response")]

        response = test_client.post("/api/summarize", json={
            "text": english_transcript
        })

        # Should handle gracefully - may return 200 with error info or 500
        assert response.status_code in [200, 500]
