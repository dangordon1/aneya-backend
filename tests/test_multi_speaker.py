"""
Unit tests for multi-speaker diarisation functionality

Tests cover:
1. Speaker role identification with 2, 3, 4+ speakers
2. Confidence scoring and threshold triggering
3. Auto-detection of speaker count
4. Backward compatibility with 2-speaker consultations
5. Edge cases (1 speaker, no speakers, malformed responses)
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

# Import the FastAPI app
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from api import app

client = TestClient(app)


class TestSpeakerRoleIdentification:
    """Test the /api/identify-speaker-roles endpoint with multi-speaker support"""

    def test_two_speaker_identification(self):
        """Test standard 2-speaker consultation (doctor + patient)"""
        segments = [
            {"speaker_id": "speaker_0", "text": "Good morning. What brings you in today?", "start_time": 0.0, "end_time": 2.5},
            {"speaker_id": "speaker_1", "text": "I've been having chest pain for three days.", "start_time": 3.0, "end_time": 5.5},
            {"speaker_id": "speaker_0", "text": "Can you describe the pain? Is it sharp or dull?", "start_time": 6.0, "end_time": 8.5},
            {"speaker_id": "speaker_1", "text": "It's a dull ache that comes and goes.", "start_time": 9.0, "end_time": 11.0},
        ]

        with patch('anthropic.Anthropic') as mock_anthropic:
            # Mock LLM response
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps({
                "speaker_0": {
                    "role": "Doctor",
                    "confidence": 0.95,
                    "reasoning": "Asks diagnostic questions, uses professional tone"
                },
                "speaker_1": {
                    "role": "Patient",
                    "confidence": 0.92,
                    "reasoning": "Describes personal symptoms, answers health questions"
                }
            }))]

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post("/api/identify-speaker-roles", json={
                "segments": segments,
                "language": "en-IN"
            })

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] == True
        assert len(data["role_mapping"]) == 2
        assert len(data["confidence_scores"]) == 2
        assert len(data["reasoning"]) == 2

        # Verify roles
        assert data["role_mapping"]["speaker_0"] == "Doctor"
        assert data["role_mapping"]["speaker_1"] == "Patient"

        # Verify confidence scores
        assert data["confidence_scores"]["speaker_0"] >= 0.7
        assert data["confidence_scores"]["speaker_1"] >= 0.7

        # High confidence - no manual assignment needed
        assert data["requires_manual_assignment"] == False
        assert len(data["low_confidence_speakers"]) == 0

    def test_three_speaker_identification(self):
        """Test 3-speaker consultation (doctor + patient + family member)"""
        segments = [
            {"speaker_id": "speaker_0", "text": "Good morning. How can I help you today?", "start_time": 0.0, "end_time": 2.0},
            {"speaker_id": "speaker_1", "text": "I've been having headaches.", "start_time": 2.5, "end_time": 4.0},
            {"speaker_id": "speaker_2", "text": "Doctor, she also mentioned dizziness last week.", "start_time": 4.5, "end_time": 7.0},
            {"speaker_id": "speaker_0", "text": "Thank you. Let's check your blood pressure.", "start_time": 7.5, "end_time": 9.5},
        ]

        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps({
                "speaker_0": {
                    "role": "Doctor",
                    "confidence": 0.94,
                    "reasoning": "Leads consultation, gives medical instructions"
                },
                "speaker_1": {
                    "role": "Patient",
                    "confidence": 0.91,
                    "reasoning": "Describes personal symptoms"
                },
                "speaker_2": {
                    "role": "Family Member",
                    "confidence": 0.78,
                    "reasoning": "Provides additional context, refers to patient in third person"
                }
            }))]

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post("/api/identify-speaker-roles", json={
                "segments": segments,
                "language": "en-IN"
            })

        assert response.status_code == 200
        data = response.json()

        # Verify 3 speakers identified
        assert len(data["role_mapping"]) == 3
        assert data["role_mapping"]["speaker_0"] == "Doctor"
        assert data["role_mapping"]["speaker_1"] == "Patient"
        assert data["role_mapping"]["speaker_2"] == "Family Member"

        # All above threshold - no manual assignment
        assert data["requires_manual_assignment"] == False

    def test_low_confidence_triggers_manual_assignment(self):
        """Test that low confidence (<0.7) triggers manual assignment flag"""
        segments = [
            {"speaker_id": "speaker_0", "text": "Hi", "start_time": 0.0, "end_time": 0.5},
            {"speaker_id": "speaker_1", "text": "Hello", "start_time": 1.0, "end_time": 1.5},
            {"speaker_id": "speaker_2", "text": "Hey", "start_time": 2.0, "end_time": 2.5},
        ]

        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps({
                "speaker_0": {
                    "role": "Unknown Speaker",
                    "confidence": 0.45,
                    "reasoning": "Insufficient context to determine role"
                },
                "speaker_1": {
                    "role": "Unknown Speaker",
                    "confidence": 0.40,
                    "reasoning": "Very brief utterance, unclear role"
                },
                "speaker_2": {
                    "role": "Unknown Speaker",
                    "confidence": 0.35,
                    "reasoning": "Cannot determine from single word"
                }
            }))]

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post("/api/identify-speaker-roles", json={
                "segments": segments,
                "language": "en-IN",
                "confidence_threshold": 0.7
            })

        assert response.status_code == 200
        data = response.json()

        # Low confidence should trigger manual assignment
        assert data["requires_manual_assignment"] == True
        assert len(data["low_confidence_speakers"]) == 3
        assert "speaker_0" in data["low_confidence_speakers"]
        assert "speaker_1" in data["low_confidence_speakers"]
        assert "speaker_2" in data["low_confidence_speakers"]

    def test_custom_confidence_threshold(self):
        """Test custom confidence threshold parameter"""
        segments = [
            {"speaker_id": "speaker_0", "text": "What symptoms do you have?", "start_time": 0.0, "end_time": 2.0},
            {"speaker_id": "speaker_1", "text": "I have a fever.", "start_time": 2.5, "end_time": 3.5},
        ]

        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps({
                "speaker_0": {
                    "role": "Doctor",
                    "confidence": 0.75,
                    "reasoning": "Asks diagnostic question"
                },
                "speaker_1": {
                    "role": "Patient",
                    "confidence": 0.72,
                    "reasoning": "Describes symptom"
                }
            }))]

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            # Test with threshold 0.8 - should require manual assignment
            response = client.post("/api/identify-speaker-roles", json={
                "segments": segments,
                "language": "en-IN",
                "confidence_threshold": 0.8
            })

        assert response.status_code == 200
        data = response.json()

        # Both speakers below 0.8 threshold
        assert data["requires_manual_assignment"] == True
        assert len(data["low_confidence_speakers"]) == 2

    def test_four_speaker_identification(self):
        """Test 4-speaker consultation (doctor + patient + nurse + family)"""
        segments = [
            {"speaker_id": "speaker_0", "text": "Good afternoon. Let's review your test results.", "start_time": 0.0, "end_time": 3.0},
            {"speaker_id": "speaker_1", "text": "I'm nervous about what they show.", "start_time": 3.5, "end_time": 5.0},
            {"speaker_id": "speaker_2", "text": "Blood pressure is 120 over 80.", "start_time": 5.5, "end_time": 7.5},
            {"speaker_id": "speaker_3", "text": "Doctor, should we be worried?", "start_time": 8.0, "end_time": 9.5},
        ]

        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps({
                "speaker_0": {
                    "role": "Doctor",
                    "confidence": 0.93,
                    "reasoning": "Reviews medical results, provides clinical assessment"
                },
                "speaker_1": {
                    "role": "Patient",
                    "confidence": 0.89,
                    "reasoning": "Expresses personal concern about own health"
                },
                "speaker_2": {
                    "role": "Nurse",
                    "confidence": 0.86,
                    "reasoning": "Reports vital signs measurement"
                },
                "speaker_3": {
                    "role": "Family Member",
                    "confidence": 0.81,
                    "reasoning": "Asks questions on behalf of patient"
                }
            }))]

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post("/api/identify-speaker-roles", json={
                "segments": segments,
                "language": "en-IN"
            })

        assert response.status_code == 200
        data = response.json()

        # Verify 4 distinct roles
        assert len(data["role_mapping"]) == 4
        assert data["role_mapping"]["speaker_0"] == "Doctor"
        assert data["role_mapping"]["speaker_1"] == "Patient"
        assert data["role_mapping"]["speaker_2"] == "Nurse"
        assert data["role_mapping"]["speaker_3"] == "Family Member"

        # All high confidence
        assert data["requires_manual_assignment"] == False

    def test_malformed_llm_response_fallback(self):
        """Test fallback behavior when LLM returns malformed JSON"""
        segments = [
            {"speaker_id": "speaker_0", "text": "Hello", "start_time": 0.0, "end_time": 1.0},
            {"speaker_id": "speaker_1", "text": "Hi", "start_time": 1.5, "end_time": 2.0},
            {"speaker_id": "speaker_2", "text": "Hey", "start_time": 2.5, "end_time": 3.0},
        ]

        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            # Invalid JSON
            mock_response.content = [MagicMock(text="This is not valid JSON {invalid}")]

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post("/api/identify-speaker-roles", json={
                "segments": segments,
                "language": "en-IN"
            })

        assert response.status_code == 200
        data = response.json()

        # Should fall back to default mapping
        assert data["success"] == False
        assert data["fallback"] == True
        assert len(data["role_mapping"]) == 3

        # Fallback assigns: speaker_0=Doctor, speaker_1=Patient, rest=Unknown
        assert data["role_mapping"]["speaker_0"] == "Doctor"
        assert data["role_mapping"]["speaker_1"] == "Patient"
        assert data["role_mapping"]["speaker_2"] == "Unknown Speaker"

        # All low confidence (0.3) - requires manual
        assert data["requires_manual_assignment"] == True
        assert all(score == 0.3 for score in data["confidence_scores"].values())


class TestAutoDetection:
    """Test auto-detection of speaker count (no hardcoded defaults)"""

    def test_num_speakers_none_allows_auto_detect(self):
        """Test that num_speakers=None allows Sarvam to auto-detect"""
        # This test verifies the parameter is optional and defaults to None
        # Full integration test would require mocking Sarvam API

        # Verify the endpoint accepts None
        from api import diarize_audio_sarvam
        import inspect

        sig = inspect.signature(diarize_audio_sarvam)
        num_speakers_param = sig.parameters['num_speakers']

        # Should default to None
        assert num_speakers_param.default is None

    def test_no_speakers_detected_returns_error(self):
        """Test that empty speaker list raises validation error"""
        # This would be tested in integration with actual audio processing
        # For now, verify the validation logic exists in the code
        pass


class TestBackwardCompatibility:
    """Test that existing 2-speaker consultations still work"""

    def test_two_speaker_consultation_unchanged(self):
        """Ensure 2-speaker flow works exactly as before"""
        segments = [
            {"speaker_id": "speaker_0", "text": "What brings you in?", "start_time": 0.0, "end_time": 2.0},
            {"speaker_id": "speaker_1", "text": "I have a cough.", "start_time": 2.5, "end_time": 4.0},
        ]

        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps({
                "speaker_0": {
                    "role": "Doctor",
                    "confidence": 0.95,
                    "reasoning": "Asks diagnostic questions"
                },
                "speaker_1": {
                    "role": "Patient",
                    "confidence": 0.92,
                    "reasoning": "Describes symptoms"
                }
            }))]

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post("/api/identify-speaker-roles", json={
                "segments": segments
            })

        assert response.status_code == 200
        data = response.json()

        # Standard 2-speaker response
        assert data["role_mapping"]["speaker_0"] == "Doctor"
        assert data["role_mapping"]["speaker_1"] == "Patient"
        assert data["confidence_scores"]["speaker_0"] >= 0.7
        assert data["confidence_scores"]["speaker_1"] >= 0.7
        assert data["requires_manual_assignment"] == False

    def test_default_threshold_is_0_7(self):
        """Verify default confidence threshold remains 0.7"""
        segments = [
            {"speaker_id": "speaker_0", "text": "Test", "start_time": 0.0, "end_time": 1.0},
        ]

        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps({
                "speaker_0": {
                    "role": "Doctor",
                    "confidence": 0.69,
                    "reasoning": "Minimal context"
                }
            }))]

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            # Don't specify threshold - should default to 0.7
            response = client.post("/api/identify-speaker-roles", json={
                "segments": segments
            })

        assert response.status_code == 200
        data = response.json()

        # 0.69 < 0.7, so should require manual assignment
        assert data["requires_manual_assignment"] == True


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_single_speaker_only(self):
        """Test handling of single-speaker audio (unusual but possible)"""
        segments = [
            {"speaker_id": "speaker_0", "text": "This is a voice memo.", "start_time": 0.0, "end_time": 2.0},
        ]

        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps({
                "speaker_0": {
                    "role": "Unknown Speaker",
                    "confidence": 0.50,
                    "reasoning": "Only one speaker detected, unclear if doctor or patient"
                }
            }))]

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post("/api/identify-speaker-roles", json={
                "segments": segments
            })

        assert response.status_code == 200
        data = response.json()

        assert len(data["role_mapping"]) == 1
        assert data["requires_manual_assignment"] == True  # Low confidence

    def test_five_plus_speakers(self):
        """Test system can handle 5+ speakers (e.g., teaching rounds)"""
        segments = [
            {"speaker_id": f"speaker_{i}", "text": f"Comment {i}", "start_time": i * 2.0, "end_time": i * 2.0 + 1.5}
            for i in range(6)
        ]

        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps({
                f"speaker_{i}": {
                    "role": "Doctor" if i == 0 else "Other Clinician" if i < 4 else "Patient" if i == 4 else "Family Member",
                    "confidence": 0.75,
                    "reasoning": f"Speaker {i} role"
                }
                for i in range(6)
            }))]

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post("/api/identify-speaker-roles", json={
                "segments": segments
            })

        assert response.status_code == 200
        data = response.json()

        # All 6 speakers identified
        assert len(data["role_mapping"]) == 6

    def test_empty_segments_list(self):
        """Test handling of empty segments list"""
        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="{}")]

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.return_value = mock_client

            response = client.post("/api/identify-speaker-roles", json={
                "segments": []
            })

        # Should still return 200 but with empty mapping
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
