from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    service_api_key: str = "dev-secret-key"
    openai_model: str = "gpt-4o"
    mock_tools: bool = True
    real_browser: bool = True
    browser_headless: bool = False  # False = you can watch the browser window

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()