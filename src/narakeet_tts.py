#!/usr/bin/env python3
import os
import logging
from typing import Dict, Optional
import re
import requests
import asyncio
import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Bhagavad Gita TTS API - Narakeet Edition", version="2.0.0")

NARAKEET_API_KEY = os.getenv('NARAKEET_API_KEY')
NARAKEET_BASE_URL = "https://api.narakeet.com"

if not NARAKEET_API_KEY:
    logger.warning("NARAKEET_API_KEY not found in environment variables")

@app.get("/")
async def root():
    return {
        "message": "Bhagavad Gita TTS API - Narakeet Edition",
        "status": "healthy" if NARAKEET_API_KEY else "degraded",
        "version": "2.0.0",
        "provider": "Narakeet"
    }

@app.get("/health")
async def health():
    return {
        "status": "ok", 
        "narakeet_available": bool(NARAKEET_API_KEY),
        "api_key_configured": bool(NARAKEET_API_KEY)
    }

def format_text_for_narakeet(text: str, language: str = "en-IN") -> str:
    if not text:
        return ""
    
    text = re.sub(r'\s+', ' ', text.strip())
    
    if language.startswith("hi"):
        text = re.sub(r'अध्याय\s+(\d+)', r'अध्याय \1', text)
        text = re.sub(r'श्लोक\s+(\d+)', r'श्लोक \1', text)
        text = re.sub(r'।\s*', '। ', text)
        text = re.sub(r'॥\s*', '॥ ', text)
        return text
    
    else:
        text = re.sub(r'Chapter\s+(\d+)', r'Chapter \1', text)
        text = re.sub(r'Verse\s+(\d+)', r'Verse \1', text)
        
        text = re.sub(r'([.!?])\s*', r'\1 ', text)
        text = re.sub(r'([,;:])\s*', r'\1 ', text)
        
        text = re.sub(r'\bO\s+([A-Z]\w+)', r'O \1', text)
        print(f"Sending to Narakeet: {text}")
        return text


async def synthesize_with_narakeet(text: str, voice: str = "anika") -> bytes:
    print(f"Sending to Narakeet: {text}")
    if not NARAKEET_API_KEY:
        raise HTTPException(status_code=503, detail="Narakeet API key not configured")
    
    headers = {
        'X-API-Key': NARAKEET_API_KEY,
        'Content-Type': 'text/plain',
        'Accept': 'audio/mpeg'
    }
    
    url = f"{NARAKEET_BASE_URL}/text-to-speech/mp3"
    params = {
        'voice': voice
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, 
                headers=headers, 
                params=params, 
                data=text.encode('utf-8'),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    return await response.read()
                else:
                    error_text = await response.text()
                    logger.error(f"Narakeet API error {response.status}: {error_text}")
                    raise HTTPException(
                        status_code=response.status, 
                        detail=f"Narakeet API error: {error_text}"
                    )
                    
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Narakeet API timeout")
    except Exception as e:
        logger.error(f"Narakeet synthesis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")

@app.post("/synthesize/verse")
async def synthesize_verse(
    verse_data: Dict,
    author: str = "purohit",
    language: str = "en-IN",
    voice: str = "anika",
    speed: float = 1.0
):
    try:
        author_data = verse_data.get(author, {})
        text = author_data.get('et') or author_data.get('ht') or author_data.get('sc', '')
        
        if not text:
            raise HTTPException(status_code=400, detail=f"No text found for author: {author}")
        
        chapter = verse_data.get('chapter', 'Unknown')
        verse_num = verse_data.get('verse', 'Unknown')
        
        if language.startswith("hi"):
            intro = f"अध्याय {chapter}, श्लोक {verse_num}"
        else:
            intro = f"Chapter {chapter}, Verse {verse_num}"
        
        full_text = f"{intro}. {text}"
        formatted_text = format_text_for_narakeet(full_text, language)
        
        if speed != 1.0:
            formatted_text = f"[speed: {speed}]\n{formatted_text}"
        
        audio_data = await synthesize_with_narakeet(formatted_text, voice)
        
        def generate_audio():
            yield audio_data
        
        verse_id = verse_data.get('_id', 'unknown')
        return StreamingResponse(
            generate_audio(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename=verse_{verse_id}_narakeet.mp3",
                "X-Verse-ID": verse_id,
                "X-Voice-Used": voice,
                "X-Provider": "Narakeet",
                "X-Quality": "Premium",
                "X-Speed": str(speed)
            }
        )
        
    except Exception as e:
        logger.error(f"Synthesis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/voices")
async def get_voices():
    return {
        "narakeet_voices": {
            "english_indian": [
                {"name": "anika", "gender": "female", "accent": "Indian", "quality": "premium", "recommended": True},
                {"name": "kiran", "gender": "male", "accent": "Indian", "quality": "premium"},
                {"name": "isha", "gender": "female", "accent": "Indian", "quality": "premium"},
                {"name": "arjun", "gender": "male", "accent": "Indian", "quality": "premium"}
            ]
        }
    }

@app.get("/languages")
async def get_languages():
    return {
        "languages": [
            {"code": "en-IN", "name": "English (Indian)", "native_name": "English"},
            {"code": "hi-IN", "name": "Hindi", "native_name": "हिन्दी"}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
