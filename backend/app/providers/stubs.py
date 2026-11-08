"""Stub providers for channels not yet implemented (WhatsApp, SMS, Email)."""

from app.providers.base import CommunicationProvider, ProviderRequest, ProviderResult


class WhatsAppProvider(CommunicationProvider):
    """Stub provider for WhatsApp communications."""

    name = "whatsapp_stub"
    channel = "whatsapp"

    async def send(self, request: ProviderRequest) -> ProviderResult:
        """Return not implemented result."""
        return ProviderResult(
            success=False,
            error="channel not implemented",
            status="NOT_IMPLEMENTED",
        )


class SMSProvider(CommunicationProvider):
    """Stub provider for SMS communications."""

    name = "sms_stub"
    channel = "sms"

    async def send(self, request: ProviderRequest) -> ProviderResult:
        """Return not implemented result."""
        return ProviderResult(
            success=False,
            error="channel not implemented",
            status="NOT_IMPLEMENTED",
        )


class EmailProvider(CommunicationProvider):
    """Stub provider for Email communications."""

    name = "email_stub"
    channel = "email"

    async def send(self, request: ProviderRequest) -> ProviderResult:
        """Return not implemented result."""
        return ProviderResult(
            success=False,
            error="channel not implemented",
            status="NOT_IMPLEMENTED",
        )
