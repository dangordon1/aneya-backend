"""
Hindi consultation transcript fixtures.

These transcripts represent typical medical consultations in Hindi (Romanized).
"""

# Simple Hindi consultation
SIMPLE_CONSULTATION = """1. [0.00s - 3.00s] speaker_0:
     Namaste, aapko kya problem hai?

  2. [3.50s - 7.00s] speaker_1:
     Mujhe ek hafta se khansi aa rahi hai.

  3. [7.50s - 10.00s] speaker_0:
     Kya aapko bukhar bhi hai?

  4. [10.50s - 13.00s] speaker_1:
     Haan, thoda bukhar bhi hai."""


# Pregnancy consultation in Hindi
PREGNANCY_CONSULTATION = """1. [0.00s - 3.00s] speaker_0:
     Namaste, bataiye kya takleef hai?

  2. [3.50s - 8.00s] speaker_1:
     Doctor sahab, main 6 week pregnant hoon.

  3. [8.50s - 11.00s] speaker_0:
     Achha, koi problem ho rahi hai?

  4. [11.50s - 17.00s] speaker_1:
     Haan, mujhe bahut zyada ulti aa rahi hai. Subah se shaam tak ulti hoti hai.

  5. [17.50s - 20.00s] speaker_0:
     Kab se ho raha hai ye?

  6. [20.50s - 24.00s] speaker_1:
     Ek hafta se. Kuch bhi khana nahi rakh paa rahi.

  7. [24.50s - 28.00s] speaker_0:
     Paani peeti ho?

  8. [28.50s - 31.00s] speaker_1:
     Haan, paani to pee rahi hoon, lekin kam.

  9. [31.50s - 36.00s] speaker_0:
     Achha, main aapko kuch dawai deta hoon. Aur kuch blood tests bhi karwane honge."""


# General health consultation in Hindi
GENERAL_CONSULTATION = """1. [0.00s - 2.50s] speaker_0:
     Bataiye, kya takleef hai aapko?

  2. [3.00s - 7.00s] speaker_1:
     Doctor, mujhe sar mein bahut dard ho raha hai.

  3. [7.50s - 10.00s] speaker_0:
     Kab se ho raha hai?

  4. [10.50s - 13.00s] speaker_1:
     Teen din se. Raat ko neend bhi nahi aati.

  5. [13.50s - 16.00s] speaker_0:
     Kya aankho mein taklif hai? Ya ulti jaisi feeling?

  6. [16.50s - 19.00s] speaker_1:
     Haan, thodi ulti jaisi feeling hai.

  7. [19.50s - 23.00s] speaker_0:
     Blood pressure check karte hain pehle. Aap ye table par baith jaiye."""


# Pre-diarized Hindi segments
SIMPLE_SEGMENTS = [
    {"speaker_id": "speaker_0", "text": "Namaste, aapko kya problem hai?", "start_time": 0.0, "end_time": 3.0},
    {"speaker_id": "speaker_1", "text": "Mujhe ek hafta se khansi aa rahi hai.", "start_time": 3.5, "end_time": 7.0},
    {"speaker_id": "speaker_0", "text": "Kya aapko bukhar bhi hai?", "start_time": 7.5, "end_time": 10.0},
    {"speaker_id": "speaker_1", "text": "Haan, thoda bukhar bhi hai.", "start_time": 10.5, "end_time": 13.0},
]

PREGNANCY_SEGMENTS = [
    {"speaker_id": "speaker_0", "text": "Namaste, bataiye kya takleef hai?", "start_time": 0.0, "end_time": 3.0},
    {"speaker_id": "speaker_1", "text": "Doctor sahab, main 6 week pregnant hoon.", "start_time": 3.5, "end_time": 8.0},
    {"speaker_id": "speaker_0", "text": "Achha, koi problem ho rahi hai?", "start_time": 8.5, "end_time": 11.0},
    {"speaker_id": "speaker_1", "text": "Haan, mujhe bahut zyada ulti aa rahi hai. Subah se shaam tak ulti hoti hai.", "start_time": 11.5, "end_time": 17.0},
    {"speaker_id": "speaker_0", "text": "Kab se ho raha hai ye?", "start_time": 17.5, "end_time": 20.0},
    {"speaker_id": "speaker_1", "text": "Ek hafta se. Kuch bhi khana nahi rakh paa rahi.", "start_time": 20.5, "end_time": 24.0},
]

GENERAL_SEGMENTS = [
    {"speaker_id": "speaker_0", "text": "Bataiye, kya takleef hai aapko?", "start_time": 0.0, "end_time": 2.5},
    {"speaker_id": "speaker_1", "text": "Doctor, mujhe sar mein bahut dard ho raha hai.", "start_time": 3.0, "end_time": 7.0},
    {"speaker_id": "speaker_0", "text": "Kab se ho raha hai?", "start_time": 7.5, "end_time": 10.0},
    {"speaker_id": "speaker_1", "text": "Teen din se. Raat ko neend bhi nahi aati.", "start_time": 10.5, "end_time": 13.0},
]
