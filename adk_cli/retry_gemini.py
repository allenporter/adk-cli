import asyncio
import logging
import random
import re
from typing import AsyncGenerator

from google.genai import types
from google.adk.models.google_llm import Gemini, _ResourceExhaustedError
from google.genai.errors import ClientError
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

logger = logging.getLogger(__name__)


class AdkRetryGemini(Gemini):
    """Custom Gemini model wrapper that natively intercepts 429 Resource Exhausted errors and parses RetryInfo delay details, inspired by gemini-cli."""

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        max_attempts = 10
        base_delay = 5.0
        max_delay = 60.0

        for attempt in range(1, max_attempts + 1):
            try:
                # Keep track of whether we've yielded anything. If we have, we can't retry safely.
                item_yielded = False
                logger.debug("--- [LLM Request Starting] ---")
                async for chunk in super().generate_content_async(llm_request, stream):
                    item_yielded = True
                    yield chunk
                logger.debug("--- [LLM Request Complete] ---")
                return  # Success
            except (_ResourceExhaustedError, ClientError) as e:
                # If we've already started streaming, we can't retry the entire stream cleanly.
                if item_yielded:
                    raise e

                code = getattr(e, "code", getattr(e, "status_code", 500))
                if code != 429:
                    raise e

                if attempt == max_attempts:
                    logger.warning(
                        "Max rate limit retries (%d) reached. Aborting.", max_attempts
                    )
                    raise e

                delay_s = base_delay

                # Check programmatic details for google.rpc.RetryInfo first
                details = getattr(e, "details", {})
                if isinstance(details, dict):
                    # Google APIs often wrap details inside an "error" envelope
                    err_payload = details.get("error", details)
                    for detail in err_payload.get("details", []):
                        if (
                            detail.get("@type")
                            == "type.googleapis.com/google.rpc.RetryInfo"
                        ):
                            delay_str = str(detail.get("retryDelay", ""))
                            if delay_str.endswith("s"):
                                try:
                                    # Fallback to programmatic delay
                                    delay_s = float(delay_str[:-1])
                                    logger.debug(
                                        "Parsed RetryInfo programmatic delay: %ss",
                                        delay_s,
                                    )
                                except ValueError:
                                    pass

                # Fallback: try to parse "Please retry in X.Xs" or similar
                if delay_s == base_delay:
                    error_body = str(e)
                    match = re.search(r"Please retry in ([0-9.]+)(ms|s)", error_body)
                    if match:
                        amount = float(match.group(1))
                        unit = match.group(2)
                        delay_s = amount if unit == "s" else amount / 1000.0
                        logger.debug("Parsed regex programmatic delay: %ss", delay_s)

                # Cap the delay to max_delay
                delay_s = min(delay_s, max_delay)

                # Add jitter
                jitter = delay_s * 0.3 * (random.random() * 2 - 1)
                total_delay = max(0, delay_s + jitter)

                logger.warning(
                    "[Rate Limit] Encountered 429 Too Many Requests. "
                    "Retrying in %.2fs (attempt %d/%d).",
                    total_delay,
                    attempt,
                    max_attempts,
                )

                # Notify the user via the TUI that a rate limit has occurred
                yield LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                text=f"```thought\n[Rate Limit] Waiting {total_delay:.1f}s before resuming...\n```\n"
                            )
                        ],
                    )
                )

                await asyncio.sleep(total_delay)
                base_delay = min(max_delay, base_delay * 2)
