"""Tests for Story A5 — provider registry, build_providers, build_strategy."""

from __future__ import annotations

import httpx
import pytest

from app.config import settings
from app.travel_times_subsystem.engine import EngineStrategy
from app.travel_times_subsystem.google_provider import GoogleTravelTimeProvider
from app.travel_times_subsystem.provider_factory import (
    ConfigurationError,
    build_providers,
    build_strategy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def http_client():
    """A real httpx.Client for provider construction; no HTTP is actually made."""
    with httpx.Client() as client:
        yield client


# ---------------------------------------------------------------------------
# ConfigurationError
# ---------------------------------------------------------------------------

def test_configuration_error_is_a_runtime_error():
    err = ConfigurationError("bad config")
    assert isinstance(err, RuntimeError)
    assert str(err) == "bad config"


# ---------------------------------------------------------------------------
# build_providers — happy paths
# ---------------------------------------------------------------------------

def test_build_providers_google_returns_one_google_provider(http_client):
    old = settings.TRAVEL_TIME_PROVIDERS
    settings.TRAVEL_TIME_PROVIDERS = "google"
    try:
        providers = build_providers(http_client)
        assert len(providers) == 1
        assert isinstance(providers[0], GoogleTravelTimeProvider)
    finally:
        settings.TRAVEL_TIME_PROVIDERS = old


def test_build_providers_preserves_config_order(http_client):
    """Listing 'google' twice returns two instances in order."""
    old = settings.TRAVEL_TIME_PROVIDERS
    settings.TRAVEL_TIME_PROVIDERS = "google,google"
    try:
        providers = build_providers(http_client)
        assert len(providers) == 2
        assert all(isinstance(p, GoogleTravelTimeProvider) for p in providers)
    finally:
        settings.TRAVEL_TIME_PROVIDERS = old


def test_build_providers_strips_whitespace_around_names(http_client):
    old = settings.TRAVEL_TIME_PROVIDERS
    settings.TRAVEL_TIME_PROVIDERS = "  google , google  "
    try:
        providers = build_providers(http_client)
        assert len(providers) == 2
    finally:
        settings.TRAVEL_TIME_PROVIDERS = old


# ---------------------------------------------------------------------------
# build_providers — error paths
# ---------------------------------------------------------------------------

def test_build_providers_unknown_name_raises_with_context(http_client):
    old = settings.TRAVEL_TIME_PROVIDERS
    settings.TRAVEL_TIME_PROVIDERS = "fantasy_provider"
    try:
        with pytest.raises(ConfigurationError) as exc_info:
            build_providers(http_client)
        message = str(exc_info.value)
        assert "fantasy_provider" in message   # tells operator what was wrong
        assert "google" in message             # tells operator what is valid
    finally:
        settings.TRAVEL_TIME_PROVIDERS = old


def test_build_providers_empty_string_raises(http_client):
    old = settings.TRAVEL_TIME_PROVIDERS
    settings.TRAVEL_TIME_PROVIDERS = ""
    try:
        with pytest.raises(ConfigurationError):
            build_providers(http_client)
    finally:
        settings.TRAVEL_TIME_PROVIDERS = old


def test_build_providers_whitespace_only_raises(http_client):
    """Commas with only spaces between them produce an empty name list."""
    old = settings.TRAVEL_TIME_PROVIDERS
    settings.TRAVEL_TIME_PROVIDERS = "  ,  ,  "
    try:
        with pytest.raises(ConfigurationError):
            build_providers(http_client)
    finally:
        settings.TRAVEL_TIME_PROVIDERS = old


def test_build_providers_mixed_valid_and_unknown_raises(http_client):
    """A single bad name in a list still raises — no partial builds."""
    old = settings.TRAVEL_TIME_PROVIDERS
    settings.TRAVEL_TIME_PROVIDERS = "google,does_not_exist"
    try:
        with pytest.raises(ConfigurationError) as exc_info:
            build_providers(http_client)
        assert "does_not_exist" in str(exc_info.value)
    finally:
        settings.TRAVEL_TIME_PROVIDERS = old


# ---------------------------------------------------------------------------
# build_strategy — happy paths
# ---------------------------------------------------------------------------

def test_build_strategy_single_returns_single():
    old = settings.TRAVEL_TIME_STRATEGY
    settings.TRAVEL_TIME_STRATEGY = "single"
    try:
        assert build_strategy() == EngineStrategy.SINGLE
    finally:
        settings.TRAVEL_TIME_STRATEGY = old


def test_build_strategy_fallback_chain_returns_fallback_chain():
    old = settings.TRAVEL_TIME_STRATEGY
    settings.TRAVEL_TIME_STRATEGY = "fallback_chain"
    try:
        assert build_strategy() == EngineStrategy.FALLBACK_CHAIN
    finally:
        settings.TRAVEL_TIME_STRATEGY = old


# ---------------------------------------------------------------------------
# build_strategy — error paths
# ---------------------------------------------------------------------------

def test_build_strategy_invalid_value_raises_with_context():
    old = settings.TRAVEL_TIME_STRATEGY
    settings.TRAVEL_TIME_STRATEGY = "turbo_mode"
    try:
        with pytest.raises(ConfigurationError) as exc_info:
            build_strategy()
        message = str(exc_info.value)
        assert "turbo_mode" in message   # tells operator what they wrote
        assert "single" in message       # tells operator what is valid
    finally:
        settings.TRAVEL_TIME_STRATEGY = old
