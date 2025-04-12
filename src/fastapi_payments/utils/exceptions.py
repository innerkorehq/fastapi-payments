class PaymentError(Exception):
    """Base class for payment-related exceptions."""

    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ProviderError(PaymentError):
    """Exception raised when a payment provider returns an error."""

    def __init__(
        self,
        message: str,
        code: str = None,
        provider: str = None,
        provider_error: str = None,
    ):
        self.provider = provider
        self.provider_error = provider_error
        super().__init__(message, code)


class ConfigurationError(PaymentError):
    """Exception raised when there is a configuration error."""

    pass


class ValidationError(PaymentError):
    """Exception raised when there is a validation error."""

    pass


class ResourceNotFoundError(PaymentError):
    """Exception raised when a resource is not found."""

    pass


class AuthenticationError(PaymentError):
    """Exception raised when there is an authentication error with the payment provider."""

    pass


class WebhookError(PaymentError):
    """Exception raised when there is an error processing a webhook."""

    pass


class DatabaseError(PaymentError):
    """Exception raised when there is a database error."""

    pass


class PaymentRequiresActionError(PaymentError):
    """Exception raised when a payment requires additional action."""

    def __init__(self, message: str, action_url: str = None, action_type: str = None):
        self.action_url = action_url
        self.action_type = action_type
        super().__init__(message, "payment_requires_action")
