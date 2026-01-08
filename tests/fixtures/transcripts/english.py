"""
English consultation transcript fixtures.

These transcripts represent typical medical consultations in English.
"""

# Simple 2-speaker consultation
SIMPLE_CONSULTATION = """1. [0.00s - 2.50s] speaker_0:
     Good morning. What brings you in today?

  2. [3.00s - 6.00s] speaker_1:
     I've been having a persistent cough for about a week now.

  3. [6.50s - 9.00s] speaker_0:
     I see. Do you have any fever or difficulty breathing?

  4. [9.50s - 12.00s] speaker_1:
     Yes, I've had a low-grade fever for the past few days."""


# Pregnancy consultation
PREGNANCY_CONSULTATION = """1. [2.00s - 4.56s] speaker_0:
     Okay. Come. What's your name?

  2. [4.56s - 7.20s] speaker_1:
     My name is Selene.

  3. [7.20s - 9.70s] speaker_0:
     Okay. From which place?

  4. [9.70s - 12.50s] speaker_1:
     I'm from London, but I'm in Bangalore for two months.

  5. [14.48s - 17.98s] speaker_0:
     Two months? Okay. Any problem? What's your problem?

  6. [17.98s - 25.90s] speaker_1:
     So, I'm six weeks pregnant, but I've been getting flu, lots of coughs, lots of cold.

  7. [25.90s - 26.26s] speaker_0:
     Mm-hmm.

  8. [26.26s - 39.40s] speaker_1:
     I'm coughing so much I can't sleep all night. I've had fever, vomiting, very sore throat, runny nose.

  9. [39.40s - 39.68s] speaker_0:
     Okay. Since when?

  10. [39.68s - 45.02s] speaker_1:
     Since Wednesday and it's now Sunday, so five days.

  11. [45.02s - 47.66s] speaker_0:
     Okay. Since five days, you have all these symptoms? Have you taken anything for that?

  12. [92.04s - 93.78s] speaker_1:
     Only paracetamol.

  13. [93.78s - 97.10s] speaker_0:
     Only paracetamol? Okay. How much was the dosage?

  14. [97.10s - 103.66s] speaker_1:
     One gram in the morning, one gram in the afternoon."""


# Three speaker consultation (with family member)
THREE_SPEAKER_CONSULTATION = """1. [0.00s - 2.50s] speaker_0:
     Good morning. Please come in and have a seat.

  2. [3.00s - 5.00s] speaker_1:
     Thank you doctor.

  3. [5.50s - 8.00s] speaker_2:
     Doctor, she's been very sick for the past week.

  4. [8.50s - 11.00s] speaker_0:
     I see. Can you tell me what symptoms you've been having?

  5. [11.50s - 15.00s] speaker_1:
     I've had terrible headaches and dizziness.

  6. [15.50s - 19.00s] speaker_2:
     She also hasn't been eating much. I'm very worried.

  7. [19.50s - 23.00s] speaker_0:
     How long have these symptoms been going on?

  8. [23.50s - 26.00s] speaker_1:
     About a week now.

  9. [26.50s - 30.00s] speaker_2:
     Actually doctor, it started last Monday after she came back from work."""


# Pediatric consultation
PEDIATRIC_CONSULTATION = """1. [0.00s - 3.00s] speaker_0:
     Hello! What seems to be the problem with your child today?

  2. [3.50s - 7.00s] speaker_1:
     My son has had a fever for two days. It goes up to 39 degrees.

  3. [7.50s - 10.00s] speaker_0:
     Is he coughing or having any difficulty breathing?

  4. [10.50s - 14.00s] speaker_1:
     Yes, he has a dry cough, especially at night.

  5. [14.50s - 17.00s] speaker_0:
     Any vomiting or diarrhea?

  6. [17.50s - 19.00s] speaker_1:
     No vomiting, but he doesn't want to eat.

  7. [19.50s - 23.00s] speaker_0:
     Is he drinking fluids? That's very important.

  8. [23.50s - 26.00s] speaker_1:
     Yes, I'm giving him water and juice regularly."""


# Pre-diarized segments for API testing
SIMPLE_SEGMENTS = [
    {"speaker_id": "speaker_0", "text": "Good morning. What brings you in today?", "start_time": 0.0, "end_time": 2.5},
    {"speaker_id": "speaker_1", "text": "I've been having a persistent cough for about a week now.", "start_time": 3.0, "end_time": 6.0},
    {"speaker_id": "speaker_0", "text": "I see. Do you have any fever or difficulty breathing?", "start_time": 6.5, "end_time": 9.0},
    {"speaker_id": "speaker_1", "text": "Yes, I've had a low-grade fever for the past few days.", "start_time": 9.5, "end_time": 12.0},
]

PREGNANCY_SEGMENTS = [
    {"speaker_id": "speaker_0", "text": "What's your name?", "start_time": 2.0, "end_time": 4.56},
    {"speaker_id": "speaker_1", "text": "My name is Selene.", "start_time": 4.56, "end_time": 7.20},
    {"speaker_id": "speaker_0", "text": "Any problem? What's your problem?", "start_time": 14.48, "end_time": 17.98},
    {"speaker_id": "speaker_1", "text": "I'm six weeks pregnant, but I've been getting flu, lots of coughs, lots of cold.", "start_time": 17.98, "end_time": 25.90},
    {"speaker_id": "speaker_0", "text": "Have you taken anything for that?", "start_time": 45.02, "end_time": 47.66},
    {"speaker_id": "speaker_1", "text": "Only paracetamol.", "start_time": 92.04, "end_time": 93.78},
]

THREE_SPEAKER_SEGMENTS = [
    {"speaker_id": "speaker_0", "text": "Good morning. Please come in and have a seat.", "start_time": 0.0, "end_time": 2.5},
    {"speaker_id": "speaker_1", "text": "Thank you doctor.", "start_time": 3.0, "end_time": 5.0},
    {"speaker_id": "speaker_2", "text": "Doctor, she's been very sick for the past week.", "start_time": 5.5, "end_time": 8.0},
    {"speaker_id": "speaker_0", "text": "I see. Can you tell me what symptoms you've been having?", "start_time": 8.5, "end_time": 11.0},
    {"speaker_id": "speaker_1", "text": "I've had terrible headaches and dizziness.", "start_time": 11.5, "end_time": 15.0},
    {"speaker_id": "speaker_2", "text": "She also hasn't been eating much. I'm very worried.", "start_time": 15.5, "end_time": 19.0},
]
