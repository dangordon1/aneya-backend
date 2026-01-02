"""
Conflict Detection Module
Compares extracted patient data with existing data to identify conflicts
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal

logger = logging.getLogger(__name__)


class ConflictDetector:
    """Detect conflicts between extracted and existing patient data"""

    # Tolerance thresholds for numeric comparisons
    NUMERIC_TOLERANCE = {
        "systolic_bp": 5,  # mmHg
        "diastolic_bp": 5,  # mmHg
        "heart_rate": 5,  # bpm
        "temperature_celsius": 0.5,  # celsius
        "spo2": 2,  # percentage
        "weight_kg": 1.0,  # kg
        "height_cm": 2.0,  # cm
        "blood_glucose_mg_dl": 10,  # mg/dL
    }

    @staticmethod
    def compare_patient_data(
        extracted_data: Dict[str, Any],
        current_data: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Compare extracted data with current patient data

        Args:
            extracted_data: Data extracted from uploaded forms
            current_data: Current patient data from database

        Returns:
            Tuple of (conflicts dict, has_conflicts bool)
        """
        conflicts = {}

        # Compare demographics
        demo_conflicts = ConflictDetector._compare_demographics(
            extracted_data.get("demographics", {}),
            current_data.get("demographics", {})
        )
        conflicts.update(demo_conflicts)

        # Compare medical history fields
        med_hist_conflicts = ConflictDetector._compare_medical_history(
            extracted_data.get("medical_history", {}),
            current_data.get("medical_history", {})
        )
        conflicts.update(med_hist_conflicts)

        # Note: Vitals, medications, and allergies are typically additive
        # rather than conflicting, but we can flag duplicates

        has_conflicts = len(conflicts) > 0

        return conflicts, has_conflicts

    @staticmethod
    def _compare_demographics(
        extracted: Dict[str, Any],
        current: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Compare demographic fields"""
        conflicts = {}

        # Fields to compare
        comparable_fields = {
            "name": "exact",
            "date_of_birth": "exact",
            "sex": "exact",
            "phone": "exact",
            "email": "exact",
            "height_cm": "numeric",
            "weight_kg": "numeric",
        }

        for field, comparison_type in comparable_fields.items():
            extracted_value = extracted.get(field)
            current_value = current.get(field)

            # Skip if either value is None
            if extracted_value is None or current_value is None:
                continue

            # Convert to comparable types
            extracted_value = ConflictDetector._normalize_value(extracted_value)
            current_value = ConflictDetector._normalize_value(current_value)

            conflict = None

            if comparison_type == "exact":
                if extracted_value != current_value:
                    conflict = {
                        "current_value": current_value,
                        "extracted_value": extracted_value,
                        "conflict_type": "value_mismatch"
                    }

            elif comparison_type == "numeric":
                conflict = ConflictDetector._compare_numeric_field(
                    field, extracted_value, current_value
                )

            if conflict:
                conflicts[f"demographics.{field}"] = conflict

        return conflicts

    @staticmethod
    def _compare_medical_history(
        extracted: Dict[str, Any],
        current: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Compare medical history fields"""
        conflicts = {}

        fields = ["current_conditions", "past_surgeries", "family_history"]

        for field in fields:
            extracted_value = extracted.get(field)
            current_value = current.get(field)

            # Skip if either is None or empty
            if not extracted_value or not current_value:
                continue

            # Normalize to sets for comparison
            extracted_set = ConflictDetector._text_to_set(extracted_value)
            current_set = ConflictDetector._text_to_set(current_value)

            # Check for differences
            added = extracted_set - current_set
            removed = current_set - extracted_set

            if added or removed:
                conflicts[f"medical_history.{field}"] = {
                    "current_value": current_value,
                    "extracted_value": extracted_value,
                    "conflict_type": "text_diff",
                    "added_items": list(added) if added else [],
                    "removed_items": list(removed) if removed else []
                }

        return conflicts

    @staticmethod
    def _compare_numeric_field(
        field_name: str,
        extracted_value: Any,
        current_value: Any
    ) -> Optional[Dict[str, Any]]:
        """Compare numeric fields with tolerance"""
        try:
            extracted_num = float(extracted_value)
            current_num = float(current_value)

            tolerance = ConflictDetector.NUMERIC_TOLERANCE.get(field_name, 0)

            diff = abs(extracted_num - current_num)

            if diff == 0:
                return None  # Exact match

            if diff <= tolerance:
                return {
                    "current_value": current_num,
                    "extracted_value": extracted_num,
                    "conflict_type": "close_match",
                    "difference": diff,
                    "tolerance": tolerance
                }
            else:
                return {
                    "current_value": current_num,
                    "extracted_value": extracted_num,
                    "conflict_type": "value_mismatch",
                    "difference": diff,
                    "tolerance": tolerance
                }

        except (ValueError, TypeError):
            # Can't compare as numbers
            if str(extracted_value) != str(current_value):
                return {
                    "current_value": current_value,
                    "extracted_value": extracted_value,
                    "conflict_type": "value_mismatch"
                }

        return None

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        """Normalize value for comparison"""
        if isinstance(value, str):
            return value.strip().lower()
        elif isinstance(value, (int, float, Decimal)):
            return float(value)
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, datetime):
            return value.date().isoformat()
        return value

    @staticmethod
    def _text_to_set(text: str) -> set:
        """Convert comma-separated text to normalized set"""
        if not text:
            return set()

        # Split by comma and normalize
        items = [item.strip().lower() for item in text.split(',')]
        return {item for item in items if item}

    @staticmethod
    def detect_duplicate_vitals(
        extracted_vitals: List[Dict[str, Any]],
        current_vitals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect potential duplicate vital records

        Returns:
            List of potential duplicates with similarity info
        """
        duplicates = []

        for extracted in extracted_vitals:
            for current in current_vitals:
                similarity = ConflictDetector._calculate_vital_similarity(
                    extracted, current
                )

                if similarity > 0.8:  # 80% similar
                    duplicates.append({
                        "extracted_vital": extracted,
                        "existing_vital": current,
                        "similarity": similarity,
                        "likely_duplicate": similarity > 0.95
                    })

        return duplicates

    @staticmethod
    def _calculate_vital_similarity(
        vital1: Dict[str, Any],
        vital2: Dict[str, Any]
    ) -> float:
        """Calculate similarity score between two vital records"""
        comparable_fields = [
            "systolic_bp", "diastolic_bp", "heart_rate",
            "temperature_celsius", "spo2", "weight_kg", "height_cm"
        ]

        matches = 0
        comparisons = 0

        for field in comparable_fields:
            val1 = vital1.get(field)
            val2 = vital2.get(field)

            if val1 is None or val2 is None:
                continue

            comparisons += 1

            try:
                num1 = float(val1)
                num2 = float(val2)
                tolerance = ConflictDetector.NUMERIC_TOLERANCE.get(field, 0)

                if abs(num1 - num2) <= tolerance:
                    matches += 1
            except (ValueError, TypeError):
                if val1 == val2:
                    matches += 1

        if comparisons == 0:
            return 0.0

        return matches / comparisons

    @staticmethod
    def detect_duplicate_medications(
        extracted_meds: List[Dict[str, Any]],
        current_meds: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect potential duplicate medication records

        Returns:
            List of potential duplicates
        """
        duplicates = []

        for extracted in extracted_meds:
            extracted_name = extracted.get("medication_name", "").lower().strip()
            if not extracted_name:
                continue

            for current in current_meds:
                current_name = current.get("medication_name", "").lower().strip()

                # Check if medication names match (exact or partial)
                if (extracted_name == current_name or
                    extracted_name in current_name or
                    current_name in extracted_name):

                    # Check if dosages match
                    extracted_dosage = extracted.get("dosage", "").lower().strip()
                    current_dosage = current.get("dosage", "").lower().strip()

                    is_duplicate = (extracted_dosage == current_dosage)

                    duplicates.append({
                        "extracted_medication": extracted,
                        "existing_medication": current,
                        "name_match": True,
                        "dosage_match": is_duplicate,
                        "likely_duplicate": is_duplicate
                    })

        return duplicates

    @staticmethod
    def detect_duplicate_allergies(
        extracted_allergies: List[Dict[str, Any]],
        current_allergies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect potential duplicate allergy records

        Returns:
            List of potential duplicates
        """
        duplicates = []

        for extracted in extracted_allergies:
            extracted_allergen = extracted.get("allergen", "").lower().strip()
            if not extracted_allergen:
                continue

            for current in current_allergies:
                current_allergen = current.get("allergen", "").lower().strip()

                # Check if allergen names match
                if (extracted_allergen == current_allergen or
                    extracted_allergen in current_allergen or
                    current_allergen in extracted_allergen):

                    duplicates.append({
                        "extracted_allergy": extracted,
                        "existing_allergy": current,
                        "likely_duplicate": extracted_allergen == current_allergen
                    })

        return duplicates

    @staticmethod
    def generate_conflict_summary(conflicts: Dict[str, Any]) -> str:
        """Generate human-readable summary of conflicts"""
        if not conflicts:
            return "No conflicts detected"

        summary_parts = []

        for field_path, conflict_info in conflicts.items():
            conflict_type = conflict_info.get("conflict_type")

            if conflict_type == "value_mismatch":
                summary_parts.append(
                    f"{field_path}: Current '{conflict_info['current_value']}' "
                    f"vs Extracted '{conflict_info['extracted_value']}'"
                )
            elif conflict_type == "close_match":
                summary_parts.append(
                    f"{field_path}: Similar values (difference: {conflict_info['difference']:.2f})"
                )
            elif conflict_type == "text_diff":
                added = conflict_info.get("added_items", [])
                removed = conflict_info.get("removed_items", [])
                if added:
                    summary_parts.append(f"{field_path}: New items - {', '.join(added)}")
                if removed:
                    summary_parts.append(f"{field_path}: Missing items - {', '.join(removed)}")

        return "\n".join(summary_parts)
