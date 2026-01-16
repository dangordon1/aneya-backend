#!/usr/bin/env python
"""
Script to replace remaining inline Supabase client creation patterns.
"""

import re

# Read the file
with open('custom_forms_api.py', 'r') as f:
    content = f.read()

# Pattern for lines with no leading spaces (or any amount of spaces)
patterns = [
    # Pattern with no additional blank line
    (r'''        from supabase import create_client, Client
        supabase_url = os\.getenv\("SUPABASE_URL"\)
        supabase_key = os\.getenv\("SUPABASE_SERVICE_KEY"\)
        supabase: Client = create_client\(supabase_url, supabase_key\)''',
     '''        supabase = get_supabase_client()'''),
]

total_count = 0
for pattern, replacement in patterns:
    count = len(re.findall(pattern, content))
    if count > 0:
        print(f"Found {count} occurrences of pattern")
        content = re.sub(pattern, replacement, content)
        total_count += count

print(f"\nTotal replaced: {total_count} occurrences")

# Write back
with open('custom_forms_api.py', 'w') as f:
    f.write(content)

print("✅ File updated successfully")
