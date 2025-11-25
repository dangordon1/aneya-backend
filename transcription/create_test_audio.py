#!/usr/bin/env python
"""Create a short test audio file for transcription testing."""

from gtts import gTTS
import os

# Short clinical phrase for testing
text = "Patient presents with a 3-day history of productive cough with green sputum, fever, 38.5 degrees Celsius, and shortness of breath.  They report feeling generally unwell with fatigue and reduced appetite.  Past medical history includes type 2 diabetes mellitus, well-controlled on metformin, and hypertension.  On remepril, no known drug allergies, non-smoker, on examination, respiratory rate 22 per minute,  oxygen saturation 94% on air, crackles herd in right lower zone on auscultation."

# Create audio file
tts = gTTS(text=text, lang='en', slow=False)
output_file = "test_audio.mp3"
tts.save(output_file)

print(f"✅ Created test audio file: {output_file}")
print(f"📝 Text: {text}")
print(f"📊 File size: {os.path.getsize(output_file)} bytes")
