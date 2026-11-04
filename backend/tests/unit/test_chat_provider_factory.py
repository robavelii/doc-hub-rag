import pytest

from app.config import settings
from app.providers import factory


@pytest.fixture
def clean_settings(monkeypatch):
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "GEMINI_API_KEY", "LLM_BASE_URL", "LLM_API_KEY", "LLM_CHAT_MODEL"):
        monkeypatch.setattr(settings, name, "")
    return monkeypatch


def test_gemini_uses_its_openai_compatible_endpoint(clean_settings):
    clean_settings.setattr(settings, "GEMINI_API_KEY", "g-key")
    clean_settings.setattr(settings, "GEMINI_CHAT_MODEL", "gemini-test")
    clean_settings.setattr(settings, "GEMINI_REASONING_EFFORT", "none")

    provider = factory._build_chat_provider("gemini")

    assert provider.provider_name == "gemini"
    assert provider.chat_model_name == "gemini-test"
    assert str(provider.client.base_url).startswith("https://generativelanguage.googleapis.com/v1beta/openai")
    assert provider.client.api_key == "g-key"
    assert provider._extra == {"reasoning_effort": "none"}


def test_compatible_needs_url_key_and_model(clean_settings):
    clean_settings.setattr(settings, "LLM_BASE_URL", "https://openrouter.ai/api/v1")
    clean_settings.setattr(settings, "LLM_API_KEY", "or-key")
    assert factory._build_chat_provider("compatible") is None

    clean_settings.setattr(settings, "LLM_CHAT_MODEL", "meta/llama")
    provider = factory._build_chat_provider("compatible")

    assert provider.provider_name == "compatible"
    assert provider.chat_model_name == "meta/llama"
    assert str(provider.client.base_url).startswith("https://openrouter.ai/api/v1")
    assert provider._extra == {}


def test_unconfigured_backends_are_skipped(clean_settings):
    assert factory._build_chat_provider("openai") is None
    assert factory._build_chat_provider("gemini") is None
    assert factory._build_chat_provider("compatible") is None


def test_provider_instances_keep_their_own_names(clean_settings):
    # provider_name is per instance: FallbackProvider dedupes the chain by it.
    clean_settings.setattr(settings, "OPENAI_API_KEY", "sk-test")
    clean_settings.setattr(settings, "GEMINI_API_KEY", "g-key")

    names = [factory._build_chat_provider(n).provider_name for n in ("openai", "gemini")]

    assert names == ["openai", "gemini"]


def test_default_chain_follows_ai_provider(clean_settings):
    clean_settings.setattr(settings, "CHAT_PROVIDER_CHAIN", "")
    clean_settings.setattr(settings, "AI_PROVIDER", "gemini")

    assert settings.chat_provider_chain_list == ["gemini", "mock"]


def test_token_count_works_for_non_openai_models(clean_settings):
    clean_settings.setattr(settings, "GEMINI_API_KEY", "g-key")
    provider = factory._build_chat_provider("gemini")

    assert provider.count_tokens("hello world, this is a test") > 1
