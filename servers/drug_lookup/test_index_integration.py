
import sys
import os
import io

# Setup path to import bnf_server and utils
sys.path.append(os.path.dirname(__file__))

# Mock FastMCP so we don't start a server
from unittest.mock import MagicMock
sys.modules['fastmcp'] = MagicMock()

# Import the server module (it will try to initialize FastMCP but we mocked it)
import bnf_server

def test_search():
    print("Testing search integration...")
    
    # Test cases that should hit the local index
    # "paracetamol" might hit exact URL logic first (it's a common name)
    # "Tylenol" should definitely hit the index (found earlier as Atenolol/Phenol) 
    # or actually Tylenol wasn't in index, but "ibuprufen" (typo) was correction.
    
    queries = ["ibuprufen", "abacavir"]
    
    for q in queries:
        print(f"\nSearching for: {q}")
        result = bnf_server._search_bnf_drug_impl(q)
        print(f"Success: {result['success']}")
        print(f"Source: {result.get('source', 'unknown')}")
        print(f"Results: {len(result['results'])}")
        
        if result['results']:
            print(f"First match: {result['results'][0]['name']} -> {result['results'][0]['url']}")

if __name__ == "__main__":
    test_search()
