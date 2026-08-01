import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    GOOGLE_MAPS_SERVER_KEY: str = os.getenv("GOOGLE_MAPS_SERVER_KEY", "")
    GOOGLE_MAPS_CLIENT_KEY: str = os.getenv("GOOGLE_MAPS_CLIENT_KEY", "")
    BACKEND_API_KEY: str = os.getenv("BACKEND_API_KEY", "")
    PORT: int = int(os.getenv("PORT", 8000))
    
    def validate(self):
        if not self.GOOGLE_MAPS_SERVER_KEY or not self.GOOGLE_MAPS_CLIENT_KEY:
            raise ValueError(
                "CRITICAL: Both GOOGLE_MAPS_SERVER_KEY and GOOGLE_MAPS_CLIENT_KEY must be set in backend/.env."
            )
        if not self.BACKEND_API_KEY:
            raise ValueError(
                "CRITICAL: BACKEND_API_KEY must be set in backend/.env to secure the proxy gateway."
            )

settings = Settings()
settings.validate()
