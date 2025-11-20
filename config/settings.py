"""
Global configuration for ASTRA‑X‑Aggregator.

This module centralises all configurable settings such as the LLM
provider, API hosts, model names and system prompts.  By changing
environment variables or editing these defaults you can swap out
providers (e.g. Ollama vs OpenAI), point to different model hosts,
update the system prompt or add API keys without hunting through the
codebase.  The dataclass schema exposes each setting as an attribute
with type hints and sensible defaults.

To override a setting at runtime set the corresponding environment
variable.  For example, to run against a local Ollama instance on
Windows Docker Desktop you might export::

    export LLM_PROVIDER="ollama"
    export OLLAMA_HOST="http://host.docker.internal:11434"
    export OLLAMA_MODEL="llama3"
    export SYSTEM_PROMPT="You are a helpful home assistant."

If you decide to switch to OpenAI/ChatGPT you can set
``LLM_PROVIDER="openai"`` and provide ``OPENAI_API_KEY`` and
``OPENAI_MODEL`` accordingly.  The application will automatically
route calls to the appropriate backend based on this configuration.
"""

from dataclasses import dataclass
import os
from typing import Literal, Optional

# Literal type for supported language model providers.  Extend this
# type and the corresponding logic in ``app.main.call_llm`` if you
# integrate additional providers (e.g. Anthropic).
Provider = Literal["ollama", "openai"]


@dataclass
class LLMConfig:
    """Container for all configurable parameters.

    Values are read from environment variables at import time with
    fallbacks to sensible defaults.  Attributes can be modified
    programmatically if desired.
    """

    # Which provider to use for inference.  Supported values: "ollama"
    # (default) and "openai".  When set to "openai" the application
    # will call the OpenAI Chat Completions API instead of Ollama.
    provider: Provider = os.getenv("LLM_PROVIDER", "ollama")  # type: ignore[assignment]

    # Host and model name for Ollama.  When provider == "ollama"
    # these settings define the base URL and the model name to use
    # when calling the Ollama API.
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "hola")

    # API key and model name for OpenAI.  These are only used when
    # provider == "openai".  ``openai_api_key`` must be set for
    # requests to succeed.  ``openai_model`` defaults to a sane
    # ChatGPT model name; change as needed.
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4-1106-preview")

    # System prompt injected as the first message in every LLM call.
    # Customise this string to control the assistant’s behaviour.  You
    # can override via the ``SYSTEM_PROMPT`` environment variable.
    system_prompt: str = os.getenv(
        "SYSTEM_PROMPT",
        "You are ASTRA-X Aggregator, a home assistant that reads events, "
        "cleans them up and explains what is going on in clear English.",
    )


# Instantiate a single global settings object.  Other modules should
# import ``settings`` instead of instantiating LLMConfig themselves so
# that all parts of the application use the same configuration.
settings = LLMConfig()