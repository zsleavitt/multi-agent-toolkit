"""Google Generative AI model provider (MAT-53)."""

from __future__ import annotations

from typing import Any

from mat_runtime.providers._utils import require_api_key
from mat_runtime.providers.errors import map_gemini_error
from mat_runtime.providers.model import ModelResponse, ProviderError


class GeminiProvider:
    """Direct Google Generative AI adapter."""

    def __init__(self, *, api_key: str | None = None, client: Any | None = None) -> None:
        if client is not None:
            self._client = client
            return
        key = require_api_key(api_key, "GOOGLE_API_KEY")
        import google.generativeai as genai

        genai.configure(api_key=key)
        # Store the module (not a client instance) — GenerativeModel is constructed per call.
        self._client = genai

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        max_tokens: int,
        timeout_ms: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        generation_config: dict[str, Any] = {"max_output_tokens": max_tokens}
        request_options: dict[str, Any] = {}
        if timeout_ms is not None:
            request_options["timeout"] = timeout_ms / 1000.0

        try:
            generative_model = self._client.GenerativeModel(model)
            response = generative_model.generate_content(
                prompt,
                generation_config=generation_config,
                request_options=request_options or None,
                **kwargs,
            )
        except ProviderError:
            raise
        except Exception as exc:
            err = map_gemini_error(exc)
            return ModelResponse(
                ok=False,
                text="",
                input_tokens=None,
                output_tokens=None,
                model=model,
                stop_reason=None,
                error=err,
            )

        text = getattr(response, "text", "") or ""
        usage = getattr(response, "usage_metadata", None)
        stop_reason = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None)
            if finish_reason is not None:
                stop_reason = str(finish_reason.name if hasattr(finish_reason, "name") else finish_reason)

        return ModelResponse(
            ok=True,
            text=text,
            input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
            model=model,
            stop_reason=stop_reason,
        )
