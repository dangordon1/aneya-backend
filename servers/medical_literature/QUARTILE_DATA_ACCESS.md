# Scopus Quartile Data Access Investigation

## Current Status

The Scopus MCP server is functional for searching and retrieving articles, but journal quartile rankings are returning as "unknown".

## Issue Analysis

### What We're Trying to Access

- **SJR Quartile**: Based on SCImago Journal Rank
- **CiteScore Quartile**: Based on Elsevier's CiteScore metric
- **Percentile Rankings**: Used to derive quartile (Q1 = 76-100%, Q2 = 51-75%, etc.)

### Current Implementation

Our `_get_journal_quartile()` function attempts to retrieve:
```python
sjr_list = entry.get("SJRList", {}).get("SJR", [])
citescore_list = entry.get("citeScoreYearInfoList", {}).get("citeScoreYearInfo", [])
```

However, the API is returning an empty or incomplete response for these fields.

## Possible Causes

### 1. API View Parameter Not Specified

The Scopus Serial Title API supports different views:
- **STANDARD**: Basic journal metadata
- **ENHANCED**: Additional metadata
- **CITESCORE**: Includes CiteScore metrics and rankings

**Solution**: Add `view=CITESCORE` parameter to the API request.

```python
params = {
    "issn": issn,
    "view": "CITESCORE"  # Add this parameter
}
```

### 2. API Key Permission Level

Free tier API keys may have limited access to metrics data. Check:
- Your API key tier on the [Elsevier Developer Portal](https://dev.elsevier.com/)
- Whether "Journal Metrics" API access is enabled
- If your institution has Scopus subscription (provides enhanced API access)

**Solution**: Request elevated API access or institutional API key.

### 3. Separate Journal Metrics API

Elsevier may require using a separate API endpoint for metrics:
- Journal Metrics API (separate from Serial Title API)
- Scopus Scival integration
- Direct access to journalmetrics.scopus.com data

### 4. API Response Structure

The API response structure may have changed or differs from documentation.

**Solution**: Add debug logging to inspect actual API responses:

```python
# Debug: Print full API response
print(json.dumps(data, indent=2))
```

## Testing & Verification

### Quick Test

Run this command to check API response:

```bash
curl -X GET \
  "https://api.elsevier.com/content/serial/title?issn=0140-6736&view=CITESCORE" \
  -H "X-ELS-APIKey: YOUR_KEY_HERE" \
  -H "Accept: application/json"
```

Expected response should include:
- `citeScoreYearInfoList`
- `SJRList`
- Quartile/percentile information

### Test with Known High-Impact Journal

The Lancet (ISSN: 0140-6736) is a Q1 journal - perfect for testing.

## Recommended Actions

1. **Add view parameter** to Serial Title API request
2. **Test API response** with curl to see actual data structure
3. **Check API key permissions** on Elsevier Developer Portal
4. **Contact Elsevier support** if view parameter doesn't resolve issue
5. **Consider alternative**: Use Scimago website scraping (with permission) if API access unavailable

## Alternative Approaches

### Option A: Use ScimagoJR CSV Data

Scimago publishes annual journal rankings as CSV files:
- Download from [scimagojr.com](https://www.scimagojr.com/journalrank.php)
- Load into database
- Match journals by ISSN
- Update quarterly

**Pros**: Free, complete data, no API limits
**Cons**: Not real-time, requires maintenance, manual updates

### Option B: Use Scopus Percentiles

If quartile data unavailable, use percentile data:
- API may return percentile even if not quartile
- Calculate quartile from percentile (76-100% = Q1, etc.)

### Option C: Institutional API Access

If affiliated with a university:
- Request institutional Scopus API key
- Usually provides enhanced access
- Contact your library's research support

## References

- [Elsevier Developer Portal - Journal Metrics](https://dev.elsevier.com/journal_metrics.html)
- [CiteScore Journal Metric FAQs](https://service.elsevier.com/app/answers/detail/a_id/30562/supporthub/scopus/)
- [Scopus Metrics Overview](https://www.elsevier.com/products/scopus/metrics)
- [What is CiteScore?](https://service.elsevier.com/app/answers/detail/a_id/14880/supporthub/scopus/kw/percentile/)
- [pybliometrics SerialTitle Documentation](https://pybliometrics.readthedocs.io/en/stable/classes/SerialTitle.html)

## Next Steps

1. Test with `view=CITESCORE` parameter
2. If unsuccessful, test raw API request with curl
3. Check API key permissions
4. Consider implementing ScimagoJR CSV fallback
5. Document actual API response structure for troubleshooting

---

**Last Updated**: 2025-12-29
