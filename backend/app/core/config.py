from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PENTAI_",
        extra="ignore",
    )

    app_name: str = "PentAI Pro API"
    environment: str = "development"
    allowed_network: str = "172.20.32.0/18"
    command_node_ip: str = "172.20.32.74"
    weapon_node_url: str = "https://172.20.32.68:5000"
    postgres_dsn: str = "postgresql+psycopg://pentai:pentai@postgres:5432/pentai"
    redis_url: str = "redis://redis:6379/0"
    ollama_url: str = "http://ollama:11434"
    gateway_audience: str = "pentai-tool-gateway"
    gateway_jwt_secret: str = "replace-this-before-use"
    gateway_ca_cert_path: str = "/workspace/certs/ca-cert.pem"
    gateway_client_cert_path: str = "/workspace/certs/command-client-cert.pem"
    gateway_client_key_path: str = "/workspace/certs/command-client-key.pem"
    artifacts_root: str = "/app/artifacts"
    operator_name: str = "lab-operator"
    auth_jwt_secret: str = "replace-this-before-use-with-32-plus-bytes-secret"
    auth_jwt_ttl_seconds: int = 60 * 60 * 12
    auth_cookie_name: str = "pentai_session"
    auth_cookie_secure: bool = False
    supabase_jwt_secret: str = "replace-with-supabase-project-jwt-secret"
    cors_allow_origins: str = "http://localhost:3000"
    knowledge_uploads_root: str = "/app/artifacts/knowledge"


@lru_cache
def get_settings() -> Settings:
    return Settings()
