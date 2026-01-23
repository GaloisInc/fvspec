"""Anthropic API client wrapper with retry logic and structured output."""

import os
import time
from pathlib import Path
from typing import Any

from anthropic import Anthropic
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
    """Wrapper for Anthropic API with retry logic and structured output."""

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
        tool_name: str,
        tool_description: str,
        output_schema: type[BaseModel],
        max_tokens: int = 4096,
    ) -> tuple[BaseModel | None, int, float]:
        """Call the API with structured output via tool use.

        Args:
            system_prompt: System prompt defining the role
            user_message: User message with the grading task
            tool_name: Name of the tool to use for structured output
            tool_description: Description of the tool
            output_schema: Pydantic model class for the output schema
            max_tokens: Maximum tokens for the response

        Returns:
            Tuple of (parsed output or None if error, tokens used, time taken)
        """
        # Create tool definition from Pydantic schema
        tools = [
            {
                "name": tool_name,
                "description": tool_description,
                "input_schema": output_schema.model_json_schema(),
            }
        ]

        backoff = self.initial_backoff
        last_error = None

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                response: Message = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                    tools=tools,
                    tool_choice={"type": "tool", "name": tool_name},
                )

                elapsed = time.time() - start_time
                tokens = response.usage.input_tokens + response.usage.output_tokens

                # Extract tool use result
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        # Parse the tool input as our output schema
                        result = output_schema.model_validate(content_block.input)
                        return result, tokens, elapsed

                # No tool use found in response
                console.print(
                    "[yellow]Warning: No tool use found in API response[/yellow]"
                )
                return None, tokens, elapsed

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if it's a rate limit error
                if "rate" in error_str or "429" in error_str:
                    if attempt < self.max_retries - 1:
                        console.print(
                            f"[yellow]Rate limit hit, retrying in {backoff:.1f}s "
                            f"(attempt {attempt + 1}/{self.max_retries})[/yellow]"
                        )
                        time.sleep(backoff)
                        backoff *= 2  # Exponential backoff
                        continue
                    else:
                        console.print(
                            "[red]Rate limit exceeded after max retries[/red]"
                        )
                        return None, 0, 0.0
                else:
                    # Non-rate-limit error, don't retry
                    console.print(f"[red]API error: {e}[/red]")
                    return None, 0, 0.0

        # Max retries exceeded
        console.print(f"[red]Max retries exceeded. Last error: {last_error}[/red]")
        return None, 0, 0.0

    def grade_quality(
        self, system_prompt: str, quality_prompt: str
    ) -> tuple[Any, int, float]:
        """Grade quality using structured output.

        Args:
            system_prompt: System prompt
            quality_prompt: Rendered quality assessment prompt

        Returns:
            Tuple of (QualityGrade or None, tokens used, time taken)
        """
        from .models import QualityGrade

        return self.call_with_structured_output(
            system_prompt=system_prompt,
            user_message=quality_prompt,
            tool_name="submit_quality_grade",
            tool_description="Submit the quality assessment for this formalization",
            output_schema=QualityGrade,
        )

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
        from .models import DifficultyGrade

        return self.call_with_structured_output(
            system_prompt=system_prompt,
            user_message=difficulty_prompt,
            tool_name="submit_difficulty_grade",
            tool_description="Submit the difficulty estimation for this formalization task",
            output_schema=DifficultyGrade,
        )
