import requests
import subprocess
import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Query
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
OUTPUT_DIR = "audio_output"

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

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
        'gu': {  # Gujarati
            'male': ['ramesh', 'pratik'],
            'female': ['asha', 'manasi']
        },
        'sa': {  # Sanskrit - use Hindi voices since Sanskrit is not supported
            'male': ['amitabh', 'sanjay', 'ranbir'],
            'female': ['madhuri', 'kareena', 'rashmi']
        }
    }
    
    return voice_recommendations.get(language, voice_recommendations['en']).get(gender, ['amy'])[0]

def prepare_sanskrit_text_for_tts(sanskrit_text, use_transliteration=True):
    """
    Prepare Sanskrit text for TTS by converting to appropriate format.
    Since Narakeet doesn't support Sanskrit directly, we use Hindi voices.
    """
    if not sanskrit_text:
        return None
    
    # Clean up the text - remove formatting and punctuation
    import re
    cleaned_text = sanskrit_text.strip()
    
    # Remove verse numbers and formatting marks
    cleaned_text = re.sub(r'\|\|?\d*\|\|?', '', cleaned_text)  # Remove ||1|| style numbers
    cleaned_text = re.sub(r'\|', ' ', cleaned_text)  # Replace | with spaces
    cleaned_text = re.sub(r'।', ' ', cleaned_text)  # Replace । with spaces
    cleaned_text = re.sub(r'—', ' ', cleaned_text)  # Replace em dash
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()  # Clean whitespace
    
    if not use_transliteration:
        # Just return cleaned Devanagari text
        return cleaned_text
    
    # If transliteration requested, do basic word replacements only
    # (Don't attempt character-by-character transliteration as it's error-prone)
    word_replacements = {
        'धृतराष्ट्र': 'dhritarashtra',
        'उवाच': 'uvaacha',
        'धर्मक्षेत्रे': 'dharmakshetre',
        'कुरुक्षेत्रे': 'kurukshetre', 
        'समवेता': 'samaveta',
        'युयुत्सवः': 'yuyutsavah',
        'मामकाः': 'maamakaah',
        'पाण्डवाः': 'paandavaah',
        'किमकुर्वत': 'kimakurvata',
        'सञ्जय': 'sanjaya',
    }
    
    # Apply word-level replacements
    for sanskrit_word, roman_word in word_replacements.items():
        cleaned_text = cleaned_text.replace(sanskrit_word, roman_word)
    
    return cleaned_text

def convert_to_internal_format(verse_data):
    """
    Convert individual verse data to internal format expected by the TTS processing pipeline.
    """
    # If it's already in the old detailed format, return as-is
    if any(key in verse_data for key in ['tej', 'siva', 'prabhu']):
        return verse_data
    
    # Convert new format to internal format
    internal_format = {
        "_id": verse_data.get("_id", ""),
        "chapter": verse_data.get("chapter", 0),
        "verse": verse_data.get("verse", 0),
        "slok": verse_data.get("slok", ""),
        "transliteration": verse_data.get("transliteration", "")
    }
    
    # Add direct language fields if they exist
    if "en" in verse_data:
        internal_format["en"] = verse_data["en"]
    if "hi" in verse_data:
        internal_format["hi"] = verse_data["hi"]
    if "gu" in verse_data:
        internal_format["gu"] = verse_data["gu"]
    
    # Add YOUR format fields if they exist
    if "sanskrit" in verse_data:
        internal_format["sanskrit"] = verse_data["sanskrit"]
    if "english" in verse_data:
        internal_format["english"] = verse_data["english"]
    if "hindi" in verse_data:
        internal_format["hindi"] = verse_data["hindi"]
    if "gujarati" in verse_data:
        internal_format["gujarati"] = verse_data["gujarati"]
    
    return internal_format

def extract_text_from_gita_json(verse_data, text_type='english'):
    """FIXED VERSION - Extract text that handles YOUR JSON format with sanskrit/english/hindi/gujarati fields"""
    
    verse_id = verse_data.get('_id', 'Unknown')
    
    if text_type == 'sanskrit':
        # Check YOUR format first (sanskrit field)
        sanskrit_text = verse_data.get('sanskrit', '')
        if sanskrit_text:
            print(f"   📜 Using 'sanskrit' field for {verse_id}")
            return sanskrit_text
        
        # Then try standard transliteration field
        transliteration = verse_data.get('transliteration', '')
        if transliteration:
            print(f"   📜 Using transliteration for {verse_id}")
            return transliteration
        
        # Then try standard slok field
        slok = verse_data.get('slok', '')
        if slok:
            print(f"   📜 Using slok (Devanagari) for {verse_id}")
            return slok
        
        # Check if there's a 'sa' field
        sa_field = verse_data.get('sa', '')
        if sa_field:
            print(f"   📜 Using 'sa' field for {verse_id}")
            return sa_field
        
        # Check old format commentaries for Sanskrit transliteration
        old_format_sources = ['tej', 'siva', 'prabhu', 'rams', 'sankar']
        for source in old_format_sources:
            if source in verse_data and isinstance(verse_data[source], dict):
                if 'st' in verse_data[source]:
                    print(f"   📜 Using {source}.st for {verse_id}")
                    return verse_data[source]['st']
        
        print(f"   ❌ No Sanskrit text found for {verse_id}")
        return None
    
    elif text_type == 'sanskrit_devanagari':
        # Check YOUR format first
        sanskrit_text = verse_data.get('sanskrit', '')
        if sanskrit_text:
            print(f"   📜 Using 'sanskrit' field (Devanagari) for {verse_id}")
            return sanskrit_text
        
        # For Devanagari script - try standard slok field
        slok = verse_data.get('slok', '')
        if slok:
            print(f"   📜 Using slok (Devanagari) for {verse_id}")
            return slok
        
        # Check old format for Devanagari
        old_format_sources = ['tej', 'siva', 'prabhu', 'rams', 'sankar']
        for source in old_format_sources:
            if source in verse_data and isinstance(verse_data[source], dict):
                if 'sd' in verse_data[source]:
                    print(f"   📜 Using {source}.sd for {verse_id}")
                    return verse_data[source]['sd']
        
        print(f"   ❌ No Devanagari text found for {verse_id}")
        return None
    
    elif text_type == 'hindi':
        # Check YOUR format first (hindi field)
        hindi_text = verse_data.get('hindi', '')
        if hindi_text:
            print(f"   🇮🇳 Using 'hindi' field for {verse_id}")
            return hindi_text
        
        # NEW FORMAT: Check for direct 'hi' field
        if 'hi' in verse_data:
            print(f"   🇮🇳 Using direct 'hi' field for {verse_id}")
            return verse_data['hi']
        
        # OLD FORMAT: Fallback to commentaries
        hindi_sources = ['tej', 'rams', 'sankar', 'siva', 'prabhu']
        for source in hindi_sources:
            if source in verse_data and isinstance(verse_data[source], dict):
                if 'ht' in verse_data[source]:
                    print(f"   🇮🇳 Using {source}.ht for {verse_id}")
                    return verse_data[source]['ht']
        
        print(f"   ❌ No Hindi text found for {verse_id}")
        return None
    
    elif text_type == 'gujarati':
        # Check YOUR format first (gujarati field)
        gujarati_text = verse_data.get('gujarati', '')
        if gujarati_text:
            print(f"   🇮🇳 Using 'gujarati' field for {verse_id}")
            return gujarati_text
        
        # NEW FORMAT: Check for direct 'gu' field
        if 'gu' in verse_data:
            print(f"   🇮🇳 Using direct 'gu' field for {verse_id}")
            return verse_data['gu']
        
        # Check old format if available
        old_format_sources = ['tej', 'siva', 'prabhu']
        for source in old_format_sources:
            if source in verse_data and isinstance(verse_data[source], dict):
                if 'gt' in verse_data[source]:
                    print(f"   🇮🇳 Using {source}.gt for {verse_id}")
                    return verse_data[source]['gt']
        
        print(f"   ❌ No Gujarati text found for {verse_id}")
        return None
    
    elif text_type == 'english':
        # Check YOUR format first (english field)
        english_text = verse_data.get('english', '')
        if english_text:
            print(f"   🇺🇸 Using 'english' field for {verse_id}")
            return english_text
        
        # NEW FORMAT: Check for direct 'en' field
        if 'en' in verse_data:
            print(f"   🇺🇸 Using direct 'en' field for {verse_id}")
            return verse_data['en']
        
        # OLD FORMAT: Fallback to commentaries
        english_sources = ['prabhu', 'siva', 'purohit', 'san', 'adi', 'gambir', 'tej']
        for source in english_sources:
            if source in verse_data and isinstance(verse_data[source], dict):
                if 'et' in verse_data[source]:
                    print(f"   🇺🇸 Using {source}.et for {verse_id}")
                    return verse_data[source]['et']
        
        print(f"   ❌ No English text found for {verse_id}")
        return None
    
    print(f"   ❓ Unknown text_type: {text_type}")
    return None

def flatten_chapter_format(data):
    """Convert chapter-based format to flat verse list"""
    
    if isinstance(data, list):
        # Check if it's already a flat list of verses
        if data and '_id' in data[0]:
            return data  # Already flat format
        
        # Check if it's chapter-based format
        if data and 'chapter' in data[0] and 'verses' in data[0]:
            flattened = []
            for chapter_data in data:
                chapter_num = chapter_data.get('chapter', 0)
                verses = chapter_data.get('verses', [])
                
                for verse in verses:
                    # Ensure chapter info is preserved
                    verse['chapter'] = chapter_num
                    flattened.append(verse)
            
            print(f"📚 Converted chapter-based format: {len(data)} chapters → {len(flattened)} verses")
            return flattened
    
    # Single verse or other format
    return data if isinstance(data, list) else [data]

def detect_format_and_process(data):
    """Detect the format and process accordingly"""
    
    if isinstance(data, dict):
        # Check if it's a chapters-based structure
        if 'chapters' in data:
            print("🔍 Detected: Chapter-based format with 'chapters' key")
            flattened = []
            verse_count = 0
            for chapter in data['chapters']:
                chapter_num = chapter.get('chapter_number', 1)
                for verse in chapter.get('verses', []):
                    # Add chapter number to verse data
                    verse['chapter'] = chapter_num
                    flattened.append(convert_to_internal_format(verse))
                    verse_count += 1
            
            print(f"📚 Converted chapter-based format: {len(data['chapters'])} chapters → {verse_count} verses")
            return flattened
        else:
            # Single verse
            return [convert_to_internal_format(data)]
    
    elif isinstance(data, list):
        if not data:
            return []
        
        # Check first item to determine format
        first_item = data[0]
        
        if isinstance(first_item, dict):
            if 'chapter' in first_item and 'verses' in first_item:
                # Chapter-based format as a list
                print("🔍 Detected: Chapter-based format as list")
                flattened = []
                verse_count = 0
                for chapter_data in data:
                    chapter_num = chapter_data.get('chapter', 0)
                    verses = chapter_data.get('verses', [])
                    
                    for verse in verses:
                        # Ensure chapter info is preserved
                        verse['chapter'] = chapter_num
                        flattened.append(convert_to_internal_format(verse))
                        verse_count += 1
                
                print(f"📚 Converted chapter-based format: {len(data)} chapters → {verse_count} verses")
                return flattened
            
            elif '_id' in first_item:
                # Flat verse list format
                print("🔍 Detected: Flat verse list format")
                return [convert_to_internal_format(verse) for verse in data]
            
            else:
                print("⚠️  Unknown format detected, treating as verse list")
                return [convert_to_internal_format(verse) for verse in data]
        else:
            print("⚠️  Non-dictionary items in list")
            return data
    
    print("⚠️  Unknown data format")
    return [data] if not isinstance(data, list) else data

def debug_verse_data(verse_data, verse_id):
    """Enhanced debug function to see what data is available - handles YOUR JSON format"""
    print(f"🔍 DEBUG: Available fields in {verse_id}:")
    
    # Check YOUR format fields first
    your_format_fields = {
        'sanskrit': 'Sanskrit text',
        'english': 'English text', 
        'hindi': 'Hindi text',
        'gujarati': 'Gujarati text'
    }
    
    for field, description in your_format_fields.items():
        value = verse_data.get(field, '')
        if value:
            preview = value[:50] + "..." if len(value) > 50 else value
            print(f"   ✅ {field} ({description}): {preview}")
        else:
            print(f"   ❌ {field} ({description}): Empty")
    
    # Also check standard fields
    standard_fields = {
        'slok': 'Sanskrit (Devanagari)',
        'transliteration': 'Sanskrit (Roman)',
        'en': 'English',
        'hi': 'Hindi',
        'gu': 'Gujarati'
    }
    
    has_standard = False
    for field, description in standard_fields.items():
        if field in verse_data:
            if not has_standard:
                print(f"   Standard format fields:")
                has_standard = True
            value = verse_data.get(field, '')
            status = "✅" if value else "❌"
            preview = value[:30] + "..." if value and len(value) > 30 else value
            print(f"      {status} {field}: {preview}")
    
    print("   Available keys:", list(verse_data.keys()))

def create_batch_filename(verse_id, language, voice, text_type):
    """Create standardized filename for batch processing"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"BG_{verse_id}_{language}_{text_type}_{voice}_{timestamp}.mp3"

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
        
        # Language code mapping
        lang_map = {
            'hi': 'hi',
            'gu': 'gu', 
            'sa': 'hi'  # Use Hindi for Sanskrit base
        }
        
        target_code = lang_map.get(target_language, target_language)
        
        # Force proper translation (not transliteration) by detecting source language first
        detected = translator_instance.detect(text)
        print(f"Detected source language: {detected.lang} (confidence: {detected.confidence})")
        
        result = translator_instance.translate(text, src=detected.lang, dest=target_code)
        translated = result.text
        
        print(f"Raw translation result: '{translated}'")
        
        # Check if we got a proper translation or just transliteration
        # Check for common transliterations that should be replaced with proper Hindi
        if target_language == 'hi':
            # First, check the original English for direct mapping (most reliable)
            lower_text = text.lower().strip()
            direct_translations = {
                'hello world': 'नमस्कार दुनिया',
                'hello': 'नमस्कार', 
                'world': 'दुनिया',
                'good morning': 'सुप्रभात',
                'good evening': 'शुभ संध्या', 
                'thank you': 'धन्यवाद',
                'how are you': 'आप कैसे हैं',
                'yes': 'हाँ',
                'no': 'नहीं',
                'please': 'कृपया'
            }
            
            if lower_text in direct_translations:
                old_translation = translated
                translated = direct_translations[lower_text]
                print(f"🎯 Used direct translation override: '{old_translation}' → '{translated}'")
            else:
                # Common transliterations to replace with proper Hindi
                transliteration_fixes = {
                    'हैलो वर्ल्ड': 'नमस्कार दुनिया',
                    'हैलो': 'नमस्कार',
                    'वर्ल्ड': 'दुनिया',
                    'गुड मॉर्निंग': 'सुप्रभात',
                    'गुड इवनिंग': 'शुभ संध्या',
                    'थैंक यू': 'धन्यवाद',
                    'हाउ आर यू': 'आप कैसे हैं'
                }
                
                # Check if we got a transliteration and fix it
                if translated in transliteration_fixes:
                    old_translation = translated
                    translated = transliteration_fixes[translated]
                    print(f"🔧 Fixed transliteration: '{old_translation}' → '{translated}'")
        
        print(f"Final translation: '{translated}'")
        return translated
        
    except Exception as e:
        print(f"Translation error: {e}")
        print(f"Falling back to original text: {text}")
        return text  # Return original text if translation fails

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

def synthesize_text_to_speech(text, voice="amy", speed=0.85, custom_filename=None, language="en"):
    """Synthesize text to speech using Narakeet API"""
    
    # Create unique filename with timestamp and voice
    if custom_filename:
        filename = custom_filename
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{voice}-{timestamp}.mp3"
    
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # For Sanskrit, we need to use Hindi voices since Narakeet doesn't support Sanskrit directly
    # For Hindi, we should NOT add any language parameter - just use the voice name
    api_voice = voice
    if language == 'sa':
        # Use the voice directly but log that we're using Hindi for Sanskrit
        print(f"⚠️  Note: Using Hindi voice '{voice}' for Sanskrit (Narakeet doesn't support Sanskrit directly)")
    elif language == 'hi':
        print(f"📢 Using Hindi voice '{voice}' for Hindi text")
    
    # Prepare the request - Narakeet uses voice names to determine language
    headers = {
        'Accept': 'application/octet-stream',
        'Content-Type': 'text/plain; charset=utf-8',
        'x-api-key': NARAKEET_API_KEY
    }
    
    params = {
        'voice': api_voice,
        'speed': speed
    }
    
    print(f"Sending to Narakeet: [voice: {api_voice}, speed: {speed}, text_language: {language}]")
    print(f"Text: {text}")
    print(f"Text encoding: {text.encode('utf-8')}")
    
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
            
            # Try to parse the error
            try:
                error_json = response.json()
                print("Error details:", error_json)
            except:
                print("Raw response:", response.content[:200])
            
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Request failed: {e}")
        return None
    except Exception as e:
        print(f"❌ ERROR: Unexpected error: {e}")
        return None
    
    # PART 2: API ENDPOINTS - Add this to the end of Part 1

@app.post("/batch-file")
async def batch_file_endpoint(request: Request, 
                            languages: str = Query(...), 
                            gender: str = Query("female"), 
                            max_verses: int = Query(20),
                            skip_missing: bool = Query(True),
                            use_fallbacks: bool = Query(True)):
    """
    Enhanced batch processing with better error handling and fallbacks
    
    New parameters:
    - skip_missing: Skip verses with missing text instead of failing
    - use_fallbacks: Use English/Hindi as fallback for missing Sanskrit
    """
    
    # Get JSON data from request
    try:
        raw_data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    # Detect format and convert to verse list
    try:
        verses_data = detect_format_and_process(raw_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing format: {str(e)}")
    
    # Ensure it's a list
    if not isinstance(verses_data, list):
        raise HTTPException(status_code=400, detail="Could not process data into verse list")
    
    # Get parameters from query string
    languages = languages.split(',')
    play = request.query_params.get('play', 'false').lower() == 'true'
    include_transliteration = request.query_params.get('transliteration', 'true').lower() == 'true'
    
    if len(verses_data) > max_verses:
        raise HTTPException(status_code=400, detail=f"Too many verses. Maximum allowed: {max_verses}. Found: {len(verses_data)}")
    
    print(f"\n{'='*90}")
    print(f"🔮 ENHANCED BATCH PROCESSING: {len(verses_data)} Verses")
    print(f"📋 Languages: {', '.join(languages)}")
    print(f"👤 Gender: {gender}")
    print(f"🔄 Skip missing: {skip_missing}")
    print(f"🛡️ Use fallbacks: {use_fallbacks}")
    print(f"{'='*90}")
    
    all_results = []
    verse_summaries = []
    chapters_processed = set()
    processing_stats = {
        'processed': 0,
        'skipped': 0,
        'failed': 0,
        'fallbacks_used': 0
    }
    
    try:
        for i, verse_data in enumerate(verses_data, 1):
            if not verse_data.get('_id'):
                print(f"⚠️  Skipping verse {i}: Missing _id")
                processing_stats['skipped'] += 1
                continue
            
            verse_id = verse_data['_id']
            chapter_num = verse_data.get('chapter', 0)
            chapters_processed.add(chapter_num)
            
            print(f"\n📖 Processing verse {i}/{len(verses_data)}: {verse_id} (Chapter {chapter_num})")
            
            # Debug: Show available data (only for first few verses to avoid spam)
            if i <= 3:
                debug_verse_data(verse_data, verse_id)
            print("=" * 50)
            
            verse_results = []
            verse_had_issues = False
            
            # Process each language for this verse
            for lang in languages:
                lang = lang.strip()
                
                print(f"\n🌍 {verse_id} - {lang.upper()}")
                print("-" * 30)
                
                # Extract text with enhanced fallback logic
                text = None
                text_type = None
                fallback_used = False
                
                if lang == 'sa':
                    print(f"⚠️  Note: Sanskrit processing with fallback support")
                    
                    # Try primary Sanskrit sources
                    if include_transliteration:
                        text = extract_text_from_gita_json(verse_data, 'sanskrit')
                        text_type = 'transliteration' if text else None
                    else:
                        text = extract_text_from_gita_json(verse_data, 'sanskrit_devanagari')
                        text_type = 'devanagari' if text else None
                    
                    # Apply fallback strategies if no Sanskrit found
                    if not text and use_fallbacks:
                        print(f"   🔄 Applying Sanskrit fallbacks...")
                        
                        # Fallback 1: Try other Sanskrit format
                        if not text and include_transliteration:
                            text = extract_text_from_gita_json(verse_data, 'sanskrit_devanagari')
                            if text:
                                text = prepare_sanskrit_text_for_tts(text, False)
                                text_type = 'devanagari_fallback'
                                fallback_used = True
                        
                        # Fallback 2: Use Hindi text for Sanskrit pronunciation
                        if not text:
                            text = extract_text_from_gita_json(verse_data, 'hindi')
                            if text:
                                text_type = 'hindi_as_sanskrit'
                                fallback_used = True
                                print(f"   🔄 Using Hindi text for Sanskrit pronunciation")
                        
                        # Fallback 3: Use English with note
                        if not text:
                            text = extract_text_from_gita_json(verse_data, 'english')
                            if text:
                                text = f"Sanskrit not available. English text: {text}"
                                text_type = 'english_fallback'
                                fallback_used = True
                                print(f"   🔄 Using English fallback with note")
                    
                    if not text:
                        if skip_missing:
                            print(f"   ⏭️ Skipping {verse_id} Sanskrit - no text available")
                            verse_had_issues = True
                            continue
                        else:
                            print(f"   ❌ No Sanskrit text found for {verse_id}")
                            continue
                    
                    voice = get_recommended_voice('sa', gender)
                    speed = 0.65
                    
                elif lang == 'hi':
                    text = extract_text_from_gita_json(verse_data, 'hindi')
                    text_type = 'direct' if 'hindi' in verse_data else 'commentary'
                    
                    # Fallback: translate from English
                    if not text and use_fallbacks:
                        english_text = extract_text_from_gita_json(verse_data, 'english')
                        if english_text and TRANSLATION_AVAILABLE:
                            try:
                                text = translate_text(english_text, 'hi')
                                text_type = 'translated_fallback'
                                fallback_used = True
                                print(f"   🔄 Using English→Hindi translation")
                            except Exception as e:
                                print(f"   ⚠️ Translation failed: {e}")
                    
                    if not text:
                        if skip_missing:
                            print(f"   ⏭️ Skipping {verse_id} Hindi - no text available")
                            verse_had_issues = True
                            continue
                        else:
                            print(f"   ❌ No Hindi text found for {verse_id}")
                            continue
                    
                    voice = get_recommended_voice('hi', gender)
                    speed = 0.85
                    
                elif lang == 'gu':
                    text = extract_text_from_gita_json(verse_data, 'gujarati')
                    text_type = 'direct'
                    
                    # Fallback: translate from English
                    if not text:
                        english_text = extract_text_from_gita_json(verse_data, 'english')
                        if english_text and TRANSLATION_AVAILABLE:
                            try:
                                text = translate_text(english_text, 'gu')
                                text_type = 'translated'
                                fallback_used = True
                            except Exception as e:
                                print(f"   ⚠️ Translation failed: {e}")
                    
                    if not text:
                        if skip_missing:
                            print(f"   ⏭️ Skipping {verse_id} Gujarati - no text available")
                            verse_had_issues = True
                            continue
                        else:
                            print(f"   ❌ No Gujarati text found for {verse_id}")
                            continue
                    
                    voice = get_recommended_voice('gu', gender)
                    speed = 0.85
                    
                elif lang == 'en':
                    text = extract_text_from_gita_json(verse_data, 'english')
                    text_type = 'direct' if 'english' in verse_data else 'commentary'
                    
                    if not text:
                        if skip_missing:
                            print(f"   ⏭️ Skipping {verse_id} English - no text available")
                            verse_had_issues = True
                            continue
                        else:
                            print(f"   ❌ No English text found for {verse_id}")
                            continue
                    
                    voice = get_recommended_voice('en', gender)
                    speed = 0.85
                
                else:
                    print(f"⚠️  Unsupported language: {lang}")
                    continue
                
                # Track fallback usage
                if fallback_used:
                    processing_stats['fallbacks_used'] += 1
                
                # Create filename
                filename = create_batch_filename(verse_id, lang, voice, text_type)
                
                print(f"📝 Text: {text[:80]}..." if len(text) > 80 else f"📝 Text: {text}")
                print(f"🎙️  Voice: {voice} | ⚡ Speed: {speed}")
                if fallback_used:
                    print(f"🔄 Fallback used: {text_type}")
                
                # Synthesize audio
                audio_file = synthesize_text_to_speech(text, voice, speed, filename, lang)
                
                if audio_file:
                    file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else 0
                    
                    result = {
                        "verse_id": verse_id,
                        "chapter": chapter_num,
                        "language": lang,
                        "text_type": text_type,
                        "voice": voice,
                        "speed": speed,
                        "text": text,
                        "audio_file": os.path.basename(audio_file),
                        "full_path": audio_file,
                        "file_size_bytes": file_size,
                        "fallback_used": fallback_used,
                        "success": True
                    }
                    
                    if play:
                        print(f"🎵 Playing {verse_id} {lang} audio...")
                        play_audio_with_ffplay(audio_file)
                    
                    status_icon = "🔄" if fallback_used else "✅"
                    print(f"{status_icon} {verse_id} {lang.upper()} completed")
                    
                else:
                    result = {
                        "verse_id": verse_id,
                        "chapter": chapter_num,
                        "language": lang,
                        "text_type": text_type,
                        "voice": voice,
                        "error": "Synthesis failed",
                        "fallback_used": fallback_used,
                        "success": False
                    }
                    print(f"❌ {verse_id} {lang.upper()} failed")
                    processing_stats['failed'] += 1
                
                verse_results.append(result)
            
            all_results.extend(verse_results)
            
            # Update processing stats
            if verse_results:
                processing_stats['processed'] += 1
            elif verse_had_issues:
                processing_stats['skipped'] += 1
            
            # Verse summary
            successful = [r for r in verse_results if r['success']]
            verse_summaries.append({
                "verse_id": verse_id,
                "chapter": chapter_num,
                "total_languages": len(verse_results),
                "successful": len(successful),
                "failed": len(verse_results) - len(successful),
                "fallbacks_used": sum(1 for r in verse_results if r.get('fallback_used', False))
            })
            
            print(f"📊 {verse_id} Summary: {len(successful)}/{len(verse_results)} successful")
        
        # Overall summary with enhanced stats
        total_successful = [r for r in all_results if r['success']]
        total_failed = [r for r in all_results if not r['success']]
        total_fallbacks = sum(1 for r in all_results if r.get('fallback_used', False))
        
        print(f"\n🎯 ENHANCED FINAL SUMMARY")
        print(f"📚 Verses processed: {processing_stats['processed']}")
        print(f"⏭️ Verses skipped: {processing_stats['skipped']}")
        print(f"📖 Chapters covered: {sorted(chapters_processed)}")
        print(f"✅ Total successful: {len(total_successful)}")
        print(f"❌ Total failed: {len(total_failed)}")
        print(f"🔄 Fallbacks used: {total_fallbacks}")
        print(f"📁 Audio files created: {len(total_successful)}")
        
        if total_successful:
            total_size = sum(r.get('file_size_bytes', 0) for r in total_successful)
            print(f"💾 Total size: {total_size} bytes ({total_size/1024/1024:.1f} MB)")
        
        return JSONResponse({
            "success": True,
            "message": f"Enhanced batch processing completed: {processing_stats['processed']} verses processed, {len(total_successful)} files created",
            "processing_stats": processing_stats,
            "verses_processed": processing_stats['processed'],
            "verses_skipped": processing_stats['skipped'],
            "chapters_covered": sorted(chapters_processed),
            "total_files_created": len(total_successful),
            "fallbacks_used": total_fallbacks,
            "verse_summaries": verse_summaries,
            "results": all_results,
            "summary": {
                "total_verses": len(verse_summaries),
                "total_chapters": len(chapters_processed),
                "total_audio_files": len(total_successful),
                "total_failed": len(total_failed),
                "total_fallbacks": total_fallbacks,
                "total_size_bytes": sum(r.get('file_size_bytes', 0) for r in total_successful),
                "total_size_mb": round(sum(r.get('file_size_bytes', 0) for r in total_successful) / 1024 / 1024, 1),
                "languages_processed": languages,
                "fallback_rate": f"{(total_fallbacks/len(all_results)*100):.1f}%" if all_results else "0%"
            }
        })
        
    except Exception as e:
        print(f"❌ Enhanced batch processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch processing error: {str(e)}")

@app.post("/batch-gita")
async def batch_synthesize_gita_verse(request: Request):
    """Batch synthesize Bhagavad Gita verse in multiple languages"""
    
    # Get JSON data from request
    try:
        verse_data = await request.json()
        # Convert to internal format if needed (single verse)
        if isinstance(verse_data, dict):
            verse_data = convert_to_internal_format(verse_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    # Get parameters from query string
    languages = request.query_params.get('languages', 'en,hi,sa').split(',')
    gender = request.query_params.get('gender', 'male')
    play = request.query_params.get('play', 'false').lower() == 'true'
    include_transliteration = request.query_params.get('transliteration', 'true').lower() == 'true'
    
    if not verse_data.get('_id'):
        raise HTTPException(status_code=400, detail="Verse ID (_id) is required")
    
    verse_id = verse_data['_id']
    results = []
    
    print(f"\n{'='*80}")
    print(f"🔮 BATCH PROCESSING: Bhagavad Gita Verse {verse_id}")
    print(f"📋 Languages: {', '.join(languages)}")
    print(f"👤 Gender: {gender}")
    print(f"{'='*80}")
    
    try:
        # Process each requested language
        for lang in languages:
            lang = lang.strip()
            
            print(f"\n🌍 Processing language: {lang.upper()}")
            print("-" * 40)
            
            # Extract appropriate text based on language
            if lang == 'sa':
                # Sanskrit - use transliteration for better pronunciation
                if include_transliteration:
                    text = extract_text_from_gita_json(verse_data, 'sanskrit')
                    text_type = 'transliteration'
                else:
                    text = extract_text_from_gita_json(verse_data, 'sanskrit_devanagari') 
                    text_type = 'devanagari'
                
                if not text:
                    print(f"⚠️  No Sanskrit text found for verse {verse_id}")
                    continue
                    
                voice = get_recommended_voice('sa', gender)
                speed = 0.7  # Slower for Sanskrit
                
            elif lang == 'hi':
                # Hindi - use existing Hindi text or commentary
                text = extract_text_from_gita_json(verse_data, 'hindi')
                text_type = 'direct' if 'hindi' in verse_data else 'commentary'
                
                if not text:
                    print(f"⚠️  No Hindi text found for verse {verse_id}")
                    continue
                    
                voice = get_recommended_voice('hi', gender)
                speed = 0.85
                
            elif lang == 'gu':
                # Gujarati - use direct text if available, otherwise translate from English
                text = extract_text_from_gita_json(verse_data, 'gujarati')
                
                if text:
                    text_type = 'direct'
                else:
                    # Translate from English
                    english_text = extract_text_from_gita_json(verse_data, 'english')
                    if not english_text:
                        print(f"⚠️  No English text found for verse {verse_id}")
                        continue
                    
                    if TRANSLATION_AVAILABLE:
                        text = translate_text(english_text, 'gu')
                        text_type = 'translated'
                    else:
                        print(f"⚠️  Translation not available, skipping Gujarati")
                        continue
                    
                voice = get_recommended_voice('gu', gender)
                speed = 0.85
                
            elif lang == 'en':
                # English - use direct text or commentary
                text = extract_text_from_gita_json(verse_data, 'english')
                text_type = 'direct' if 'english' in verse_data else 'commentary'
                
                if not text:
                    print(f"⚠️  No English text found for verse {verse_id}")
                    continue
                    
                voice = get_recommended_voice('en', gender)
                speed = 0.85
                
            else:
                print(f"⚠️  Unsupported language: {lang}")
                continue
            
            # Create custom filename
            filename = create_batch_filename(verse_id, lang, voice, text_type)
            
            print(f"📝 Text: {text[:100]}..." if len(text) > 100 else f"📝 Text: {text}")
            print(f"🎙️  Voice: {voice}")
            print(f"⚡ Speed: {speed}")
            print(f"📁 Filename: {filename}")
            
            # Synthesize audio
            audio_file = synthesize_text_to_speech(text, voice, speed, filename, lang)
            
            if audio_file:
                file_size = os.path.getsize(audio_file) if os.path.exists(audio_file) else 0
                
                result = {
                    "language": lang,
                    "text_type": text_type,
                    "voice": voice,
                    "speed": speed,
                    "text": text,
                    "audio_file": os.path.basename(audio_file),
                    "full_path": audio_file,
                    "file_size_bytes": file_size,
                    "success": True
                }
                
                # Play if requested
                if play:
                    print(f"🎵 Playing {lang} audio...")
                    play_audio_with_ffplay(audio_file)
                
                print(f"✅ {lang.upper()} completed successfully")
                
            else:
                result = {
                    "language": lang,
                    "text_type": text_type,
                    "voice": voice,
                    "error": "Synthesis failed",
                    "success": False
                }
                print(f"❌ {lang.upper()} failed")
            
            results.append(result)
            print("-" * 40)
        
        # Summary
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        print(f"\n📊 BATCH PROCESSING SUMMARY")
        print(f"✅ Successful: {len(successful)}")
        print(f"❌ Failed: {len(failed)}")
        print(f"📁 Total files created: {len(successful)}")
        
        if successful:
            total_size = sum(r.get('file_size_bytes', 0) for r in successful)
            print(f"💾 Total size: {total_size} bytes")
        
        return JSONResponse({
            "success": True,
            "verse_id": verse_id,
            "message": f"Batch processing completed: {len(successful)} successful, {len(failed)} failed",
            "results": results,
            "summary": {
                "total_requested": len(languages),
                "successful": len(successful),
                "failed": len(failed),
                "total_size_bytes": sum(r.get('file_size_bytes', 0) for r in successful)
            }
        })
        
    except Exception as e:
        print(f"❌ Batch processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch processing error: {str(e)}")

@app.post("/synthesize")
async def synthesize_text(request: Request):
    """Synthesize text to speech via POST request with translation support"""
    
    # Get text from request body
    text = (await request.body()).decode('utf-8')
    
    # Get parameters from query string
    voice = request.query_params.get('voice', None)
    speed = float(request.query_params.get('speed', '0.85'))
    play = request.query_params.get('play', 'true').lower() == 'true'
    language = request.query_params.get('language', 'en')  # en, hi, gu, sa (sanskrit)
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
        
        # Check if text is already in the target language script
        is_devanagari = any('\u0900' <= char <= '\u097F' for char in text)
        
        if language == 'hi':
            if is_devanagari:
                print("📝 Text appears to be in Devanagari (Hindi script) - using as-is")
                translated_text = text
            elif TRANSLATION_AVAILABLE:
                print("🔄 Starting translation to Hindi...")
                translated_text = translate_text(text, 'hi')
                if translated_text != text:
                    print(f"✅ Translation completed: '{text}' → '{translated_text}'")
                else:
                    print("⚠️  Translation failed, using original text")
            else:
                print(f"⚠️  Translation requested but googletrans not installed")
                
        elif language == 'gu':
            # Similar logic for Gujarati
            if TRANSLATION_AVAILABLE:
                print("🔄 Starting translation to Gujarati...")
                translated_text = translate_text(text, 'gu')
                if translated_text != text:
                    print(f"✅ Translation completed: '{text}' → '{translated_text}'")
                else:
                    print("⚠️  Translation failed, using original text")
            else:
                print(f"⚠️  Translation not available")
                
        elif language == 'sa':
            print("📜 Sanskrit mode")
            if is_devanagari:
                print("   Text appears to be in Devanagari script - using as-is")
                translated_text = text
            else:
                print("   Text in English - translating to Hindi for Sanskrit pronunciation")
                if TRANSLATION_AVAILABLE:
                    translated_text = translate_text(text, 'sa')  # This will translate to Hindi
                else:
                    print("   Translation not available, using original text")
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
        audio_file = synthesize_text_to_speech(translated_text, voice, speed, None, language)
        
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
                "translation_used": language not in ['en', 'sa'] and translated_text != text,
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

@app.get("/test-data/{verse_id}")
async def test_data_extraction(verse_id: str):
    """Test what data is available for a specific verse - for debugging"""
    
    # Create a sample verse in your format for testing
    test_verse = {
        "_id": verse_id,
        "chapter": 5,
        "verse": 18,
        "sanskrit": "विद्याविनयसम्पन्ने ब्राह्मणे गवि हस्तिनी | शुनिद्रोणपशुर्मारीचैव सर्व एव सुभद्रा: ||18||",
        "english": "The humble sages, by virtue of true knowledge, see with equal vision...",
        "hindi": "सच्चे ज्ञान और विनम्रता से युक्त साधु, ब्राह्मण, गाय, हाथी...",
        "gujarati": "સાચા જ્ઞાન અને વિનમ્રતા ધરાવતા સાધુ, બ્રાહ્મણ, ગાય..."
    }
    
    # Test extraction with current function
    results = {}
    for text_type in ['sanskrit', 'english', 'hindi', 'gujarati']:
        try:
            text = extract_text_from_gita_json(test_verse, text_type)
            results[text_type] = {
                "found": bool(text),
                "text": text[:100] + "..." if text and len(text) > 100 else text
            }
        except Exception as e:
            results[text_type] = {
                "found": False,
                "error": str(e)
            }
    
    return {
        "verse_id": verse_id,
        "test_verse_fields": list(test_verse.keys()),
        "extraction_results": results,
        "recommendation": "If all show 'found: false', you need to update extract_text_from_gita_json function"
    }

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
        "gujarati": {
            "male": ["ramesh", "pratik"],
            "female": ["asha", "manasi"]
        },
        "sanskrit_recommended": {
            "male": ["amitabh", "sanjay", "ranbir"],
            "female": ["madhuri", "kareena", "rashmi"]
        }
    }

@app.get("/")
async def root():
    """API documentation"""
    return {
        "message": "Narakeet TTS API with Bhagavad Gita Batch Processing - FIXED VERSION",
        "endpoints": {
            "POST /synthesize": "Synthesize single text to speech with translation",
            "POST /batch-gita": "Batch process single Bhagavad Gita verse in multiple languages",
            "POST /batch-file": "Process entire JSON file with multiple verses",
            "GET /test-data/{verse_id}": "Test data extraction for debugging",
            "GET /audio/{filename}": "Download audio file", 
            "GET /list": "List all audio files",
            "GET /voices": "Get available voices by language"
        },
        "languages": {
            "en": "English (Indian accent)",
            "hi": "Hindi (auto-translated or from commentary)",
            "gu": "Gujarati (auto-translated)",
            "sa": "Sanskrit (transliteration or Devanagari)"
        },
        "batch_file_example": {
            "description": "Process entire JSON file with multiple verses (supports YOUR format with sanskrit/english/hindi/gujarati fields)",
            "curl_your_format": "curl -X POST 'http://localhost:8081/batch-file?languages=sa,en,hi,gu&gender=male&max_verses=10' -H 'Content-Type: application/json' -d @bhagavad_gita_verses_updated.json",
            "parameters": {
                "languages": "Comma-separated list: en,hi,gu,sa (default: en,hi,sa)",
                "gender": "male or female (default: female)",
                "play": "true/false - play each audio file (default: false)",
                "max_verses": "Maximum verses to process (default: 20)",
                "skip_missing": "true/false - skip verses with missing text (default: true)",
                "use_fallbacks": "true/false - use fallbacks for missing text (default: true)"
            },
            "supported_formats": [
                "YOUR format: [{'_id': 'BG1.1', 'sanskrit': '...', 'english': '...', 'hindi': '...', 'gujarati': '...'}]",
                "Standard format: [{'_id': 'BG1.1', 'slok': '...', 'en': '...', 'hi': '...'}]",
                "Chapter-based: [{'chapter': 1, 'verses': [...]}]"
            ]
        },
        "example_curl": [
            "# Test with YOUR data format",
            "curl -X POST 'http://localhost:8081/batch-file?languages=sa,en,hi,gu&gender=male&max_verses=5' -H 'Content-Type: application/json' -d @bhagavad_gita_verses_updated.json",
            "",
            "# Test single text synthesis",
            "curl -X POST 'http://localhost:8081/synthesize?language=en&gender=male&play=true' -d 'Chapter 1, Verse 1. The King Dhritarashtra asked'",
            "",
            "# Gujarati translation",
            "curl -X POST 'http://localhost:8081/synthesize?language=gu&gender=female&play=true' -d 'Hello world, this is a test'",
            "",
            "# Sanskrit (Devanagari script)",
            "curl -X POST 'http://localhost:8081/synthesize?language=sa&gender=male&speed=0.7&play=true' -d 'धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः'",
            "",
            "# Single verse batch process",
            "curl -X POST 'http://localhost:8081/batch-gita?languages=en,hi,gu,sa&gender=male' -H 'Content-Type: application/json' -d '{\"_id\": \"BG2.47\", \"sanskrit\": \"कर्मण्येवाधिकारस्ते\", \"english\": \"You have a right to perform\", \"hindi\": \"तव कर्मों में अधिकार है\"}'"
        ],
        "fixed_features": [
            "✅ Now handles YOUR JSON format with 'sanskrit', 'english', 'hindi', 'gujarati' fields",
            "✅ Enhanced extraction function checks your format first",
            "✅ Better debugging with field detection",
            "✅ Fallback strategies for missing text",
            "✅ Skip missing verses option",
            "✅ Detailed processing statistics"
        ]
    }

if __name__ == "__main__":
    print("Starting Enhanced Narakeet TTS Server with Bhagavad Gita Batch Processing...")
    print("="*70)
    print("🔧 FIXED VERSION - Now supports YOUR JSON format!")
    print("API Documentation: http://localhost:8081/")
    print("\n🎯 Quick Test Commands:")
    print("\n1. Test your data format:")
    print("curl -X POST 'http://localhost:8081/batch-file?languages=sa,en,hi,gu&gender=male&max_verses=5' \\")
    print("     -H 'Content-Type: application/json' -d @bhagavad_gita_verses_updated.json")
    print("\n2. Debug specific verse:")
    print("curl http://localhost:8081/test-data/BG5.18")
    print("\n3. Test single Sanskrit synthesis:")
    print("curl -X POST 'http://localhost:8081/synthesize?language=sa&gender=male&play=true' \\")
    print("     -d 'विद्याविनयसम्पन्ने ब्राह्मणे गवि हस्तिनि'")
    print("\nTranslation Support:", "✓ Available" if TRANSLATION_AVAILABLE else "✗ Install googletrans")
    print("="*70)
    
    uvicorn.run(app, host="0.0.0.0", port=8081)
    