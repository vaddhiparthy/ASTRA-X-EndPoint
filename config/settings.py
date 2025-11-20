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

"""
Configuration and prompt loading for ASTRA‑X‑Aggregator.

This module centralises all configurable settings (provider, model names,
hosts) and also exposes helpers to read prompt instructions from plain
text files located in the ``config`` directory.  Separating prompt
instructions into their own files makes it easy to tweak the agent’s
behaviour and output format without touching Python code.  See
``prompt_static.txt`` and ``prompt_structure.txt`` for details.

Environment variables override most settings.  For example you can
export ``LLM_PROVIDER=openai`` and provide ``OPENAI_API_KEY`` to
switch from Ollama to the OpenAI Chat Completions API.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Literal, Optional

# Literal type for supported language model providers.  Extend this
# type and the corresponding logic in ``app.main.call_llm`` if you
# integrate additional providers (e.g. Anthropic).
Provider = Literal["ollama", "openai"]


@dataclass
class LLMConfig:
    """Container for all configurable parameters.

    Values are read from environment variables at import time with
    fallbacks to sensible defaults.  The prompt files are *not* loaded
    here; instead use ``get_static_prompt()`` and
    ``get_structure_prompt()`` to read the contents of
    ``prompt_static.txt`` and ``prompt_structure.txt`` respectively.
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
    # requests to succeed.  ``openai_model`` defaults to a sensible
    # ChatGPT model name; change as needed.
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4-1106-preview")

    # Paths to the static and structure prompt files.  These can be
    # overridden via ``PROMPT_STATIC_PATH`` and ``PROMPT_STRUCTURE_PATH``
    # environment variables.  Defaults point to files in the same
    # directory as this settings module.
    prompt_static_path: Path = Path(
        os.getenv(
            "PROMPT_STATIC_PATH", (Path(__file__).parent / "prompt_static.txt").as_posix()
        )
    )
    prompt_structure_path: Path = Path(
        os.getenv(
            "PROMPT_STRUCTURE_PATH",
            (Path(__file__).parent / "prompt_structure.txt").as_posix(),
        )
    )

    # A fallback system prompt if the prompt files are missing and
    # ``SYSTEM_PROMPT`` is not set.  This ensures the agent still
    # behaves reasonably even if configuration files are absent.
    default_system_prompt: str = (
        "You are ASTRA-X Aggregator, a home assistant that reads events, "
        "cleans them up and explains what is going on in clear English."
    )

    # Additional custom system prompt loaded from the environment.  If
    # provided this text will be appended to the prompts loaded from
    # files when constructing LLM messages.  This makes it easy to
    # override behaviour without editing files.  Leave unset for
    # production.
    system_prompt_override: Optional[str] = os.getenv("SYSTEM_PROMPT")


# Instantiate a single global settings object.  Other modules should
# import ``settings`` instead of instantiating LLMConfig themselves so
# that all parts of the application use the same configuration.
settings = LLMConfig()


def _read_file(path: Path) -> Optional[str]:
    """Read the contents of a text file and return it or None.

    Any leading/trailing whitespace is stripped.  Errors are
    suppressed; the caller should provide sensible fallbacks.
    """
    try:
        text = path.read_text(encoding="utf-8")
        return text.strip()
    except Exception:
        return None


def get_static_prompt() -> str:
    """Return the static prompt instructions.

    This text typically contains high‑level identity and behaviour
    guidelines that rarely change.  The file location is defined by
    ``settings.prompt_static_path`` and can be overridden via
    environment variable.  If the file is missing, falls back to an
    empty string.
    """
    text = _read_file(Path(settings.prompt_static_path))
    return text or ""


def get_structure_prompt() -> str:
    """Return the structure prompt instructions.

    This text contains guidelines for the desired response format or
    structure (e.g. how to format summaries).  The file location is
    defined by ``settings.prompt_structure_path`` and can be
    overridden via environment variable.  If the file is missing,
    returns an empty string.
    """
    text = _read_file(Path(settings.prompt_structure_path))
    return text or ""


def get_system_prompt() -> str:
    """Assemble the full system prompt from files and overrides.

    This helper concatenates the static prompt, structure prompt and
    any override text.  If all sources are missing it uses
    ``settings.default_system_prompt``.  It may return an empty
    string if prompts are deliberately disabled.
    """
    parts = []
    static = get_static_prompt()
    structure = get_structure_prompt()
    if static:
        parts.append(static)
    if structure:
        parts.append(structure)
    if settings.system_prompt_override:
        parts.append(settings.system_prompt_override)
    if parts:
        return "\n\n".join(parts)
    # Fallback to default system prompt
    return settings.default_system_prompt