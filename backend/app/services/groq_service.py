from __future__ import annotations

import logging
from typing import TypeVar

from groq import Groq, GroqError
from pydantic import TypeAdapter

from ..config import settings

logger = logging.getLogger(__name__)
T = TypeVar("T")


class AIConfigurationError(RuntimeError):
    """Raised when a feature requires Groq but no API key is configured."""


class AIRequestError(RuntimeError):
    """Raised when Groq cannot complete a configured request."""


class GroqService:
    def __init__(self) -> None:
        self._client = (
            Groq(api_key=settings.groq_api_key, timeout=20.0, max_retries=1)
            if settings.groq_api_key
            else None
        )

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if self._client is None:
            raise AIConfigurationError(
                "AI features are unavailable because GROQ_API_KEY is not configured."
            )
        return self._request(system_prompt, user_prompt, structured=False)

    def complete_structured(
        self, system_prompt: str, user_prompt: str, response_type: type[T]
    ) -> T:
        if self._client is None:
            raise AIConfigurationError(
                "AI features are unavailable because GROQ_API_KEY is not configured."
            )
        content = self._request(system_prompt, user_prompt, structured=True)
        return TypeAdapter(response_type).validate_json(content)

    def _request(self, system_prompt: str, user_prompt: str, structured: bool) -> str:
        if self._client is None:
            raise AIConfigurationError(
                "AI features are unavailable because GROQ_API_KEY is not configured."
            )
        try:
            if structured:
                response = self._client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
            else:
                response = self._client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
        except GroqError as error:
            logger.error("Groq completion request failed (%s).", type(error).__name__)
            raise AIRequestError("The AI service could not complete the request.") from error
        if not response.choices:
            raise AIRequestError("The AI service returned no response choices.")
        content = response.choices[0].message.content
        if not content:
            raise AIRequestError("The AI service returned an empty response.")
        return content


groq_service = GroqService()
