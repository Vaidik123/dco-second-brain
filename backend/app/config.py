from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    voyage_api_key: str
    database_url: str
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    twitter_bearer_token: str = ""
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
