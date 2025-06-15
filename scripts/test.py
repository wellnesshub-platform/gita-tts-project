#!/usr/bin/env python3

import requests
import json

# Test verse
test_verse = {
    "_id": "BG1.1",
    "chapter": 1,
    "verse": 1,
    "purohit": {
        "et": "The King Dhritarashtra asked: O Sanjaya! What happened on the sacred battlefield of Kurukshetra?"
    }
}

def test_api(base_url="http://localhost:8080"):
    print(f"🧪 Testing API at {base_url}")
    
    try:
        # Health check
        response = requests.get(f"{base_url}/health")
        print(f"Health: {response.json()}")
        
        # Test synthesis
        response = requests.post(
            f"{base_url}/synthesize/verse",
            json=test_verse,
            params={"author": "purohit", "language": "en-IN"}
        )
        
        if response.status_code == 200:
            with open("test_audio.mp3", "wb") as f:
                f.write(response.content)
            print("✅ Audio generated: test_audio.mp3")
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_api()
