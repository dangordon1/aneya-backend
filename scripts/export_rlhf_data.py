#!/usr/bin/env python3
"""
RLHF Data Export Script

Exports feedback data from Supabase in JSONL format for Reinforcement Learning
from Human Feedback (RLHF) model training.

Usage:
    python export_rlhf_data.py --output feedback_data.jsonl --days 30
    python export_rlhf_data.py --output feedback_data.jsonl --type diagnosis
    python export_rlhf_data.py --output feedback_data.jsonl --days 7 --type transcription

Features:
- Exports feedback with consultation context
- Filters by date range and feedback type
- Generates summary statistics
- JSONL format for easy model training
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_supabase_client():
    """Initialize and return Supabase client."""
    from supabase import create_client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

    return create_client(supabase_url, supabase_key)


def fetch_feedback_data(
    supabase,
    days: Optional[int] = None,
    feedback_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch feedback data with consultation context from Supabase.

    Args:
        supabase: Supabase client
        days: Number of days to look back (None = all time)
        feedback_type: Filter by specific type (None = all types)

    Returns:
        List of feedback records with consultation data
    """
    print(f"📊 Fetching feedback data...")

    # Build query
    query = supabase.table('ai_feedback').select(
        """
        *,
        consultations (
            id,
            consultation_text,
            original_transcript,
            summary_data,
            diagnoses,
            patient_id,
            created_at
        )
        """
    )

    # Apply filters
    if days:
        date_threshold = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = query.gte('created_at', date_threshold)

    if feedback_type:
        query = query.eq('feedback_type', feedback_type)

    # Execute query
    result = query.order('created_at', desc=False).execute()

    print(f"✅ Fetched {len(result.data)} feedback records")
    return result.data


def format_for_rlhf(feedback_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a feedback record for RLHF training.

    Creates a structured JSONL entry with:
    - input: The context (consultation, patient info)
    - output: The AI-generated content that was rated
    - feedback: User rating and metadata

    Args:
        feedback_record: Raw feedback record from database

    Returns:
        Formatted RLHF training example
    """
    consultation = feedback_record.get('consultations', {})
    feedback_type = feedback_record['feedback_type']

    # Base input context (always include)
    input_data = {
        "consultation_id": feedback_record['consultation_id'],
        "consultation_text": consultation.get('consultation_text', ''),
        "original_transcript": consultation.get('original_transcript', ''),
        "patient_id": consultation.get('patient_id'),
        "timestamp": consultation.get('created_at'),
    }

    # Extract the AI output that was rated
    output_data = {}

    if feedback_type == 'transcription':
        output_data = {
            "type": "transcription",
            "content": consultation.get('original_transcript', ''),
            "component_id": feedback_record.get('component_identifier')
        }

    elif feedback_type == 'summary':
        output_data = {
            "type": "summary",
            "content": consultation.get('summary_data', {}),
            "component_id": feedback_record.get('component_identifier')
        }

    elif feedback_type == 'diagnosis':
        # Find the specific diagnosis from the diagnoses array
        diagnoses = consultation.get('diagnoses', [])
        diagnosis_text = feedback_record.get('diagnosis_text', '')

        # Try to find matching diagnosis in consultation
        matched_diagnosis = None
        for diag in diagnoses:
            if diag.get('diagnosis') == diagnosis_text or diag.get('name') == diagnosis_text:
                matched_diagnosis = diag
                break

        output_data = {
            "type": "diagnosis",
            "diagnosis_text": diagnosis_text,
            "full_diagnosis_data": matched_diagnosis,
            "is_correct_diagnosis": feedback_record.get('is_correct_diagnosis', False),
            "confidence": matched_diagnosis.get('confidence') if matched_diagnosis else None,
            "component_id": feedback_record.get('component_identifier')
        }

    elif feedback_type == 'drug_recommendation':
        output_data = {
            "type": "drug_recommendation",
            "drug_name": feedback_record.get('drug_name'),
            "drug_dosage": feedback_record.get('drug_dosage'),
            "component_id": feedback_record.get('component_identifier')
        }

    # Feedback metadata
    feedback_data = {
        "sentiment": feedback_record['feedback_sentiment'],
        "user_role": feedback_record.get('user_role', 'anonymous'),
        "user_id": feedback_record.get('user_id'),
        "notes": feedback_record.get('notes'),
        "metadata": feedback_record.get('metadata', {}),
        "created_at": feedback_record['created_at'],
        "updated_at": feedback_record['updated_at']
    }

    return {
        "feedback_id": feedback_record['id'],
        "input": input_data,
        "output": output_data,
        "feedback": feedback_data
    }


def calculate_statistics(feedback_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate summary statistics for feedback data.

    Args:
        feedback_records: List of feedback records

    Returns:
        Dictionary of statistics
    """
    total_count = len(feedback_records)

    if total_count == 0:
        return {
            "total_feedback": 0,
            "message": "No feedback data found"
        }

    # Count by type and sentiment
    by_type = defaultdict(lambda: {"positive": 0, "negative": 0, "total": 0})
    by_user_role = defaultdict(int)
    correct_diagnoses = 0
    unique_consultations = set()

    for record in feedback_records:
        fb_type = record['feedback_type']
        sentiment = record['feedback_sentiment']

        by_type[fb_type][sentiment] += 1
        by_type[fb_type]["total"] += 1

        by_user_role[record.get('user_role', 'anonymous')] += 1
        unique_consultations.add(record['consultation_id'])

        if record['feedback_type'] == 'diagnosis' and record.get('is_correct_diagnosis'):
            correct_diagnoses += 1

    # Calculate percentages
    positive_count = sum(1 for r in feedback_records if r['feedback_sentiment'] == 'positive')
    positive_pct = (positive_count / total_count * 100) if total_count > 0 else 0

    # Type-specific stats
    type_stats = {}
    for fb_type, counts in by_type.items():
        type_total = counts['total']
        type_positive_pct = (counts['positive'] / type_total * 100) if type_total > 0 else 0
        type_stats[fb_type] = {
            "total": type_total,
            "positive": counts['positive'],
            "negative": counts['negative'],
            "positive_percentage": round(type_positive_pct, 2)
        }

    return {
        "total_feedback": total_count,
        "unique_consultations": len(unique_consultations),
        "overall_positive_percentage": round(positive_pct, 2),
        "by_type": type_stats,
        "by_user_role": dict(by_user_role),
        "correct_diagnoses_marked": correct_diagnoses,
        "date_range": {
            "earliest": min(r['created_at'] for r in feedback_records),
            "latest": max(r['created_at'] for r in feedback_records)
        }
    }


def export_to_jsonl(
    feedback_records: List[Dict[str, Any]],
    output_file: str
) -> int:
    """
    Export feedback records to JSONL file.

    Args:
        feedback_records: List of feedback records
        output_file: Path to output file

    Returns:
        Number of records exported
    """
    count = 0

    with open(output_file, 'w') as f:
        for record in feedback_records:
            rlhf_entry = format_for_rlhf(record)
            f.write(json.dumps(rlhf_entry) + '\n')
            count += 1

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Export RLHF feedback data from Supabase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all feedback from last 30 days
  python export_rlhf_data.py --output feedback.jsonl --days 30

  # Export only diagnosis feedback
  python export_rlhf_data.py --output diagnosis_feedback.jsonl --type diagnosis

  # Export all transcription feedback from last 7 days
  python export_rlhf_data.py --output transcription.jsonl --days 7 --type transcription

  # Export everything (all time)
  python export_rlhf_data.py --output all_feedback.jsonl
        """
    )

    parser.add_argument(
        '--output',
        '-o',
        type=str,
        required=True,
        help='Output JSONL file path'
    )

    parser.add_argument(
        '--days',
        '-d',
        type=int,
        default=None,
        help='Number of days to look back (default: all time)'
    )

    parser.add_argument(
        '--type',
        '-t',
        type=str,
        choices=['transcription', 'summary', 'diagnosis', 'drug_recommendation'],
        default=None,
        help='Filter by feedback type (default: all types)'
    )

    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Only print statistics without exporting'
    )

    args = parser.parse_args()

    try:
        # Initialize Supabase
        print("🔗 Connecting to Supabase...")
        supabase = get_supabase_client()

        # Fetch data
        feedback_records = fetch_feedback_data(
            supabase,
            days=args.days,
            feedback_type=args.type
        )

        if not feedback_records:
            print("⚠️  No feedback data found matching the criteria")
            return

        # Calculate statistics
        stats = calculate_statistics(feedback_records)

        # Print statistics
        print("\n" + "="*60)
        print("📈 FEEDBACK STATISTICS")
        print("="*60)
        print(f"\nTotal Feedback Entries: {stats['total_feedback']}")
        print(f"Unique Consultations: {stats['unique_consultations']}")
        print(f"Overall Positive Rate: {stats['overall_positive_percentage']}%")

        print("\n📊 By Feedback Type:")
        for fb_type, type_stats in stats['by_type'].items():
            print(f"\n  {fb_type.upper()}:")
            print(f"    Total: {type_stats['total']}")
            print(f"    Positive: {type_stats['positive']} ({type_stats['positive_percentage']}%)")
            print(f"    Negative: {type_stats['negative']}")

        print("\n👥 By User Role:")
        for role, count in stats['by_user_role'].items():
            print(f"  {role}: {count}")

        if stats['correct_diagnoses_marked'] > 0:
            print(f"\n✅ Correct Diagnoses Marked: {stats['correct_diagnoses_marked']}")

        print(f"\n📅 Date Range:")
        print(f"  Earliest: {stats['date_range']['earliest']}")
        print(f"  Latest: {stats['date_range']['latest']}")

        # Export to file (unless --stats-only)
        if not args.stats_only:
            print("\n" + "="*60)
            print("💾 EXPORTING DATA")
            print("="*60)

            exported_count = export_to_jsonl(feedback_records, args.output)

            print(f"\n✅ Exported {exported_count} records to: {args.output}")
            print(f"📄 File size: {os.path.getsize(args.output):,} bytes")

            # Show sample entry
            print("\n📝 Sample JSONL entry:")
            with open(args.output, 'r') as f:
                first_line = f.readline()
                sample = json.loads(first_line)
                print(json.dumps(sample, indent=2)[:500] + "...")

        print("\n" + "="*60)
        print("✨ EXPORT COMPLETE")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
