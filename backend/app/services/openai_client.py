from openai import OpenAI

from app.core.config import settings


def get_openai_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured."
        )

    return OpenAI(
        api_key=settings.openai_api_key,
    )
