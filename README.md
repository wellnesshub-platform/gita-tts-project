# Bhagavad Gita TTS Project

Multi-language Text-to-Speech API for Bhagavad Gita verses.

## Quick Start

1. **Setup:**
   ```bash
   ./scripts/setup.sh
   ```

2. **Configure GCP:**
   - Place your service account key as `service-account-key.json`
   - Or set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

3. **Run:**
   ```bash
   source venv/bin/activate
   python src/main.py
   ```

4. **Test:**
   ```bash
   python scripts/test.py
   ```

## API Endpoints

- `GET /` - Health check
- `POST /synthesize/verse` - Generate TTS audio
- `GET /languages` - Supported languages

## Configuration

Project: gita-tts
Region: us-central1
Bucket: gita-tts-gita-tts-audio

## Next Steps

1. Get GCP service account key
2. Run the setup script
3. Test the API
4. Deploy to Cloud Run (optional)

# gita-tts-project
