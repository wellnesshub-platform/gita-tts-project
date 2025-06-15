# Bhagavad Gita Text-to-Speech (TTS) System

A multilingual Text-to-Speech system specifically designed for Bhagavad Gita content, supporting English (Indian accent), Hindi, and Sanskrit with authentic pronunciation using Narakeet API.

## Features

- 🎙️ **Indian accent voices** for authentic pronunciation
- 🌍 **Multi-language support**: English, Hindi, Sanskrit
- 🔄 **Auto-translation** from English to Hindi
- 📜 **Sanskrit support** with Devanagari script and transliteration
- 🎵 **Immediate playback** with ffplay
- 💾 **File output** with timestamped filenames
- 🚀 **REST API** for easy integration
- ⚡ **Smart voice selection** based on language and gender

## Prerequisites

### System Requirements
- Python 3.7+
- ffmpeg (for audio playback)

### Install ffmpeg
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

## Installation

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd gita-tts-project
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install fastapi uvicorn requests googletrans==4.0.0-rc1
```

### 4. Setup Narakeet API Key

**Option A: Environment Variable (Recommended)**
```bash
export NARAKEET_API_KEY="your_narakeet_api_key_here"
```

**Option B: .env File**
```bash
echo "NARAKEET_API_KEY=your_narakeet_api_key_here" > .env
```

**Option C: config.txt File**
```bash
echo "your_narakeet_api_key_here" > config.txt
```

### 5. Get Narakeet API Key
1. Sign up at [Narakeet.com](https://www.narakeet.com/)
2. Go to your account dashboard
3. Generate an API key
4. Ensure your account has API access (not just web interface credits)

## Usage

### Starting the Server

```bash
python simple_narakeet_tts.py
```

Server will start on `http://localhost:8081`

### API Documentation

Visit `http://localhost:8081/` for interactive API documentation.

### Basic Usage Examples

#### 1. English with Indian Accent
```bash
curl -X POST 'http://localhost:8081/synthesize?language=en&gender=male&play=true' \
     -d 'Chapter 1, Verse 1. The King Dhritarashtra asked: O Sanjaya! What happened on the sacred battlefield of Kurukshetra?'
```

#### 2. Auto-translate to Hindi
```bash
curl -X POST 'http://localhost:8081/synthesize?language=hi&gender=male&play=true' \
     -d 'Chapter 1, Verse 1. The King Dhritarashtra asked: O Sanjaya! What happened on the sacred battlefield of Kurukshetra?'
```

#### 3. Sanskrit (Devanagari Script)
```bash
curl -X POST 'http://localhost:8081/synthesize?language=sa&gender=male&speed=0.7&play=true' \
     -d 'धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः। मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय॥'
```

#### 4. Sanskrit from English (Auto-transliterate)
```bash
curl -X POST 'http://localhost:8081/synthesize?language=sa&gender=male&speed=0.7&play=true' \
     -d 'Chapter 1, Verse 1. Dhritarashtra asked Sanjaya about the battlefield of Kurukshetra'
```

## API Parameters

### POST /synthesize

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `language` | string | `en` | Language: `en` (English), `hi` (Hindi), `sa` (Sanskrit) |
| `gender` | string | `male` | Voice gender: `male`, `female` |
| `voice` | string | auto | Specific voice name (overrides auto-selection) |
| `speed` | float | `0.85` | Speech speed (0.5-2.0, auto-capped at 0.75 for Sanskrit) |
| `play` | boolean | `true` | Play audio immediately with ffplay |

### Available Voices

#### English (Indian Accent)
- **Male**: ravi, dev, rajesh, manish, himesh
- **Female**: anushka, deepika, neerja, pooja, vidya

#### Hindi
- **Male**: amitabh, sanjay, ranbir, varun, sunil
- **Female**: madhuri, kareena, rashmi, janhvi, shreya

#### Sanskrit (uses Hindi voices)
- **Recommended**: sanjay (perfect for Bhagavad Gita - Sanjaya is the narrator!)
- **Male**: amitabh, sanjay, ranbir
- **Female**: madhuri, kareena, rashmi

## File Output

Audio files are saved in the `audio_output/` directory with the format:
```
{voice}-{timestamp}.mp3
```

Example: `sanjay-20250615_143022.mp3`

## API Endpoints

- `POST /synthesize` - Main TTS endpoint
- `GET /audio/{filename}` - Download specific audio file
- `GET /list` - List all generated audio files
- `GET /voices` - Get available voices by language
- `GET /` - API documentation

## Project Structure

```
gita-tts-project/
├── simple_narakeet_tts.py    # Main application
├── .env                      # API key (create this)
├── config.txt               # Alternative API key storage
├── audio_output/            # Generated audio files
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Troubleshooting

### Common Issues

#### 1. 403 Forbidden Error
- **Cause**: Invalid API key or no API access
- **Solution**: 
  - Verify your API key is correct
  - Ensure your Narakeet account has API access (not just web credits)
  - Try regenerating your API key

#### 2. Translation Not Working
- **Cause**: `googletrans` not installed
- **Solution**: `pip install googletrans==4.0.0-rc1`

#### 3. Audio Not Playing
- **Cause**: ffmpeg not installed
- **Solution**: Install ffmpeg for your system

#### 4. Voice Not Available Error
- **Cause**: Using a voice name not in your account
- **Solution**: Use `GET /voices` to see available voices, or let the system auto-select

#### 5. Old/Cached Audio
- **Cause**: Using invalid voice names falls back to cached audio
- **Solution**: Use only voices from your account's voice list

### Testing Your Setup

```bash
# Test API key and basic functionality
curl -X POST 'http://localhost:8081/synthesize?language=en&voice=ravi&play=true' \
     -d 'Hello, this is a test'

# Test translation
curl -X POST 'http://localhost:8081/synthesize?language=hi&play=true' \
     -d 'Hello world'

# List generated files
curl http://localhost:8081/list

# Check available voices
curl http://localhost:8081/voices
```

## Development

### Running in Development Mode
```bash
# Enable auto-reload
uvicorn simple_narakeet_tts:app --reload --host 0.0.0.0 --port 8081
```

### Adding New Features
- Voice selection logic: `get_recommended_voice()`
- Translation: `translate_text()`
- Audio synthesis: `synthesize_text_to_speech()`

## License

[Your License Here]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Acknowledgments

- [Narakeet](https://www.narakeet.com/) for the Text-to-Speech API
- ffmpeg for audio processing
- The Bhagavad Gita for eternal wisdom

---

**Perfect for**: Audiobook creation, educational content, meditation apps, Sanskrit learning, and spiritual applications.