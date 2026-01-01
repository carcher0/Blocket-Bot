"""
OpenAI LLM client with strict JSON validation.
"""
import json
import logging
from typing import Any, Optional, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from ..config import get_config


logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    OpenAI LLM client with strict JSON mode and Pydantic validation.
    All responses are parsed and validated against schemas.
    """

    def __init__(self, model: Optional[str] = None):
        config = get_config()
        self.api_key = config.openai.api_key
        self.model = model or config.openai.model
        self.max_tokens = config.openai.max_tokens
        self.temperature = config.openai.temperature

        if not self.api_key:
            logger.warning("No OpenAI API key configured")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)

    def is_available(self) -> bool:
        """Check if the LLM client is properly configured."""
        return self.client is not None

    def _call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[dict] = None,
    ) -> str:
        """Make an API call and return the response text."""
        if not self.client:
            raise RuntimeError("LLM client not configured")

        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def call_with_schema(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        """
        Make an API call and parse response into a Pydantic model.

        Args:
            system_prompt: System context
            user_prompt: User query
            response_model: Pydantic model class to parse into

        Returns:
            Validated Pydantic model instance

        Raises:
            ValidationError: If response doesn't match schema
            RuntimeError: If LLM not configured
        """
        # Force JSON mode
        response_text = self._call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format={"type": "json_object"},
        )

        # Parse JSON
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from LLM: {e}")
            raise

        # Validate with Pydantic
        return response_model.model_validate(data)

    def call_raw(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Make a raw API call without JSON parsing."""
        return self._call(system_prompt, user_prompt)

    def extract_json(
        self,
        text: str,
        schema: Type[T],
    ) -> Optional[T]:
        """
        Use LLM to extract structured data from text.

        Args:
            text: Text to extract from
            schema: Pydantic model defining what to extract

        Returns:
            Validated model or None if extraction fails
        """
        schema_json = schema.model_json_schema()
        
        system_prompt = """You are a data extraction assistant. 
Extract structured data from the given text according to the provided schema.
Return ONLY valid JSON matching the schema. No explanations."""

        user_prompt = f"""Schema:
{json.dumps(schema_json, indent=2)}

Text to extract from:
{text}

Return JSON:"""

        try:
            return self.call_with_schema(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=schema,
            )
        except (ValidationError, json.JSONDecodeError) as e:
            logger.warning(f"Extraction failed: {e}")
            return None
