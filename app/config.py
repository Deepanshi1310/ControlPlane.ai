from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    GEMINI_API_KEY: str

    GEMINI_MODEL: str = "gemini-2.5-flash-lite"

    DATABASE_URL: str = ""

    class Config:
        env_file = ".env"


settings = Settings()