# Consultation Analysis Integration

## Overview

The BMJ and Scopus MCP servers are now fully integrated into the consultation analysis system with intelligent cascading fallback when guidelines don't provide sufficient information.

## Cascading Evidence Search Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ CONSULTATION ANALYSIS EVIDENCE SEARCH                       │
└─────────────────────────────────────────────────────────────┘

Step 1: Regional Guidelines
├─ NICE (UK)
├─ FOGSI/NHM/AIIMS (India)
└─ Other regional guidelines
         │
         ├─ Found sufficient evidence? → DONE ✓
         │
         └─ No/Insufficient → Step 2

Step 2: Parallel High-Quality Literature Search
├─ BMJ Medical Literature           ┐
│  ├─ BMJ publications (Europe PMC) │ Run in
│  ├─ BMJ, BMJ Open, BMJ Case Rpts  │ parallel
│  └─ All content (no filter)       │ for speed
└─ Scopus Q1 Journals                │
   ├─ Top 25% of journals            │
   └─ SJR/CiteScore ≥76th percentile ┘
         │
         ├─ Found evidence from either/both? → DONE ✓
         │
         └─ No results from both → Step 3

Step 3: Scopus Q2 Journals (Fallback)
├─ Search Scopus database
├─ Filter: Q2 journals (25-50th percentile)
└─ Based on SJR/CiteScore percentile 51-75
         │
         └─ Return findings → DONE ✓
```

## Implementation Details

### Configuration (`config.py`)

```python
MCP_SERVERS = {
    # ... existing servers ...
    "bmj": str(SERVERS_DIR / "medical_literature" / "bmj_server.py"),
    "scopus": str(SERVERS_DIR / "medical_literature" / "scopus_server.py")
}

GUIDELINE_SERVERS = [
    "patient_info", "nice", "fogsi", "nhm", "aiims",
    "pubmed", "bmj", "scopus"  # Added BMJ and Scopus
]
```

### DiagnosisEngine Methods

**New Methods:**
- `get_bmj_tools()` - Get BMJ-specific tools
- `get_scopus_tools()` - Get Scopus-specific tools
- `literature_fallback()` - Main cascading search method
- `_search_literature_source()` - Helper for single source search

**Workflow:**
```python
# In consultation analysis
diagnoses, tool_calls = await diagnosis_engine.analyze_with_guidelines(scenario)

if len(diagnoses) < threshold:
    # Cascading fallback: (BMJ + Scopus Q1 in parallel) → Scopus Q2
    diagnoses, lit_calls = await diagnosis_engine.literature_fallback(
        scenario, diagnoses
    )
```

### Prompts

**`get_literature_fallback_prompt()`**
- Dynamically configured for BMJ or Scopus
- Includes quartile guidance for Scopus searches
- Instructs LLM to:
  - Search for systematic reviews, meta-analyses, RCTs
  - Cite article titles and DOIs
  - Provide evidence levels
  - Extract evidence-based recommendations

## Evidence Quality Hierarchy

The system prioritizes evidence in this order:

1. **Official Guidelines** (NICE, FOGSI, etc.)
   - Highest priority
   - Region-specific, authoritative
   - Updated regularly by medical bodies

2. **BMJ Publications**
   - Peer-reviewed medical journal
   - Includes systematic reviews and clinical guidance
   - No quartile filter (all BMJ content is high quality)

3. **Scopus Q1 Journals**
   - Top 25% of journals in their field
   - Highest impact factor journals
   - Most cited research

4. **Scopus Q2 Journals**
   - 25-50th percentile journals
   - Still high-quality, peer-reviewed
   - Broader evidence base

## Tool Exclusion Strategy

BMJ and Scopus tools are **excluded** from initial guideline search to prevent:
- Premature literature searches
- Mixed evidence quality
- Unnecessary API calls

They're only made available during fallback, ensuring:
- Guidelines are tried first
- Cascading quality levels
- Efficient resource use

## API Requirements

### BMJ Server
- **API Key**: Not required (uses Europe PMC)
- **Rate Limit**: ~5 requests/sec
- **Cost**: Free

### Scopus Server
- **API Key**: Required (`SCOPUS_API_KEY`)
- **Rate Limit**: 2 requests/sec (free tier)
- **Cost**: Free for research/academic use
- **Registration**: https://dev.elsevier.com/

## Example Flow

**Scenario**: Rare tropical disease not covered by UK guidelines

```
1. Search NICE guidelines → 0 results
2. Trigger literature_fallback()

   3. Search BMJ AND Scopus Q1 in parallel
      ├─ BMJ search: tropical disease
      │  └─ Found 3 articles in BMJ Tropical Medicine
      └─ Scopus Q1 search: tropical disease (≥76th percentile)
         └─ Found 5 articles in Lancet, NEJM, etc.

   4. Combine results from both sources
      └─ Total: 8 high-quality evidence sources
      └─ Extract recommendations from all articles
      └─ STOP (sufficient evidence)

If neither BMJ nor Scopus Q1 had results:
   5. Search Scopus Q2 (fallback)
      └─ Broaden to 51-75th percentile journals
      └─ Find additional research
      └─ Provide best available evidence
```

## Testing

To test the integration:

```bash
# 1. Set up Scopus API key
export SCOPUS_API_KEY='your-key-here'

# 2. Run consultation analysis with rare condition
python -m servers.clinical_decision_support.client \
    --scenario "Patient with dengue fever presenting with warning signs" \
    --country IN

# 3. Observe cascading search in logs:
#    - Guidelines searched first
#    - If insufficient, BMJ and Scopus Q1 triggered in parallel
#    - Results from both sources combined
#    - If still insufficient, Scopus Q2 searched
```

## Monitoring

The system logs each step:

```
[DiagnosisEngine] Available tools: 15
[DiagnosisEngine] Calling tool: search_nice_guidelines
[DiagnosisEngine] Extracted 0 diagnoses

[DiagnosisEngine] Searching BMJ literature (4 tools)
[DiagnosisEngine] Searching Scopus Q1 journals (5 tools)
[DiagnosisEngine] Running 2 searches in parallel...
[DiagnosisEngine] BMJ found 2 diagnoses
[DiagnosisEngine] Scopus Q1 found 3 diagnoses
[DiagnosisEngine] Total diagnoses after parallel search: 5
```

## Benefits

1. **Evidence-Based**: Always provides best available evidence
2. **Quality-Focused**: Prioritizes authoritative sources
3. **Comprehensive**: Doesn't miss rare conditions
4. **Efficient**: Parallel search reduces latency; stops at first sufficient level
5. **Transparent**: Clear evidence hierarchy
6. **Scalable**: Easy to add more literature sources
7. **Fast**: BMJ and Scopus Q1 searched simultaneously for optimal performance

## Future Enhancements

Potential additions:
- Cochrane Library integration
- UpToDate search capability
- PubMed Central full-text access
- Citation network analysis
- Evidence grading (GRADE system)
- Meta-analysis synthesis

---

**Last Updated**: 2025-12-29
**Feature Branch**: `feature/medical-paper-mcps`
**Status**: ✅ Implemented and ready for testing
