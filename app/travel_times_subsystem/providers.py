"""Travel time providers."""

from abc import ABC, abstractmethod

from app.travel_times_subsystem.schemas import TravelTimeRequest, TravelTimeResult

class TravelTimeProviderError(Exception):
    """Represents a transient error talking to the external travel time provider API."""
    def __init__(self, provider_name: str, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.provider_name = provider_name
        self.message = message
        self.original_error = original_error

class TravelTimeProvider(ABC):
    """Abstract base for all travel time providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the provider."""
        raise NotImplementedError

    @abstractmethod
    def get_travel_times(self, request: TravelTimeRequest) -> TravelTimeResult:
        """Return the travel times for the given request."""
        raise NotImplementedError