"""Runtime configuration, read once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _csv(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    table_name: str = os.environ.get("TABLE_NAME", "climate-hubris")
    # Set to http://dynamodb:8000 by docker-compose; unset in AWS.
    dynamodb_endpoint: str | None = os.environ.get("DYNAMODB_ENDPOINT") or None
    aws_region: str = os.environ.get("AWS_REGION", "us-east-1")

    cors_origins: list[str] = field(
        default_factory=lambda: _csv("CORS_ORIGINS", "http://localhost:3000")
    )

    # Agent. "bedrock" needs no API key (IAM); "openai" reads its key from SSM.
    llm_provider: str = os.environ.get("LLM_PROVIDER") or "bedrock"
    bedrock_model: str = (
        os.environ.get("BEDROCK_MODEL") or "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    openai_key_param: str = os.environ.get("OPENAI_KEY_PARAM", "/climate-hubris/openai-api-key")
    agent_max_documents: int = int(os.environ.get("AGENT_MAX_DOCUMENTS", "40"))
    # ReliefWeb's API only answers pre-approved app names; the source is skipped when unset.
    reliefweb_appname: str | None = os.environ.get("RELIEFWEB_APPNAME") or None

    user_agent: str = os.environ.get(
        "HTTP_USER_AGENT", "climate-hubris/1.0 (+https://climate.akash.ucsciba.org)"
    )


settings = Settings()
