"""
Field validation and sanitization for form auto-fill.

Validates extracted field values against schemas, performs type checking,
range validation, unit conversions, and sanitization.
"""

from typing import Any, Tuple, Optional, Dict
import re
from datetime import datetime

from mcp_servers.form_schemas import get_field_metadata

# ============================================
# VALIDATION FUNCTIONS
# ============================================

def validate_field_update(
    form_type: str,
    field_path: str,
    value: Any,
) -> Tuple[bool, Any, Optional[str]]:
    """
    Validate and sanitize a field value against the form schema.

    Args:
        form_type: One of 'obgyn', 'infertility', 'antenatal'
        field_path: Field path in dot notation (e.g., 'vital_signs.systolic_bp')
        value: The value to validate

    Returns:
        Tuple of (is_valid, sanitized_value, error_message)
        - is_valid: True if validation passed
        - sanitized_value: The validated and sanitized value (may be converted)
        - error_message: Description of validation error if is_valid is False, else None
    """
    # Get field metadata from schema
    metadata = get_field_metadata(form_type, field_path)
    if metadata is None:
        return False, None, f"Field '{field_path}' not found in schema for form type '{form_type}'"

    field_type = metadata.get('type')

    # Handle None/null values
    if value is None or value == '':
        return True, None, None

    try:
        # Validate based on field type
        if field_type == 'number':
            return _validate_number(value, metadata)
        elif field_type == 'string':
            return _validate_string(value, metadata)
        elif field_type == 'boolean':
            return _validate_boolean(value, metadata)
        elif field_type == 'object':
            return _validate_object(value, metadata)
        elif field_type == 'array':
            # Array fields (tables) - accept list or skip validation for now
            if isinstance(value, list):
                return True, value, None
            else:
                # Try to convert single value to array
                return True, [value], None
        else:
            return False, None, f"Unknown field type: {field_type}"

    except Exception as e:
        return False, None, f"Validation error: {str(e)}"


def _validate_number(value: Any, metadata: Dict[str, Any]) -> Tuple[bool, Any, Optional[str]]:
    """Validate and convert numeric values."""
    # Try to convert to float
    try:
        if isinstance(value, str):
            # Remove common text like "approximately", "about", etc.
            value = value.replace('approximately', '').replace('about', '').strip()
            numeric_value = float(value)
        elif isinstance(value, (int, float)):
            numeric_value = float(value)
        else:
            return False, None, f"Cannot convert {type(value).__name__} to number"
    except ValueError:
        return False, None, f"Invalid number format: '{value}'"

    # Apply unit conversions if needed
    unit = metadata.get('unit', '')
    if unit == 'celsius':
        # Check if value might be in Fahrenheit (>50 is likely F, not C)
        if numeric_value > 50:
            numeric_value = fahrenheit_to_celsius(numeric_value)

    # Validate range
    value_range = metadata.get('range')
    if value_range:
        min_val, max_val = value_range
        if not (min_val <= numeric_value <= max_val):
            return False, None, f"Value {numeric_value} outside valid range [{min_val}, {max_val}]"

    return True, numeric_value, None


def _validate_string(value: Any, metadata: Dict[str, Any]) -> Tuple[bool, Any, Optional[str]]:
    """Validate and sanitize string values."""
    # Convert to string
    str_value = str(value).strip()

    # Check max length
    max_length = metadata.get('max_length')
    if max_length and len(str_value) > max_length:
        # Truncate with warning
        str_value = str_value[:max_length]
        # Note: Still valid, just truncated

    # Sanitize for XSS prevention (basic)
    str_value = sanitize_string(str_value)

    # Validate format if specified
    format_type = metadata.get('format')
    if format_type == 'YYYY-MM-DD':
        normalized = _normalize_date(str_value)
        if normalized is None:
            return False, None, f"Invalid date format: '{str_value}'. Expected a recognizable date"
        return True, normalized, None

    return True, str_value, None


def _validate_boolean(value: Any, metadata: Dict[str, Any]) -> Tuple[bool, Any, Optional[str]]:
    """Validate and convert boolean values."""
    if isinstance(value, bool):
        return True, value, None

    if isinstance(value, str):
        lower_val = value.lower().strip()
        if lower_val in ['true', 'yes', '1', 'positive']:
            return True, True, None
        elif lower_val in ['false', 'no', '0', 'negative']:
            return True, False, None

    return False, None, f"Cannot convert '{value}' to boolean"


def _validate_object(value: Any, metadata: Dict[str, Any]) -> Tuple[bool, Any, Optional[str]]:
    """Validate object/dict values."""
    if not isinstance(value, dict):
        return False, None, f"Expected object/dict, got {type(value).__name__}"

    # Could add recursive validation of nested fields here if needed
    return True, value, None


# ============================================
# UNIT CONVERSION FUNCTIONS
# ============================================

def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return round((fahrenheit - 32) * 5/9, 1)


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return round((celsius * 9/5) + 32, 1)


def parse_blood_pressure(text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse blood pressure from text like "120 over 80" or "120/80".

    Returns:
        Tuple of (systolic, diastolic) or (None, None) if parsing fails
    """
    # Pattern 1: "120 over 80", "120 on 80"
    match = re.search(r'(\d+)\s+(?:over|on)\s+(\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Pattern 2: "120/80"
    match = re.search(r'(\d+)\s*/\s*(\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))

    return None, None


def parse_text_to_number(text: str) -> Optional[float]:
    """
    Convert text representations of numbers to numeric values.
    Handles formats like "one twenty" -> 120, "ninety-eight point six" -> 98.6
    """
    if not isinstance(text, str):
        return None

    # Remove common filler words
    text = text.lower()
    text = re.sub(r'\b(approximately|about|around)\b', '', text)

    # Word to number mapping
    word_to_num = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
        'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
        'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
        'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
        'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30,
        'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
        'eighty': 80, 'ninety': 90, 'hundred': 100, 'thousand': 1000
    }

    # Try direct numeric conversion first
    try:
        return float(text)
    except ValueError:
        pass

    # Try word-based conversion (basic implementation)
    # "ninety eight" -> 98
    words = text.split()
    total = 0
    for word in words:
        word_clean = word.strip('.,;:!?')
        if word_clean in word_to_num:
            num = word_to_num[word_clean]
            if num >= 100:
                total *= num
            else:
                total += num

    return total if total > 0 else None


# ============================================
# SANITIZATION FUNCTIONS
# ============================================

def sanitize_string(text: str) -> str:
    """
    Sanitize string for XSS prevention and safe storage.

    Removes potentially dangerous characters and scripts.
    """
    if not isinstance(text, str):
        return str(text)

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Remove script tags content
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)

    # Remove common XSS patterns
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)

    # Normalize whitespace
    text = ' '.join(text.split())

    return text.strip()


def _normalize_date(date_str: str) -> Optional[str]:
    """Parse common date formats and normalize to YYYY-MM-DD."""
    for fmt in ('%Y-%m-%d', '%b %d, %Y', '%B %d, %Y', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def _is_valid_date(date_str: str) -> bool:
    """Check if string is a valid date in any recognized format."""
    return _normalize_date(date_str) is not None


# ============================================
# BATCH VALIDATION
# ============================================

def validate_multiple_fields(
    form_type: str,
    field_updates: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Validate multiple field updates at once.

    Args:
        form_type: One of 'obgyn', 'infertility', 'antenatal'
        field_updates: Dictionary mapping field paths to values

    Returns:
        Tuple of (valid_updates, errors)
        - valid_updates: Dictionary of field paths that passed validation with sanitized values
        - errors: Dictionary mapping field paths to error messages
    """
    valid_updates = {}
    errors = {}

    for field_path, value in field_updates.items():
        is_valid, sanitized_value, error_msg = validate_field_update(
            form_type, field_path, value
        )

        if is_valid:
            valid_updates[field_path] = sanitized_value
        else:
            errors[field_path] = error_msg or "Validation failed"

    return valid_updates, errors


# ============================================
# CONFIDENCE-BASED FILTERING
# ============================================

def filter_by_confidence(
    field_updates: Dict[str, Any],
    confidence_scores: Dict[str, float],
    min_confidence: float = 0.7
) -> Dict[str, Any]:
    """
    Filter field updates to only include high-confidence extractions.

    Args:
        field_updates: Dictionary of field paths to values
        confidence_scores: Dictionary of field paths to confidence scores (0.0-1.0)
        min_confidence: Minimum confidence threshold (default 0.7)

    Returns:
        Filtered dictionary containing only high-confidence updates
    """
    filtered = {}

    for field_path, value in field_updates.items():
        confidence = confidence_scores.get(field_path, 0.0)
        if confidence >= min_confidence:
            filtered[field_path] = value

    return filtered


# ============================================
# DUPLICATE DETECTION
# ============================================

def exclude_existing_fields(
    field_updates: Dict[str, Any],
    current_form_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Exclude fields that already have values in the current form state.
    This prevents overwriting existing data.

    Args:
        field_updates: Dictionary of field paths to new values
        current_form_state: Current state of the form

    Returns:
        Filtered dictionary excluding fields already populated
    """
    filtered = {}

    for field_path, value in field_updates.items():
        # Parse nested path
        current_value = _get_nested_value(current_form_state, field_path)

        # Only include if current value is None, empty string, or missing
        if current_value is None or current_value == '':
            filtered[field_path] = value

    return filtered


def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """
    Get value from nested dictionary using dot notation path.

    Example: _get_nested_value({'vital_signs': {'systolic_bp': 120}}, 'vital_signs.systolic_bp') -> 120
    """
    keys = path.split('.')
    value = data

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None

    return value
