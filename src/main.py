#!/usr/bin/env python3
import os
import logging
from typing import Dict, Optional
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from google.cloud import texttospeech
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Bhagavad Gita TTS API", version="1.0.0")

try:
    tts_client = texttospeech.TextToSpeechClient()
    logger.info("TTS client initialized")
except Exception as e:
    logger.error(f"Failed to initialize TTS client: {e}")
    tts_client = None

@app.get("/")
async def root():
    return {
        "message": "Bhagavad Gita TTS API",
        "status": "healthy" if tts_client else "degraded",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    return {"status": "ok", "tts_available": tts_client is not None}

def create_natural_ssml(text: str, language: str = "en-IN") -> str:
    if not text:
        return ""
    
    text = re.sub(r'\s+', ' ', text.strip())
    
    if language == "hi-IN":
        text = re.sub(r'अध्याय\s+(\d+)', r'अध्याय <say-as interpret-as="cardinal">\1</say-as>', text)
        text = re.sub(r'श्लोक\s+(\d+)', r'श्लोक <say-as interpret-as="cardinal">\1</say-as>', text)
        text = re.sub(r'।', '<break time="0.7s"/>', text)
        text = re.sub(r'॥', '<break time="1.2s"/>', text)
        
        return f'''<speak>
            <prosody rate="0.92" pitch="+1st" volume="+6dB">
                <emphasis level="reduced">
                    {text}
                </emphasis>
            </prosody>
        </speak>'''
    
    else:
        text = re.sub(r'Chapter\s+(\d+)', r'Chapter <say-as interpret-as="cardinal">\1</say-as>', text)
        text = re.sub(r'Verse\s+(\d+)', r'Verse <say-as interpret-as="cardinal">\1</say-as>', text)
        
        text = re.sub(r'([.!?])\s*', r'\1<break time="1.0s"/>', text)
        text = re.sub(r'([,;])\s*', r'\1<break time="0.5s"/>', text)
        text = re.sub(r'(:)\s*', r'\1<break time="0.7s"/>', text)
        
        text = re.sub(r'\bO\s+([A-Z]\w+)', r'<emphasis level="strong">O <break time="0.2s"/>\1</emphasis>', text)
        
        name_replacements = {
            'Sanjaya': '<phoneme alphabet="ipa" ph="sənˈdʒaɪə">Sanjaya</phoneme>',
            'Dhritarashtra': '<phoneme alphabet="ipa" ph="ˈdʰrɪtəˌraːʂtrə">Dhritarashtra</phoneme>',
            'Kurukshetra': '<phoneme alphabet="ipa" ph="ˈkʊrʊkˌʃetrə">Kurukshetra</phoneme>',
            'Pandavas': '<phoneme alphabet="ipa" ph="ˈpaːɳɖəvəs">Pandavas</phoneme>'
        }
        
        for name, phoneme in name_replacements.items():
            text = re.sub(rf'\b{name}\b', phoneme, text)
        
        text = re.sub(r'\b(asked|said|spoke|declared|inquired)\b', r'<emphasis level="moderate">\1</emphasis>', text)
        
        return f'''<speak>
            <prosody rate="0.93" pitch="+0.5st" volume="+5dB">
                <emphasis level="moderate">
                    <prosody range="15%">
                        {text}
                    </prosody>
                </emphasis>
            </prosody>
        </speak>'''

@app.post("/synthesize/verse")
async def synthesize_verse(
    verse_data: Dict,
    author: str = "purohit",
    language: str = "en-IN",
    voice_name: Optional[str] = None,
    quality: str = "ultra"
):
    if not tts_client:
        raise HTTPException(status_code=503, detail="TTS service unavailable")
    
    try:
        author_data = verse_data.get(author, {})
        text = author_data.get('et') or author_data.get('ht') or author_data.get('sc', '')
        
        if not text:
            raise HTTPException(status_code=400, detail=f"No text found for author: {author}")
        
        chapter = verse_data.get('chapter', 'Unknown')
        verse_num = verse_data.get('verse', 'Unknown')
        
        if language == "hi-IN":
            intro = f"अध्याय {chapter}, श्लोक {verse_num}"
        else:
            intro = f"Chapter {chapter}, Verse {verse_num}"
        
        full_text = f"{intro}. {text}"
        processed_text = create_natural_ssml(full_text, language)
        
        ultra_voices = {
            "en-IN": [
                ("en-IN-Studio-B", texttospeech.SsmlVoiceGender.MALE),
                ("en-IN-Studio-C", texttospeech.SsmlVoiceGender.FEMALE),
                ("en-IN-Neural2-B", texttospeech.SsmlVoiceGender.MALE),
                ("en-IN-Neural2-A", texttospeech.SsmlVoiceGender.FEMALE),
                ("en-IN-Neural2-C", texttospeech.SsmlVoiceGender.MALE),
                ("en-IN-Neural2-D", texttospeech.SsmlVoiceGender.FEMALE),
            ],
            "hi-IN": [
                ("hi-IN-Neural2-A", texttospeech.SsmlVoiceGender.FEMALE),
                ("hi-IN-Neural2-B", texttospeech.SsmlVoiceGender.MALE),
                ("hi-IN-Neural2-C", texttospeech.SsmlVoiceGender.MALE),
                ("hi-IN-Neural2-D", texttospeech.SsmlVoiceGender.FEMALE),
            ]
        }
        
        available_voices = ultra_voices.get(language, ultra_voices["en-IN"])
        
        if voice_name:
            selected_voice = next((v for v in available_voices if v[0] == voice_name), available_voices[0])
        else:
            selected_voice = available_voices[0]
        
        selected_voice_name, voice_gender = selected_voice
        
        synthesis_input = texttospeech.SynthesisInput(ssml=processed_text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=language,
            name=selected_voice_name,
            ssml_gender=voice_gender
        )
        
        if quality == "ultra":
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                speaking_rate=0.93,
                pitch=0.5,
                volume_gain_db=4.0,
                sample_rate_hertz=48000,
                effects_profile_id=["large-home-entertainment-class-device"]
            )
        else:
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=0.9,
                pitch=0.0,
                volume_gain_db=2.0,
                sample_rate_hertz=24000,
                effects_profile_id=["headphone-class-device"]
            )
        
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        def generate_audio():
            yield response.audio_content
        
        verse_id = verse_data.get('_id', 'unknown')
        
        if quality == "ultra":
            media_type = "audio/wav"
            file_ext = "wav"
        else:
            media_type = "audio/mpeg"
            file_ext = "mp3"
        
        return StreamingResponse(
            generate_audio(),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename=verse_{verse_id}_ultra.{file_ext}",
                "X-Verse-ID": verse_id,
                "X-Voice-Used": selected_voice_name,
                "X-Quality": quality,
                "X-Sample-Rate": "48000" if quality == "ultra" else "24000"
            }
        )
        
    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/voices")
async def get_voices():
    return {
        "ultra_voices": {
            "en-IN": [
                {"name": "en-IN-Studio-B", "gender": "male", "quality": "studio", "recommended": True, "description": "Ultra-natural storytelling"},
                {"name": "en-IN-Studio-C", "gender": "female", "quality": "studio", "description": "Professional broadcast quality"},
                {"name": "en-IN-Neural2-B", "gender": "male", "quality": "neural", "description": "Most natural male voice"},
                {"name": "en-IN-Neural2-A", "gender": "female", "quality": "neural", "description": "Expressive female voice"}
            ]
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)