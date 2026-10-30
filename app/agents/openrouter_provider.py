import asyncio
import json
import logging
import re
from typing import Any

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

from app.agents.base import BaseLLMProvider
from app.core.config import settings
from app.schemas.planning import ArchitecturePlanContent, TaskPlanContent
from app.schemas.specification import SRSContent

logger = logging.getLogger(__name__)


def normalize_api_key(raw_key: str | None) -> str:
    """Normalize a user-supplied OpenRouter key.

    Users frequently paste keys with a leading ``Bearer`` prefix, surrounding
    quotes, or trailing whitespace. OpenRouter rejects those values with a
    misleading "Missing Authentication header" error, so normalize them here.
    """
    key = (raw_key or "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in {'"', "'"}:
        key = key[1:-1].strip()
    return key


class OpenRouterProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = normalize_api_key(api_key or settings.OPENROUTER_API_KEY)
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenRouter API key is not configured. Please add a valid key in the app settings or .env.",
            )
        if not self.api_key.startswith("sk-or-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "The supplied OpenRouter API key is not valid. OpenRouter keys start with "
                    "'sk-or-v1-'. Make sure you saved an OpenRouter key (not a Gemini key) in the "
                    "dashboard, then retry."
                ),
            )
        self.model = model or settings.OPENROUTER_MODEL

    async def _call(self, system_instruction: str, prompt: str, schema: type[BaseModel]):
        candidates = []
        seen: set[str] = set()
        for model in [self.model, self.model.removesuffix(":free") if self.model.endswith(":free") else None, "meta-llama/llama-3.1-8b-instruct:free", "openai/gpt-oss-20b"]:
            if not model or model in seen:
                continue
            seen.add(model)
            candidates.append(model)

        last_error = None
        for idx, model in enumerate(candidates):
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "AgentForge AI",
            }

            try:
                async with httpx.AsyncClient(timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS) as client:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
            except httpx.HTTPError as exc:
                logger.error("OpenRouter request failed with %s", type(exc).__name__)
                last_error = exc
                continue

            if response.status_code == 404:
                try:
                    error_message = response.json().get("error", {}).get("message", "")
                except ValueError:
                    error_message = ""
                if "unavailable for free" in error_message and idx < len(candidates) - 1:
                    logger.warning(
                        "OpenRouter free model %s is unavailable; retrying with %s",
                        model,
                        candidates[idx + 1],
                    )
                    continue
                logger.error(
                    "OpenRouter request failed with status %s: %s",
                    response.status_code,
                    response.text[:500],
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="The OpenRouter provider rejected the request. Please retry.",
                )

            if response.status_code in {401, 403}:
                logger.error(
                    "OpenRouter authentication failed with status %s: %s",
                    response.status_code,
                    response.text[:500],
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=(
                        "OpenRouter rejected the API key. Verify the key saved in the dashboard is a "
                        "valid OpenRouter key (starts with 'sk-or-v1-') and has available credits."
                    ),
                )

            if response.status_code >= 400:
                logger.error(
                    "OpenRouter request failed with status %s: %s",
                    response.status_code,
                    response.text[:500],
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="The OpenRouter provider rejected the request. Please retry.",
                )

            try:
                data = response.json()
            except ValueError as exc:
                logger.error("OpenRouter returned invalid JSON: %s", response.text[:500])
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="The OpenRouter provider returned an invalid response. Please retry.",
                ) from exc

            choices = data.get("choices") or []
            if not choices:
                logger.error("OpenRouter returned no choices: %s", data)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="The OpenRouter provider returned no response. Please retry.",
                )

            message = choices[0].get("message") or {}
            text = message.get("content") or ""
            if isinstance(text, list):
                text = "".join(
                    part.get("text", "") if isinstance(part, dict) else "" for part in text
                )

            if not text:
                logger.error("OpenRouter returned an empty response")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="The OpenRouter provider returned an empty response. Please retry.",
                )

            self.model = model
            return text

        if last_error is not None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The OpenRouter provider failed to connect. Please retry.",
            ) from last_error

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The OpenRouter provider rejected the request. Please retry.",
        )

    @staticmethod
    def _json_candidates(text: str) -> list[str]:
        """Build progressively more aggressive JSON extraction candidates."""
        candidates: list[str] = [text.strip()]

        for match in re.finditer(
            r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE
        ):
            candidates.append(match.group(1).strip())

        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            candidates.append(text[brace_start : brace_end + 1].strip())

        bracket_start = text.find("[")
        bracket_end = text.rfind("]")
        if bracket_start != -1 and bracket_end > bracket_start:
            candidates.append(text[bracket_start : bracket_end + 1].strip())

        return [candidate for candidate in candidates if candidate]

    @staticmethod
    def _repair_json(candidate: str) -> str:
        """Apply safe, lossless-ish fixes for common LLM JSON mistakes."""
        repaired = candidate.strip()
        # Remove trailing commas before a closing brace/bracket.
        repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
        # Replace smart quotes that models sometimes emit.
        repaired = repaired.replace("\u201c", '"').replace("\u201d", '"')
        repaired = repaired.replace("\u2018", "'").replace("\u2019", "'")
        return repaired

    def _parse_response(self, text: str, schema: type[BaseModel], label: str) -> BaseModel:
        last_error: Exception | None = None

        for candidate in self._json_candidates(text):
            for attempt in (candidate, self._repair_json(candidate)):
                try:
                    return schema.model_validate_json(attempt)
                except ValidationError as exc:
                    last_error = exc
                except ValueError as exc:
                    last_error = exc

                try:
                    parsed = json.loads(attempt)
                except (TypeError, ValueError) as exc:
                    last_error = exc
                    continue

                try:
                    return schema.model_validate(parsed)
                except ValidationError as exc:
                    last_error = exc

        logger.error(
            "OpenRouter returned an invalid %s payload (error=%s)",
            label,
            type(last_error).__name__ if last_error else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"The LLM provider returned a response that did not match the required "
                f"{label} schema. Try again, or switch to a stronger model."
            ),
        )

    async def _generate_structured(
        self,
        system_instruction: str,
        prompt: str,
        schema: type[BaseModel],
        label: str,
    ) -> BaseModel:
        """Call the model and parse its output, retrying once with a repair prompt."""
        text = await self._call(system_instruction, prompt, schema)
        try:
            return self._parse_response(text, schema, label)
        except HTTPException:
            logger.warning("Retrying OpenRouter %s generation with a repair prompt", label)

        repair_prompt = (
            f"{prompt}\n\n"
            "### Previous Invalid Output:\n"
            f"{text[:6000]}\n\n"
            "The previous output did not match the required JSON schema. "
            "Return ONLY valid JSON that strictly matches the schema. "
            "Do not include markdown fences, comments, or explanatory text."
        )
        repaired_text = await self._call(system_instruction, repair_prompt, schema)
        return self._parse_response(repaired_text, schema, label)

    async def generate_srs(
        self, user_requirement: str, project_context: dict[str, Any] | None = None
    ) -> SRSContent:
        prompt_parts = [f"### User Requirements:\n{user_requirement.strip()}\n"]
        if project_context:
            prompt_parts.append(f"### Project Context:\n{json.dumps(project_context, indent=2)}\n")
        prompt_parts.append(
            "Compile the complete, schema-valid Software Requirements Specification (SRS)."
        )
        return await self._generate_structured(
            "You are the AgentForge AI Lead Software Architect and Requirements Engineering Agent.",
            "\n".join(prompt_parts),
            SRSContent,
            "SRS",
        )

    async def generate_architecture_plan(
        self,
        srs: SRSContent,
        project_context: dict[str, Any] | None = None,
        repo_context: str | None = None,
    ) -> ArchitecturePlanContent:
        prompt_parts = [f"### Approved SRS:\n{srs.model_dump_json(indent=2)}\n"]
        if project_context:
            prompt_parts.append(f"### Project Context:\n{json.dumps(project_context, indent=2)}\n")
        if repo_context:
            prompt_parts.append(f"### Existing Repository Context:\n{repo_context}\n")
        prompt_parts.append("Produce the complete technical architecture plan.")
        return await self._generate_structured(
            "You are the AgentForge AI Senior Software Architect.",
            "\n".join(prompt_parts),
            ArchitecturePlanContent,
            "architecture plan",
        )

    async def generate_tasks(
        self,
        srs: SRSContent,
        architecture: ArchitecturePlanContent | None = None,
        project_context: dict[str, Any] | None = None,
        additional_context: str | None = None,
    ) -> TaskPlanContent:
        prompt_parts = [f"### Approved SRS:\n{srs.model_dump_json(indent=2)}\n"]
        if architecture:
            prompt_parts.append(
                f"### Architecture Plan:\n{architecture.model_dump_json(indent=2)}\n"
            )
        if project_context:
            prompt_parts.append(f"### Project Context:\n{json.dumps(project_context, indent=2)}\n")
        if additional_context:
            prompt_parts.append(f"### Additional Context:\n{additional_context}\n")
        prompt_parts.append("Produce the complete, ordered, dependency-aware task plan.")
        return await self._generate_structured(
            "You are the AgentForge AI Engineering Lead and Sprint Planner.",
            "\n".join(prompt_parts),
            TaskPlanContent,
            "task plan",
        )
