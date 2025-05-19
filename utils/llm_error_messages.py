import openai
from anthropic import (
    BadRequestError, RateLimitError, InternalServerError, AnthropicError,
    AuthenticationError, APIConnectionError, APITimeoutError,
    PermissionDeniedError, NotFoundError, ConflictError, UnprocessableEntityError
)

class LLMErrorMessages:
    """Class to handle error messages for OpenAI and Anthropic APIs."""

    # Define constants for error messages and codes
    OPENAI_ERROR_MESSAGES = {
        openai.APIConnectionError: ("Fynix Agent is Unable to Establish Connection to API, please try again after Some time", 2001),
        openai.RateLimitError: ("Fynix Agent API request has exceeded the rate limit. please try again after Some time", 2002),
        openai.Timeout: ("Fynix Agent API Timeout Error. please try again after Some time", 2006)
    }

    DEFAULT_OPENAI_ERROR_MESSAGE = ("Fynix Agent Couldn't Complete Request", 2007)
    INVALID_REQUEST_DEFAULT_MESSAGE = ("Fynix Agent API cannot process the input due to invalid request details", 2005)

    ANTHROPIC_ERROR_MESSAGES = {
        APIConnectionError: ("Fynix Agent is unable to establish a connection to the Anthropic API. Please try again after some time or try with another model.", 1001),
        APITimeoutError: ("Fynix Agent request to the Anthropic API timed out. Please try again after some time or try with another model.", 1002),
        RateLimitError: ("Fynix Agent API request to Anthropic has exceeded the rate limit. Please try again after some time or try with another model.", 1003),
        BadRequestError: ("Fynix Agent encountered a bad request error with the Anthropic API. Please try with a different model.", 1004),
        AuthenticationError: ("Fynix Agent is unauthorized to access the Anthropic API. Please check your API key.", 1005),
        PermissionDeniedError: ("Fynix Agent does not have permission to access the requested resource in the Anthropic API.", 1006),
        NotFoundError: ("Fynix Agent couldn't find the requested resource in the Anthropic API.", 1007),
        ConflictError: ("Fynix Agent encountered a conflict error with the Anthropic API. This may be due to conflicting data.", 1008),
        InternalServerError: ("Fynix Agent encountered an internal server error with the Anthropic API. Please try again later.", 1010)
    }

    DEFAULT_ANTHROPIC_ERROR_MESSAGE = ("Fynix Agent encountered an unexpected error with the Anthropic API", 1011)

    @staticmethod
    def get_openai_invalid_request_message(error):
        """Retrieve message for specific OpenAI InvalidRequestError codes."""
        error_code_messages = {
            'string_above_max_length': ("Fynix Agent is unable to process strings that exceed the maximum length limit.", 2003),
            'context_length_exceeded': (f"Fynix Agent Can't Process Input : {str(error)}", 2004)
        }
        return error_code_messages.get(error.code, (f"{LLMErrorMessages.INVALID_REQUEST_DEFAULT_MESSAGE[0]}: {str(error)}", LLMErrorMessages.INVALID_REQUEST_DEFAULT_MESSAGE[1]))

    @classmethod
    def get_openai_error_message(cls, error):
        """Return a user-friendly message and code for OpenAI API errors."""
        if isinstance(error, openai.BadRequestError):
            return cls.get_openai_invalid_request_message(error)

        return cls.OPENAI_ERROR_MESSAGES.get(type(error), (f"{cls.DEFAULT_OPENAI_ERROR_MESSAGE[0]}: {str(error)}", cls.DEFAULT_OPENAI_ERROR_MESSAGE[1]))

    @classmethod
    def get_anthropic_error_message(cls, error):
        """Return a user-friendly message and code for Anthropic API errors."""
        if isinstance(error, UnprocessableEntityError):
            return f"Fynix Agent couldn't process the entity in the Anthropic API: {str(error)}", 1009

        return cls.ANTHROPIC_ERROR_MESSAGES.get(type(error), (f"{cls.DEFAULT_ANTHROPIC_ERROR_MESSAGE[0]}: {str(error)}", cls.DEFAULT_ANTHROPIC_ERROR_MESSAGE[1]))
