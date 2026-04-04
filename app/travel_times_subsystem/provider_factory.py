"""Travel-time provider registry and engine factory (Story A5)."""

from typing import Callable

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.travel_times_subsystem.engine import EngineStrategy, TravelTimeEngine
from app.travel_times_subsystem.google_provider import GoogleTravelTimeProvider
from app.travel_times_subsystem.providers import TravelTimeProvider
from app.travel_times_subsystem.resolvers import DbLocationResolver


class ConfigurationError(RuntimeError):
    """Raised when travel-time provider config is invalid at startup."""


# Maps a provider name (as used in TRAVEL_TIME_PROVIDERS) to a callable that
# builds a provider instance given a shared httpx.Client.
# To add a new provider, register it here — nothing else needs to change.
ProviderFactory = Callable[[httpx.Client], TravelTimeProvider]

_PROVIDER_REGISTRY: dict[str, ProviderFactory] = {
    "google": lambda client: GoogleTravelTimeProvider(
        client=client,
        api_key=settings.GOOGLE_MAPS_API_KEY,
        base_url=settings.GOOGLE_DISTANCE_MATRIX_BASE_URL,
        max_retries=settings.GOOGLE_DISTANCE_MATRIX_MAX_RETRIES,
    ),
}


def build_providers(client: httpx.Client) -> list[TravelTimeProvider]:
    """Build an ordered list of providers from TRAVEL_TIME_PROVIDERS config."""
    names = [n.strip() for n in settings.TRAVEL_TIME_PROVIDERS.split(",") if n.strip()]
    if not names:
        raise ConfigurationError(
            "TRAVEL_TIME_PROVIDERS must not be empty. "
            f"Known providers: {list(_PROVIDER_REGISTRY)}"
        )
    providers: list[TravelTimeProvider] = []
    for name in names:
        factory = _PROVIDER_REGISTRY.get(name)
        if factory is None:
            raise ConfigurationError(
                f"Unknown travel-time provider: {name!r}. "
                f"Known providers: {list(_PROVIDER_REGISTRY)}"
            )
        providers.append(factory(client))
    return providers


def build_strategy() -> EngineStrategy:
    """Parse TRAVEL_TIME_STRATEGY into an EngineStrategy enum value."""
    try:
        return EngineStrategy(settings.TRAVEL_TIME_STRATEGY)
    except ValueError:
        valid = [e.value for e in EngineStrategy]
        raise ConfigurationError(
            f"Unknown travel-time strategy: {settings.TRAVEL_TIME_STRATEGY!r}. "
            f"Valid values: {valid}"
        )


def build_travel_time_engine(db: Session) -> TravelTimeEngine:
    """Build a fully wired TravelTimeEngine from current config and a DB session."""
    client = httpx.Client(timeout=settings.GOOGLE_DISTANCE_MATRIX_TIMEOUT)
    providers = build_providers(client)
    strategy = build_strategy()
    resolver = DbLocationResolver(db)
    return TravelTimeEngine(providers=providers, strategy=strategy, resolver=resolver)
