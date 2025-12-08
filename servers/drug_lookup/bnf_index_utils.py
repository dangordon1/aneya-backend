
import json
import os
import difflib
import logging
from typing import List, Dict, Optional, Any

# Configure logging
logger = logging.getLogger(__name__)

# Common drug name synonyms/aliases that map to BNF names
# Maps variations -> BNF canonical name
DRUG_SYNONYMS = {
    # Combination antibiotics
    'amoxicillin-clavulanate': 'co-amoxiclav',
    'amoxicillin/clavulanate': 'co-amoxiclav',
    'amoxicillin clavulanate': 'co-amoxiclav',
    'augmentin': 'co-amoxiclav',
    'amoxyclav': 'co-amoxiclav',

    # Other common combinations
    'trimethoprim-sulfamethoxazole': 'co-trimoxazole',
    'tmp-smx': 'co-trimoxazole',
    'bactrim': 'co-trimoxazole',
    'septrin': 'co-trimoxazole',

    # Common brand -> generic
    'tylenol': 'paracetamol',
    'acetaminophen': 'paracetamol',
    'advil': 'ibuprofen',
    'motrin': 'ibuprofen',
    'nurofen': 'ibuprofen',

    # Other variations
    'zithromax': 'azithromycin',
    'amoxil': 'amoxicillin',
    'augmentin': 'co-amoxiclav',
    'ventolin': 'salbutamol',
    'albuterol': 'salbutamol',

    # Spelling variations
    'paracetamol': 'paracetamol',
    'acetaminophen': 'paracetamol',
}


class BNFIndex:
    def __init__(self, index_path: str = None):
        if index_path is None:
            # Default to data/bnf_drug_index.json relative to this file
            index_path = os.path.join(os.path.dirname(__file__), 'data', 'bnf_drug_index.json')
        
        self.index_path = index_path
        self.data = self._load_index()
        self.drugs = self.data.get('drugs', [])
        
        # Create map for O(1) exact lookups
        self.name_map = {d['name'].lower(): d for d in self.drugs}
        
    def _load_index(self) -> Dict[str, Any]:
        try:
            with open(self.index_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"BNF Index file not found at {self.index_path}")
            return {"drugs": []}
            
    def get_exact(self, name: str) -> Optional[Dict[str, str]]:
        """
        Get exact match for drug name (case-insensitive).
        """
        return self.name_map.get(name.lower().strip())
        
    def search(self, query: str, limit: int = 5, cutoff: float = 0.6) -> List[Dict[str, str]]:
        """
        Fuzzy search for drugs.
        """
        query = query.lower().strip()

        # 0. Check synonyms first (maps brand names / variations to BNF canonical names)
        if query in DRUG_SYNONYMS:
            canonical = DRUG_SYNONYMS[query]
            if canonical in self.name_map:
                logger.info(f"Synonym match: '{query}' -> '{canonical}'")
                return [self.name_map[canonical]]

        # 1. Exact match check first
        if query in self.name_map:
            return [self.name_map[query]]
            
        # 2. Contains match (very simple priority to starts_with)
        contains_matches = [d for d in self.drugs if query in d['name'].lower()]
        # Sort by starts_with query first
        contains_matches.sort(key=lambda x: 0 if x['name'].lower().startswith(query) else 1)
        
        # 3. Fuzzy match using difflib
        all_names = [d['name'] for d in self.drugs]
        matches = difflib.get_close_matches(query, all_names, n=limit, cutoff=cutoff)
        
        results = []
        seen_slugs = set()
        
        # Helper to add unique results
        def add_result(d):
            if d['slug'] not in seen_slugs:
                results.append(d)
                seen_slugs.add(d['slug'])

        # Add contains matches first
        for d in contains_matches:
             add_result(d)
        
        # Add fuzzy matches
        for name in matches:
            d = self.name_map.get(name.lower())
            if d:
                add_result(d)
                
        return results[:limit]

# Singleton instance
_index_instance = None

def get_bnf_index() -> BNFIndex:
    global _index_instance
    if _index_instance is None:
        _index_instance = BNFIndex()
    return _index_instance
