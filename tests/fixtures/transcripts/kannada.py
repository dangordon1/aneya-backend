"""
Kannada consultation transcript fixtures.

These transcripts represent typical medical consultations in Kannada (Romanized).
"""

# Simple Kannada consultation
SIMPLE_CONSULTATION = """1. [0.00s - 3.00s] speaker_0:
     Namaskara, nimma samasyenu?

  2. [3.50s - 7.00s] speaker_1:
     Nanage ondu varada indha kemmu ide.

  3. [7.50s - 10.00s] speaker_0:
     Jvara ideyaa?

  4. [10.50s - 13.00s] speaker_1:
     Haagoo, sulpu jvara ide."""


# Pregnancy consultation in Kannada
PREGNANCY_CONSULTATION = """1. [0.00s - 3.00s] speaker_0:
     Namaskara, enu samasye ide?

  2. [3.50s - 7.00s] speaker_1:
     Doctor, naanu 6 vaara garbhini.

  3. [7.50s - 11.00s] speaker_0:
     Ohh, enu tondare ideyaa?

  4. [11.50s - 16.00s] speaker_1:
     Houdu, thumba vaanti aaguttide. Belige inda saanjeyavaregu.

  5. [16.50s - 19.00s] speaker_0:
     Yeshtu dinagalinda haage?

  6. [19.50s - 23.00s] speaker_1:
     Ondu varada indha. Enu tinnalikkilla.

  7. [23.50s - 27.00s] speaker_0:
     Neeru kudeetira?

  8. [27.50s - 30.00s] speaker_1:
     Houdu, neeru kudeetheeni, aadre kammi."""


# General consultation in Kannada
GENERAL_CONSULTATION = """1. [0.00s - 3.00s] speaker_0:
     Heliri, enu samasye?

  2. [3.50s - 7.00s] speaker_1:
     Doctor, nanage thale noovu thumba ide.

  3. [7.50s - 10.00s] speaker_0:
     Yeshtu dinagalinda?

  4. [10.50s - 13.00s] speaker_1:
     Mooru dinagalinda. Raatri nidre bandilla.

  5. [13.50s - 17.00s] speaker_0:
     Kannige tondare ideyaa?

  6. [17.50s - 20.00s] speaker_1:
     Houdu, sulpu vaanti aadange feeling ide."""


# Pre-diarized Kannada segments
SIMPLE_SEGMENTS = [
    {"speaker_id": "speaker_0", "text": "Namaskara, nimma samasyenu?", "start_time": 0.0, "end_time": 3.0},
    {"speaker_id": "speaker_1", "text": "Nanage ondu varada indha kemmu ide.", "start_time": 3.5, "end_time": 7.0},
    {"speaker_id": "speaker_0", "text": "Jvara ideyaa?", "start_time": 7.5, "end_time": 10.0},
    {"speaker_id": "speaker_1", "text": "Haagoo, sulpu jvara ide.", "start_time": 10.5, "end_time": 13.0},
]

PREGNANCY_SEGMENTS = [
    {"speaker_id": "speaker_0", "text": "Namaskara, enu samasye ide?", "start_time": 0.0, "end_time": 3.0},
    {"speaker_id": "speaker_1", "text": "Doctor, naanu 6 vaara garbhini.", "start_time": 3.5, "end_time": 7.0},
    {"speaker_id": "speaker_0", "text": "Ohh, enu tondare ideyaa?", "start_time": 7.5, "end_time": 11.0},
    {"speaker_id": "speaker_1", "text": "Houdu, thumba vaanti aaguttide. Belige inda saanjeyavaregu.", "start_time": 11.5, "end_time": 16.0},
]

GENERAL_SEGMENTS = [
    {"speaker_id": "speaker_0", "text": "Heliri, enu samasye?", "start_time": 0.0, "end_time": 3.0},
    {"speaker_id": "speaker_1", "text": "Doctor, nanage thale noovu thumba ide.", "start_time": 3.5, "end_time": 7.0},
    {"speaker_id": "speaker_0", "text": "Yeshtu dinagalinda?", "start_time": 7.5, "end_time": 10.0},
    {"speaker_id": "speaker_1", "text": "Mooru dinagalinda. Raatri nidre bandilla.", "start_time": 10.5, "end_time": 13.0},
]
