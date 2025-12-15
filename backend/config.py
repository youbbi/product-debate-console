import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv()

class Config:
    # Azure OpenAI
    AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_DEPLOYMENT_GPT4 = os.getenv("AZURE_DEPLOYMENT_GPT4", "gpt-4-turbo")

    # Anthropic Claude
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # Google Gemini
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

    # Council config
    COUNCIL_CHAIRMAN_PROVIDER = os.getenv("COUNCIL_CHAIRMAN_PROVIDER", "anthropic")
    COUNCIL_MIN_PROVIDERS = int(os.getenv("COUNCIL_MIN_PROVIDERS", "2"))

    # App
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))

    # Debate config
    MAX_DEBATE_ROUNDS = 2
    ENABLE_PARALLEL = True  # Run all execs simultaneously
    STREAMING_ENABLED = True

    @classmethod
    def get_enabled_providers(cls) -> list:
        """Return list of providers with valid credentials"""
        providers = []
        if cls.AZURE_ENDPOINT and cls.AZURE_KEY:
            providers.append("azure")
        if cls.ANTHROPIC_API_KEY:
            providers.append("anthropic")
        if cls.GOOGLE_API_KEY:
            providers.append("google")
        return providers
    
    @classmethod
    def get_llm(cls, temperature: float = 0.7):
        """Factory for Azure OpenAI LLM"""
        return AzureChatOpenAI(
            azure_endpoint=cls.AZURE_ENDPOINT,
            api_key=cls.AZURE_KEY,
            deployment_name=cls.AZURE_DEPLOYMENT_GPT4,
            api_version="2024-12-01-preview",
            temperature=1,
            max_tokens=2500
        )

try:
    assert Config.AZURE_ENDPOINT, "AZURE_OPENAI_ENDPOINT not set"
    assert Config.AZURE_KEY, "AZURE_OPENAI_API_KEY not set"
    print("✓ Azure OpenAI credentials loaded")
except AssertionError as e:
    print(f"❌ Config error: {e}")

# Log additional providers
if Config.ANTHROPIC_API_KEY:
    print("✓ Anthropic Claude credentials loaded")
if Config.GOOGLE_API_KEY:
    print("✓ Google Gemini credentials loaded")

enabled = Config.get_enabled_providers()
print(f"✓ Council providers available: {', '.join(enabled) if enabled else 'None'}")
