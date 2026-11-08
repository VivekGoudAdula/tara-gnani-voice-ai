"""Base provider interfaces and result models for outbound communications."""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ProviderRequest(BaseModel):
    """Payload passed to an outbound communication provider."""

    recipient_phone: str
    variables: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ProviderResult(BaseModel):
    """Normalized response returned from a communication provider."""

    success: bool
    provider_ref: str | None = None
    raw_response: dict[str, Any] | None = None
    error: str | None = None
    status: str = "DISPATCHED"
    ambiguous_dispatch: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CommunicationProvider(ABC):
    """Abstract base class for all communication channel providers."""

    name: str
    channel: str

    @abstractmethod
    async def send(self, request: ProviderRequest) -> ProviderResult:
        """
        Dispatch outbound communication to recipient.

        Returns ProviderResult containing dispatch reference or error details.
        """
        raise NotImplementedError
