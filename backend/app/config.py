from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ragdb"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/ragdb"
    DATABASE_ADMIN_URL: str = ""
    DATABASE_ADMIN_SYNC_URL: str = ""
    POSTGRES_PASSWORD: str = "postgres"
    REDIS_URL: str = "redis://localhost:6379/0"

    AI_PROVIDER: str = "mock"
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHAT_MODEL: str = "gpt-4o-mini"
    EMBEDDING_DIMENSIONS: int = 768

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_CHAT_MODEL: str = "llama3.2:1b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    CHAT_PROVIDER_CHAIN: str = "openai,ollama,mock"
    EMBEDDING_PROVIDER: str = ""  # empty = follow AI_PROVIDER; never falls back
    PROVIDER_TIMEOUT_SECONDS: int = 30

    # In-process models (EMBEDDING_PROVIDER=local, RERANKER=local)
    LOCAL_EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    LOCAL_RERANK_MODEL: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    LOCAL_MODEL_CACHE_DIR: str = ""
    RERANKER: str = "local"  # local | none
    # Fused candidates sent to the reranker. Evals: 8-12 gave the best hit@1 and
    # ~220-310 ms on CPU; larger pools cost latency without improving quality.
    RERANK_POOL: int = 10

    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "rag-documents"
    S3_REGION: str = "us-east-1"

    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 30
    ENCRYPTION_KEY: str = "change-this-32-byte-key-for-fernet"

    APP_ENV: str = "development"
    APP_BASE_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:5173,http://localhost:8080"
    SUPERADMIN_EMAIL: str = "admin@yoursaas.com"
    SUPERADMIN_PASSWORD: str = "change-this"

    NOTION_CLIENT_ID: str = ""
    NOTION_CLIENT_SECRET: str = ""

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_PRO: str = ""
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/settings?billing=success"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/settings?billing=cancel"

    SENTRY_DSN: str = ""
    ENABLE_QUERY_REWRITE: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def chat_provider_chain_list(self) -> list[str]:
        if self.CHAT_PROVIDER_CHAIN.strip():
            return [p.strip().lower() for p in self.CHAT_PROVIDER_CHAIN.split(",") if p.strip()]
        provider = self.AI_PROVIDER.lower()
        if provider == "mock":
            return ["mock"]
        if provider == "ollama":
            return ["ollama", "mock"]
        if provider == "openai":
            return ["openai", "ollama", "mock"]
        return ["mock"]

    @property
    def embedding_provider_name(self) -> str:
        if self.EMBEDDING_PROVIDER.strip():
            return self.EMBEDDING_PROVIDER.strip().lower()
        return self.AI_PROVIDER.lower()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
