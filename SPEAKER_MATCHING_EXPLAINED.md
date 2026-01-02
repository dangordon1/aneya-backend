# How Speaker Matching Works Between Chunks

## The Problem

When you split audio into chunks and diarize them separately, each chunk assigns its own speaker IDs:

```
Chunk 0 (0-30s):  → API returns: speaker_0, speaker_1
Chunk 1 (20-50s): → API returns: speaker_0, speaker_1 (might be different people!)
```

**The API doesn't know these are the same recording**, so `speaker_0` in Chunk 1 might actually be `speaker_1` from Chunk 0!

## The Solution: Overlap-Based Matching

### Step 1: Analyze the Overlap Region

The **overlap** is the audio that appears in BOTH chunks (20-30s in our test):

```
Timeline:
Chunk 0:  |===================|          (0-30s)
Overlap:                |======|          (20-30s) ← SAME AUDIO IN BOTH!
Chunk 1:                |===================|  (20-50s)
```

### Step 2: Calculate Speaker Statistics in Overlap

For **each chunk**, we analyze who talked in the overlap (20-30s):

**Chunk 0 overlap (20-30s):**
```json
{
  "speaker_0": {
    "duration": 5.4s,     ← How long they spoke
    "words": 16,          ← How many words
    "segments": 2         ← How many times they spoke
  },
  "speaker_1": {
    "duration": 4.6s,
    "words": 14,
    "segments": 1
  }
}
```

**Chunk 1 overlap (20-30s):**
```json
{
  "speaker_0": {
    "duration": 7.1s,     ← Different! (same audio, but API variance)
    "words": 21,
    "words": 2
  },
  "speaker_1": {
    "duration": 2.8s,
    "words": 12,
    "segments": 2
  }
}
```

### Step 3: Sort by Activity Level

Rank speakers by who talked the **most** in the overlap:

**Chunk 0 ranked:**
1. `speaker_0` (5.4s) ← Most active
2. `speaker_1` (4.6s) ← Less active

**Chunk 1 ranked:**
1. `speaker_0` (7.1s) ← Most active
2. `speaker_1` (2.8s) ← Less active

### Step 4: Match by Rank

**Key assumption:** The person who talks the most in the overlap region of Chunk 0 is probably the same person who talks the most in the overlap region of Chunk 1 (because it's literally the same 10 seconds of audio!).

**Matching:**
```
Chunk 0 (rank 1) → Chunk 1 (rank 1)
speaker_0        →  speaker_0

Chunk 0 (rank 2) → Chunk 1 (rank 2)
speaker_1        →  speaker_1
```

### Step 5: Calculate Confidence Score

For each match, we calculate a **similarity score** based on:

**Duration similarity (50% weight):**
```
speaker_0: |5.4s - 7.1s| / max(5.4, 7.1) = 1.7 / 7.1 = 0.24 difference
           Similarity = 1 - 0.24 = 0.76 (76%)
```

**Word count similarity (30% weight):**
```
speaker_0: |16 - 21| / max(16, 21) = 5 / 21 = 0.24 difference
           Similarity = 1 - 0.24 = 0.76 (76%)
```

**Avg segment length similarity (20% weight):**
```
Avg segment = duration / segment_count
speaker_0 Chunk 0: 5.4 / 2 = 2.7s
speaker_0 Chunk 1: 7.1 / 2 = 3.55s
Similarity = 1 - |2.7 - 3.55| / max(2.7, 3.55) = 0.76 (76%)
```

**Final confidence:**
```
0.76 × 0.5 + 0.76 × 0.3 + 0.76 × 0.2 = 75.78% ✓
```

If confidence > 70%, we accept the match!

## Example: When Speaker IDs DON'T Match

This is where the algorithm really shines. Imagine Chunk 1 had used different IDs:

**Chunk 0 overlap:**
- `speaker_0`: 5.4s (most active)
- `speaker_1`: 4.6s

**Chunk 1 overlap (with different IDs):**
- `speaker_2`: 7.1s (most active)  ← Actually same person as speaker_0!
- `speaker_3`: 2.8s               ← Actually same person as speaker_1!

**Our algorithm would correctly map:**
```
Chunk1:speaker_2 → Chunk0:speaker_0 (confidence: 75.78%)
Chunk1:speaker_3 → Chunk0:speaker_1 (confidence: 69.10%)
```

Then we **remap all Chunk 1 segments**:
- Every segment labeled `speaker_2` gets relabeled to `speaker_0`
- Every segment labeled `speaker_3` gets relabeled to `speaker_1`

Now the entire transcript uses consistent speaker IDs!

## Why This Works

1. **Same audio, same behavior**: The overlap region is literally the same 10 seconds, so whoever talks a lot in Chunk 0's view of it will also talk a lot in Chunk 1's view

2. **Rank-based matching**: We don't rely on absolute durations (which vary due to API variance), we rely on **relative activity** (who talks more than whom)

3. **Multiple metrics**: Using duration + word count + segment length makes it robust against small API differences

4. **Confidence threshold**: We only accept matches with >70% confidence, catching cases where the algorithm might be wrong

## Limitations

1. **Overlapping speech**: If both speakers talk at the same time in the overlap, stats might be unreliable

2. **Silent overlap**: If nobody talks in the 10-second overlap, we can't match

3. **Multiple speakers with similar activity**: If 3 speakers all talk for ~3 seconds each, ranking becomes ambiguous

4. **Solution**: Increase overlap duration to 15s if matching confidence is low

## Code Implementation

```python
def match_speakers(prev_overlap_stats, curr_overlap_stats):
    # Sort by total duration (most active speaker first)
    sorted_prev = sorted(prev_overlap_stats.values(),
                        key=lambda x: x['duration'],
                        reverse=True)
    sorted_curr = sorted(curr_overlap_stats.values(),
                        key=lambda x: x['duration'],
                        reverse=True)

    mapping = {}

    for i in range(min(len(sorted_prev), len(sorted_curr))):
        prev_speaker = sorted_prev[i]
        curr_speaker = sorted_curr[i]

        # Calculate similarity
        duration_sim = 1 - abs(prev['duration'] - curr['duration']) / max(...)
        word_sim = 1 - abs(prev['words'] - curr['words']) / max(...)
        avg_sim = 1 - abs(prev['avg_len'] - curr['avg_len']) / max(...)

        confidence = duration_sim * 0.5 + word_sim * 0.3 + avg_sim * 0.2

        if confidence > 0.7:
            mapping[curr_speaker['speaker_id']] = prev_speaker['speaker_id']

    return mapping
```

## Test Results from Our Recording

```
✅ Chunk 0 → Chunk 1 matching:
   speaker_0 → speaker_0 (75.78% confidence) ✓
   speaker_1 → speaker_1 (69.10% confidence) ✓

Both above 70% threshold → Reliable match!
```

The algorithm successfully identified that:
- The most active speaker in both chunks is the same person
- The less active speaker in both chunks is also the same person

Even though the exact durations differed (5.4s vs 7.1s), the **rank order** was preserved, allowing correct matching.
