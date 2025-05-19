from sentry_sdk import capture_exception, capture_message

from utils.exceptions import ApplicationException
from utils.llm_error_messages import LLMErrorMessages
from utils.serializers import ResponseData
from config.logging import logger, get_call_stack
from prometheus.metrics import EXCEPTION_COUNTER
from openai import OpenAIError
from anthropic import AnthropicError
from fex_utilities.utils.exceptions import ApplicationException as FexUtilityApplicationException

class BaseView:
    default_error_message = "Something went wrong with this, please retry. Do not worry, this won't be counted in your usage."
    @staticmethod
    def construct_success_response(data=None, message="", code=200):
        return ResponseData.construct(success=True, data=data or {}, message=message, code=code)

    @classmethod
    def construct_error_response(cls, exp, message="", code=5001):
        logger.error("Error: %s", str(exp), call_stack=get_call_stack())
        if isinstance(exp, Exception):
            capture_exception(exp)
        elif isinstance(exp, str):
            capture_message(exp)

        if isinstance(exp, OpenAIError):
            error_message, code = LLMErrorMessages.get_openai_error_message(exp)
        elif isinstance(exp, AnthropicError):
            error_message, code = LLMErrorMessages.get_anthropic_error_message(exp)
        elif isinstance(exp, ApplicationException) or isinstance(exp, FexUtilityApplicationException):
            code = exp.error_code
            error_message = exp.message
        else:
            code = 5001
            error_message = str(cls.default_error_message)

        # Increment the Prometheus counter with exception details
        EXCEPTION_COUNTER.labels(exception_type=type(exp).__name__, code=code).inc()

        return ResponseData.construct(
            success=False,
            data=[],
            message=message or error_message,
            errors=[error_message],
            code=code
        ) 