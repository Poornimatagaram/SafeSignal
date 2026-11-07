"""Speech-to-text, on the device only (VC-02, VC-03, PV-03). Not built yet (task A2).

Plan: faster-whisper (small or base English model); fallback whisper.cpp. Audio arrives from patient-web on
localhost, never leaves this machine and is deleted after transcription. Never use cloud speech or the browser
SpeechRecognition API.
"""
