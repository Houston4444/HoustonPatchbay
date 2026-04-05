import logging
from typing import TypeVar


class LogStr:
    func_args = ''


_logger = logging.getLogger(__name__)

T = TypeVar('T')

def patchbay_api(func: T) -> T:
    '''decorator for API callable functions.
    It makes debug logs and also a global logging string
    usable directly in the functions'''

    def wrapper(*args, **kwargs):
        args_strs = [str(arg) for arg in args]
        args_strs += [f"{k}={v}" for k, v in kwargs.items()]

        LogStr.func_args = f"{func.__name__}({', '.join(args_strs)})" # type:ignore
        _logger.debug(LogStr.func_args)
        return func(*args, **kwargs) # type:ignore
    return wrapper # type:ignore
