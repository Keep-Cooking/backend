import os
from dotenv import load_dotenv
from pydantic_ai.providers.google import GoogleProvider

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
THEMEALDB_API_KEY = os.getenv("THEMEALDB_API_KEY", "1")
THEMEALDB_PREMIUM = THEMEALDB_API_KEY != "1"
THEMEALDB_VERSION = "v2" if THEMEALDB_PREMIUM else "v1"
THEMEALDB = f"https://www.themealdb.com/api/json/{THEMEALDB_VERSION}/{THEMEALDB_API_KEY}"

# make sure the google api key is defined
if not GOOGLE_API_KEY:
    raise EnvironmentError("No GOOGLE_API_KEY defined.")

# Provider for Gemini API
provider = GoogleProvider(api_key=GOOGLE_API_KEY)