"""Anthropic API client wrapper with retry logic and structured output."""

import json
import os
import random
import time
from pathlib import Path
from typing import Any

from anthropic import Anthropic, RateLimitError
from anthropic.types import Message
from dotenv import load_dotenv
from pydantic import BaseModel
from rich.console import Console

console = Console()

# Load .env from parent directory (repo root) if it exists
# This allows running from ./benchmark/ while keeping .env in ./
_env_paths = [
    Path.cwd() / ".env",  # Current directory
    Path.cwd().parent / ".env",  # Parent directory
]
for _env_path in _env_paths:
    if _env_path.exists():
        load_dotenv(_env_path)
        break


class AnthropicGraderClient:
    """Wrapper for Anthropic API with retry logic and structured output.

    Features:
    - Prompt caching: System prompts are cached for 90% cost savings (5 min TTL)
    - Rate limit handling: Graceful 429 handling with exponential backoff + jitter
    - Structured outputs: Uses beta API for guaranteed JSON schema conformance
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        max_retries: int = 3,
        initial_backoff: float = 1.0,
    ):
        """Initialize the Anthropic client.

        Args:
            model: Model to use for grading
            max_retries: Maximum number of retries on rate limit
            initial_backoff: Initial backoff time in seconds (doubles on each retry)
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Please set it to your Anthropic API key."
            )

        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff

    def call_with_structured_output(
        self,
        system_prompt: str,
        user_message: str,
        output_schema: type[BaseModel],
        max_tokens: int = 4096,
    ) -> tuple[BaseModel | None, int, float]:
        """Call the API with structured output using the new beta API.

        Uses prompt caching for the system prompt and graceful rate limit handling.

        Args:
            system_prompt: System prompt defining the role
            user_message: User message with the grading task
            output_schema: Pydantic model class for the output schema
            max_tokens: Maximum tokens for the response

        Returns:
            Tuple of (parsed output or None if error, tokens used, time taken)
        """
        backoff = self.initial_backoff
        last_error = None

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                response: Message = self.client.beta.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    # Use prompt caching for system prompt (saves cost on repeated calls)
                    system=[
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": user_message}],
                    betas=[
                        "structured-outputs-2025-11-13",
                        "prompt-caching-2024-07-31",
                    ],
                    output_format={
                        "type": "json_schema",
                        "schema": output_schema.model_json_schema(),
                    },
                )

                elapsed = time.time() - start_time
                tokens = response.usage.input_tokens + response.usage.output_tokens

                # Log cache performance if available
                if hasattr(response.usage, "cache_creation_input_tokens"):
                    cache_write = response.usage.cache_creation_input_tokens or 0
                    cache_read = response.usage.cache_read_input_tokens or 0
                    if cache_write > 0:
                        console.print(
                            f"[dim]Cache write: {cache_write} tokens[/dim]",
                            style="dim",
                        )
                    if cache_read > 0:
                        console.print(
                            f"[dim]Cache hit: {cache_read} tokens (90% savings)[/dim]",
                            style="dim",
                        )

                # Parse the response text as JSON matching our schema
                result_data = json.loads(response.content[0].text)
                result = output_schema.model_validate(result_data)
                return result, tokens, elapsed

            except RateLimitError as e:
                # Handle rate limit with info from headers
                last_error = e
                if attempt < self.max_retries - 1:
                    # Add jitter to prevent thundering herd
                    jitter = random.uniform(0, 0.1 * backoff)
                    sleep_time = backoff + jitter

                    # Try to extract retry-after from headers if available
                    retry_after = None
                    if hasattr(e, "response") and hasattr(e.response, "headers"):
                        retry_after_header = e.response.headers.get("retry-after")
                        if retry_after_header:
                            try:
                                retry_after = float(retry_after_header)
                                sleep_time = max(sleep_time, retry_after)
                            except ValueError:
                                # If the retry-after header is malformed, ignore it and
                                # fall back to the existing exponential backoff value.
                                pass

                    console.print(
                        f"[yellow]Rate limit hit (429), retrying in {sleep_time:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})[/yellow]"
                    )
                    time.sleep(sleep_time)
                    backoff *= 2  # Exponential backoff
                    continue
                else:
                    console.print("[red]Rate limit exceeded after max retries[/red]")
                    return None, 0, 0.0

            except Exception as e:
                # Non-rate-limit error, don't retry
                last_error = e
                console.print(f"[red]API error: {e}[/red]")
                return None, 0, 0.0

        # Max retries exceeded
        console.print(f"[red]Max retries exceeded. Last error: {last_error}[/red]")
        return None, 0, 0.0

    def grade_difficulty(
        self, system_prompt: str, difficulty_prompt: str
    ) -> tuple[Any, int, float]:
        """Grade difficulty using structured output.

        Args:
            system_prompt: System prompt
            difficulty_prompt: Rendered difficulty assessment prompt

        Returns:
            Tuple of (DifficultyGrade or None, tokens used, time taken)
        """
        from scripts.postproduction.grader.models import DifficultyGrade

        return self.call_with_structured_output(
            system_prompt=system_prompt,
            user_message=difficulty_prompt,
            output_schema=DifficultyGrade,
        )
