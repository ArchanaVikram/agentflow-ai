from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Language model (any OpenAI-compatible provider: Gemini, Groq, OpenRouter, ...)
    llm_api_key: str = ""
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_model: str = "gemini-3.1-flash-lite"

    service_api_key: str = "dev-secret-key"
    mock_tools: bool = True
    real_browser: bool = True
    browser_headless: bool = False  # False = you can watch the browser window

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()