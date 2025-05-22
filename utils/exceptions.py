from structlog.contextvars import bind_contextvars


class CustomException(Exception):
    DEFAULT_ERROR_MESSAGE = "Exception occurred"

    def __init__(self, error_message: str = None):
        error_message = error_message or self.DEFAULT_ERROR_MESSAGE
        self.error_message = error_message
        super().__init__(self.error_message)
        bind_contextvars(exception={"error_message": self.error_message})


class ApiException(CustomException):
    DEFAULT_ERROR_MESSAGE = "API Exception"


class OpenAIException(CustomException):
    DEFAULT_ERROR_MESSAGE = "Open AI Exception"


class AnthropicException(CustomException):
    DEFAULT_ERROR_MESSAGE = "Anthropic AI Exception"

class SessionExpiredException(CustomException):
    DEFAULT_MESSAGE = "Session Expired for Almanac"
    ERROR_CODE = 6001
