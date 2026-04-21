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


@lru_cache
def get_settings() -> Settings:
    return Settings()
