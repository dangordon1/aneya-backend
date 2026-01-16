#!/usr/bin/env python
"""
Script to replace inline Supabase client creation with get_supabase_client() calls.
"""

import re

# Read the file
with open('custom_forms_api.py', 'r') as f:
    content = f.read()

# Pattern to match the inline client creation
pattern = r'''        from supabase import create_client, Client

        supabase_url = os\.getenv\("SUPABASE_URL"\)
        supabase_key = os\.getenv\("SUPABASE_SERVICE_KEY"\)
        supabase: Client = create_client\(supabase_url, supabase_key\)'''

replacement = '''        supabase = get_supabase_client()'''

# Replace all occurrences
new_content = re.sub(pattern, replacement, content)

# Count replacements
count = len(re.findall(pattern, content))

print(f"Found and replaced {count} occurrences")

# Write back
with open('custom_forms_api.py', 'w') as f:
    f.write(new_content)

print("✅ File updated successfully")
