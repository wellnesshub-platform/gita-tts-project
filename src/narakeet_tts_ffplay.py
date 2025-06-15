import requests
import subprocess
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
from pathlib import Path

# Translation support
try:
    from googletrans import Translator
    TRANSLATION_AVAILABLE = True
    translator = Translator()
except ImportError:
    TRANSLATION_AVAILABLE = False
    print("Translation not available. Install with: pip install googletrans==4.0.0-rc1")

app = FastAPI()

# Configuration
def load_api_key():
    """Load API key from multiple sources"""
    
    # 1. Environment variable
    api_key = os.getenv('NARAKEET_API_KEY')
    if api_key:
        print("✓ Using API key from environment variable")
        return api_key
    
    # 2. .env file
    env_file = Path('.env')
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('NARAKEET_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"\'')
                        print("✓ Using API key from .env file")
                        return api_key
        except Exception as e:
            print(f"Warning: Could not read .env file: {e}")
    
    # 3. config.txt file
    config_file = Path('config.txt')
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                api_key = f.read().strip()
                if api_key:
                    print("✓ Using API key from config.txt")
                    return api_key
        except Exception as e:
            print(f"Warning: Could not read config.txt: {e}")
    
    raise ValueError("No API key found. Please set NARAKEET_API_KEY environment variable or create config.txt")

# Load API key
try:
    NARAKEET_API_KEY = load_api_key()
    print(f"API Key loaded: {NARAKEET_API_KEY[:10]}...")
except ValueError as e:
    print(f"Error: {e}")
    exit(1)

NARAKEET_BASE_URL = "https://api.narakeet.com/text-to-speech/mp3"
def translate_text(text, target_language='hi'):
    """Translate text to target language using Google Translate"""
    if not TRANSLATION_AVAILABLE:
        print("Warning: Translation not available. Install with: pip install googletrans==4.0.0-rc1")
        return text
    
    try:
        if target_language == 'en':
            return text  # No translation needed
        
        print(f"Translating '{text[:50]}...' to {target_language}")
        
        # Create translator instance each time to avoid connection issues
        translator_instance = Translator()
        result = translator_instance.translate(text, src='en', dest=target_language)
        translated = result.text
        
        print(f"Translation successful: '{translated}'")
        return translated
        
    except Exception as e:
        print(f"Translation error: {e}")
        print(f"Falling back to original text: {text}")
        return text  # Return original text if translation fails

def get_recommended_voice(language='en', gender='male'):
    """Get recommended voice based on language and gender preference"""
    
    voice_recommendations = {
        'en': {
            'male': ['ravi', 'dev', 'rajesh', 'manish', 'himesh'],
            'female': ['anushka', 'deepika', 'neerja', 'pooja', 'vidya']
        },
        'hi': {
            'male': ['amitabh', 'sanjay', 'ranbir', 'varun', 'sunil'],
            'female': ['madhuri', 'kareena', 'rashmi', 'janhvi', 'shreya']
        },
        'sa': {  # Sanskrit - use Hindi voices with slower speed
            'male': ['amitabh', 'sanjay', 'ranbir'],
            'female': ['madhuri', 'kareena', 'rashmi']
        }
    }
    
    return voice_recommendations.get(language, voice_recommendations['en']).get(gender, ['amy'])[0]

OUTPUT_DIR = "audio_output"

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

def play_audio_with_ffplay(filename):
    """Play audio file using ffplay"""
    try:
        print(f"Playing audio: {filename}")
        result = subprocess.run([
            'ffplay', 
            '-nodisp',      # No video display
            '-autoexit',    # Exit when finished
            '-volume', '80', # Set volume
            filename
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("Audio playback completed successfully")
        else:
            print(f"ffplay error: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("Audio playback timed out")
    except FileNotFoundError:
        print("Error: ffplay not found. Please install ffmpeg first:")
        print("  macOS: brew install ffmpeg")
        print("  Ubuntu: sudo apt install ffmpeg")
    except Exception as e:
        print(f"Error playing audio: {e}")

def synthesize_text_to_speech(text, voice="amy", speed=0.85):
    """Synthesize text to speech using Narakeet API"""
    
    # Create unique filename with timestamp and voice
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{voice}-{timestamp}.mp3"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # Prepare the request
    headers = {
        'Accept': 'application/octet-stream',
        'Content-Type': 'text/plain',
        'x-api-key': NARAKEET_API_KEY
    }
    
    params = {
        'voice': voice,
        'speed': speed
    }
    
    print(f"Sending to Narakeet: [voice: {voice}, speed: {speed}]")
    print(f"Text: {text}")
    
    try:
        # Make API request
        response = requests.post(
            NARAKEET_BASE_URL,
            headers=headers,
            params=params,
            data=text.encode('utf-8'),
            timeout=30
        )
        
        print(f"Narakeet response status: {response.status_code}")
        print(f"Response content length: {len(response.content)} bytes")
        
        if response.status_code == 200:
            # Save the audio file
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Audio saved successfully to: {filepath}")
            return filepath
                
        else:
            print(f"❌ ERROR: Narakeet API error {response.status_code}")
            print("Response content:", response.text)
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Request failed: {e}")
        return None
    except Exception as e:
        print(f"❌ ERROR: Unexpected error: {e}")
        return None

@app.post("/synthesize")
async def synthesize_text(request: Request):
    """Synthesize text to speech via POST request with translation support"""
    
    # Get text from request body
    text = (await request.body()).decode('utf-8')
    
    # Get parameters from query string
    voice = request.query_params.get('voice', None)
    speed = float(request.query_params.get('speed', '0.85'))
    play = request.query_params.get('play', 'true').lower() == 'true'
    language = request.query_params.get('language', 'en')  # en, hi, sa (sanskrit)
    gender = request.query_params.get('gender', 'male')    # male, female
    
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    print(f"\n{'='*60}")
    print(f"📝 Processing request:")
    print(f"   Original text: {text}")
    print(f"   Language: {language}")
    print(f"   Gender: {gender}")
    print(f"   Voice: {voice or 'auto-select'}")
    print(f"   Speed: {speed}")
    print(f"   Play: {play}")
    print(f"{'='*60}")
    
    try:
        # Translate if needed
        translated_text = text
        if language == 'hi' and TRANSLATION_AVAILABLE:
            print("🔄 Starting translation to Hindi...")
            translated_text = translate_text(text, 'hi')
            if translated_text != text:
                print(f"✅ Translation completed")
            else:
                print("⚠️  Translation failed, using original text")
        elif language == 'hi' and not TRANSLATION_AVAILABLE:
            print("⚠️  Translation requested but googletrans not installed")
        elif language == 'sa':
            print("📜 Sanskrit mode - using text as provided")
            # For Sanskrit, assume text is already in Sanskrit
            translated_text = text
        else:
            print("🇺🇸 English mode - no translation needed")
        
        # Auto-select voice if not specified
        if not voice:
            voice = get_recommended_voice(language, gender)
            print(f"🎙️  Auto-selected voice: {voice}")
        
        # Adjust speed for Sanskrit (slower for better pronunciation)
        if language == 'sa':
            original_speed = speed
            speed = min(speed, 0.75)  # Cap at 0.75 for Sanskrit
            if speed != original_speed:
                print(f"🐌 Adjusted speed for Sanskrit: {original_speed} → {speed}")
        
        print(f"🔊 Synthesizing audio...")
        audio_file = synthesize_text_to_speech(translated_text, voice, speed)
        
        if audio_file:
            # Always play audio if requested (default true)
            if play:
                print(f"🎵 Playing audio with ffplay...")
                play_audio_with_ffplay(audio_file)
            
            response_data = {
                "success": True,
                "message": "Synthesis completed successfully",
                "original_text": text,
                "final_text": translated_text,
                "translation_used": language != 'en' and translated_text != text,
                "audio_file": os.path.basename(audio_file),
                "full_path": audio_file,
                "voice": voice,
                "language": language,
                "speed": speed,
                "played": play,
                "file_size_bytes": os.path.getsize(audio_file) if os.path.exists(audio_file) else 0
            }
            
            print(f"✅ Success! Audio saved to: {audio_file}")
            print(f"📁 File size: {response_data['file_size_bytes']} bytes")
            
            return JSONResponse(response_data)
        else:
            raise HTTPException(status_code=500, detail="Synthesis failed")
            
    except Exception as e:
        print(f"❌ Error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve audio file"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="audio/mpeg")
    else:
        raise HTTPException(status_code=404, detail="Audio file not found")

@app.get("/list")
async def list_audio_files():
    """List all generated audio files"""
    files = []
    if os.path.exists(OUTPUT_DIR):
        for filename in os.listdir(OUTPUT_DIR):
            if filename.endswith('.mp3'):
                filepath = os.path.join(OUTPUT_DIR, filename)
                stat = os.stat(filepath)
                files.append({
                    "filename": filename,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "url": f"/audio/{filename}"
                })
    return {"files": files}

@app.get("/")
async def root():
    """API documentation"""
    return {
        "message": "Narakeet TTS API with Translation Support",
        "endpoints": {
            "POST /synthesize": "Synthesize text to speech with translation",
            "GET /audio/{filename}": "Download audio file", 
            "GET /list": "List all audio files",
            "GET /voices": "Get available voices by language"
        },
        "languages": {
            "en": "English (Indian accent)",
            "hi": "Hindi (auto-translated)",
            "sa": "Sanskrit (provide Sanskrit text)"
        },
        "example_curl": [
            "# English with Indian accent",
            "curl -X POST 'http://localhost:8081/synthesize?language=en&gender=male&play=true' -d 'Chapter 1, Verse 1. The King Dhritarashtra asked: O Sanjaya! What happened on the sacred battlefield of Kurukshetra?'",
            "",
            "# Auto-translate to Hindi",
            "curl -X POST 'http://localhost:8081/synthesize?language=hi&gender=male&play=true' -d 'Chapter 1, Verse 1. The King Dhritarashtra asked: O Sanjaya! What happened on the sacred battlefield of Kurukshetra?'",
            "",
            "# Sanskrit (provide Sanskrit text)",
            "curl -X POST 'http://localhost:8081/synthesize?language=sa&gender=male&speed=0.7&play=true' -d 'धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः।'"
        ]
    }

@app.get("/voices")
async def get_voices_by_language():
    """Get recommended voices by language"""
    return {
        "english_indian_accent": {
            "male": ["ravi", "dev", "rajesh", "manish", "himesh"],
            "female": ["anushka", "deepika", "neerja", "pooja", "vidya"]
        },
        "hindi": {
            "male": ["amitabh", "sanjay", "ranbir", "varun", "sunil"],
            "female": ["madhuri", "kareena", "rashmi", "janhvi", "shreya"]
        },
        "sanskrit_recommended": {
            "male": ["amitabh", "sanjay", "ranbir"],
            "female": ["madhuri", "kareena", "rashmi"]
        }
    }

if __name__ == "__main__":
    print("Starting Narakeet TTS Server with Translation Support...")
    print("="*60)
    print("API Documentation: http://localhost:8081/")
    print("\nTranslation Support:", "✓ Available" if TRANSLATION_AVAILABLE else "✗ Install googletrans")
    print("\nExample usage:")
    print("\n1. English with Indian accent:")
    print("curl -X POST 'http://localhost:8081/synthesize?language=en&gender=male&play=true' \\")
    print("     -d 'Chapter 1, Verse 1. The King Dhritarashtra asked'")
    print("\n2. Auto-translate to Hindi:")
    print("curl -X POST 'http://localhost:8081/synthesize?language=hi&gender=male&play=true' \\")
    print("     -d 'Chapter 1, Verse 1. The King Dhritarashtra asked'")
    print("\n3. Sanskrit:")
    print("curl -X POST 'http://localhost:8081/synthesize?language=sa&gender=male&speed=0.7&play=true' \\")
    print("     -d 'धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः।'")
    print("="*60)
    
    uvicorn.run(app, host="0.0.0.0", port=8081)