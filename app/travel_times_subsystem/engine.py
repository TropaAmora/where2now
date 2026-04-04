"""Travel time engine."""

from enum import Enum
import logging

from app.travel_times_subsystem.providers import TravelTimeProvider, TravelTimeProviderError
from app.travel_times_subsystem.schemas import LatLng, TravelTimeRequest, TravelTimeResult, TravelTimeError, DeliveryPointRef
from app.travel_times_subsystem.resolvers import LocationResolver, LocationResolutionError

logger = logging.getLogger(__name__)

class EngineStrategy(str, Enum):
    SINGLE = "single"
    FALLBACK_CHAIN = "fallback_chain"

class TravelTimeEngine:
    """Travel time engine."""

    def __init__(self, providers: list[TravelTimeProvider], strategy: EngineStrategy, resolver: LocationResolver):
        if not providers:
            raise ValueError("TravelTimeEngine requires at least one provider")
        self.providers = providers
        self.strategy = strategy
        self.resolver = resolver

    def get_travel_times(self, request: TravelTimeRequest) -> TravelTimeResult:
        """"""
        request_id = request.metadata.request_id if request.metadata else None
        try:
            resolved_request = self._resolve_request_locations(request)
        except LocationResolutionError as exc:
          return TravelTimeResult(
              request_id=request_id,
              provider="engine",
              errors=[
                  TravelTimeError(
                      message=exc.message,
                      code="location_resolution_failed",
                  )
              ],
          )

        if self.strategy == EngineStrategy.SINGLE:
            provider = self.providers[0]
            try:
                return self._call_provider(provider, resolved_request, request_id=request_id)
            except TravelTimeProviderError as exc:
                logger.error(f"Provider {provider.name} failed: {exc}")
                return TravelTimeResult(
                    request_id=request_id,
                    provider="engine",
                    errors=[
                        TravelTimeError(
                            message=f"Provider {provider.name} failed: {exc}",
                            code="single_provider_failed"
                        )
                    ]
                )

        if self.strategy == EngineStrategy.FALLBACK_CHAIN:
            last_error: TravelTimeProviderError | None = None
            for provider in self.providers:
                try: 
                    return self._call_provider(provider, resolved_request, request_id=request_id)
                except TravelTimeProviderError as exc:
                    last_error = exc
                    logger.warning(f"Provider {exc.provider_name} failed: {exc.message}")
            
            # All providers failed
            assert last_error is not None
            return TravelTimeResult(
                request_id=request_id,
                provider="engine",
                errors=[
                    TravelTimeError(
                        message=f"All providers failed. Last error from {last_error.provider_name}: {last_error.message}",
                        code="all_providers_failed"
                    )
                ],
            )


        return TravelTimeResult(
            request_id=request_id,
            provider="engine",
            errors=[
                TravelTimeError(
                    message=f"Unsupported strategy: {self.strategy}",
                    code="invalid_strategy"
                )
            ],
        )

    def _call_provider(self, provider: TravelTimeProvider, request: TravelTimeRequest, *, request_id: str | None) -> TravelTimeResult:
        """"""
        logger.info(f"Calling provider={provider.name} request_id={request_id}")
        result = provider.get_travel_times(request)
        return result

    def _resolve_request_locations(self, request: TravelTimeRequest) -> TravelTimeRequest:
        refs: list[DeliveryPointRef] = []
        for loc in [*request.origins, *request.destinations]:
            if isinstance(loc, DeliveryPointRef):
                refs.append(loc)

        resolved_map = self.resolver.resolve(refs) if refs else {}

        resolved_origins = [self._resolve_location(loc, resolved_map) for loc in request.origins]
        resolved_destinations = [self._resolve_location(loc, resolved_map) for loc in request.destinations]

        return request.model_copy(
            update={
                "origins": resolved_origins,
                "destinations": resolved_destinations,
            }
        )

    @staticmethod
    def _resolve_location(
        loc: LatLng | DeliveryPointRef,
        resolved_map: dict[int, LatLng],
    ) -> LatLng:
        if isinstance(loc, LatLng):
            return loc
        return resolved_map[loc.delivery_point_id]