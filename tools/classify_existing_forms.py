"""
Classify all existing custom forms to detect which tables/fields reference previous consultations.

This script:
1. Fetches all custom forms from the database
2. Runs the TableClassifier on each form
3. Updates the table_metadata column with classification results
4. Generates a report of which forms/tables link to previous consultations
"""

import asyncio
import json
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from supabase import create_client, Client
from table_classifier import TableClassifier

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


async def fetch_all_custom_forms() -> List[Dict[str, Any]]:
    """Fetch all custom forms from the database."""
    print("📥 Fetching all custom forms from database...")

    response = supabase.table("custom_forms").select("*").execute()

    forms = response.data
    print(f"   Found {len(forms)} custom forms\n")

    return forms


async def classify_form(form: Dict[str, Any], classifier: TableClassifier) -> Dict[str, Any]:
    """
    Classify a single form and return the classification metadata.

    Returns:
        Classification result with table metadata
    """
    print(f"\n{'='*80}")
    print(f"📋 Form: {form['form_name']}")
    print(f"   Specialty: {form['specialty']}")
    print(f"   ID: {form['id']}")
    print(f"{'='*80}")

    # Prepare form metadata for classification
    form_metadata = {
        "form_name": form["form_name"],
        "specialty": form["specialty"],
        "description": form.get("patient_criteria", ""),
        "patient_criteria": form.get("patient_criteria", "")
    }

    # Classify all tables in the form
    table_metadata = await classifier.classify_all_tables(
        form_schema=form["form_schema"],
        form_metadata=form_metadata
    )

    return table_metadata


async def update_form_metadata(form_id: str, table_metadata: Dict[str, Any]) -> None:
    """Update the table_metadata column for a form."""
    print(f"\n💾 Updating table_metadata for form {form_id}...")

    supabase.table("custom_forms").update({
        "table_metadata": table_metadata
    }).eq("id", form_id).execute()

    print(f"   ✅ Updated successfully")


def generate_report(results: List[Dict[str, Any]]) -> None:
    """
    Generate a report of forms/tables that reference previous consultations.
    """
    print(f"\n\n{'='*80}")
    print("📊 CLASSIFICATION REPORT")
    print(f"{'='*80}\n")

    total_forms = len(results)
    total_tables = 0
    tables_with_previous_consultation = []
    tables_by_data_source = {}

    for result in results:
        form_id = result["form_id"]
        form_name = result["form_name"]
        table_metadata = result["table_metadata"]

        if not table_metadata or "tables" not in table_metadata:
            continue

        for table_name, classification in table_metadata["tables"].items():
            total_tables += 1

            data_source = classification.get("data_source_type", "unknown")
            references_prev = classification.get("references_previous_consultation", False)

            # Track data source types
            if data_source not in tables_by_data_source:
                tables_by_data_source[data_source] = 0
            tables_by_data_source[data_source] += 1

            # Track tables that reference previous consultations
            if references_prev:
                tables_with_previous_consultation.append({
                    "form_name": form_name,
                    "form_id": form_id,
                    "table_name": table_name,
                    "data_source": data_source,
                    "confidence": classification.get("confidence", 0),
                    "reasoning": classification.get("reasoning", "")
                })

    # Print summary statistics
    print(f"📈 Summary Statistics:")
    print(f"   Total Forms: {total_forms}")
    print(f"   Total Tables: {total_tables}")
    print(f"   Tables Referencing Previous Consultations: {len(tables_with_previous_consultation)}")
    print()

    # Print data source breakdown
    print(f"📊 Data Source Types:")
    for data_source, count in sorted(tables_by_data_source.items(), key=lambda x: -x[1]):
        print(f"   {data_source}: {count}")
    print()

    # Print detailed list of tables referencing previous consultations
    if tables_with_previous_consultation:
        print(f"\n🔗 Tables Referencing Previous Consultations:\n")
        for item in tables_with_previous_consultation:
            print(f"   Form: {item['form_name']} ({item['form_id'][:8]}...)")
            print(f"   Table: {item['table_name']}")
            print(f"   Data Source: {item['data_source']}")
            print(f"   Confidence: {item['confidence']:.2f}")
            print(f"   Reasoning: {item['reasoning']}")
            print()
    else:
        print(f"\n✨ No tables found that reference previous consultations")

    print(f"\n{'='*80}")


async def main():
    """Main function to classify all existing forms."""
    print("\n🚀 Starting classification of all existing custom forms...\n")

    # Initialize classifier
    classifier = TableClassifier()

    # Fetch all forms
    forms = await fetch_all_custom_forms()

    if not forms:
        print("⚠️  No custom forms found in database")
        return

    # Classify each form
    results = []
    for i, form in enumerate(forms, 1):
        print(f"\n[{i}/{len(forms)}] Processing form: {form['form_name']}")

        try:
            table_metadata = await classify_form(form, classifier)

            # Update database
            await update_form_metadata(form["id"], table_metadata)

            # Store result for report
            results.append({
                "form_id": form["id"],
                "form_name": form["form_name"],
                "table_metadata": table_metadata
            })

        except Exception as e:
            print(f"❌ Error processing form {form['form_name']}: {e}")
            continue

    # Generate report
    generate_report(results)

    print("\n✅ Classification complete!")


if __name__ == "__main__":
    asyncio.run(main())
