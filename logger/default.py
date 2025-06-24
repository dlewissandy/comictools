from logger.generic import Logger


class DefaultLogger(Logger):

    """
    A default logger implementation that uses the loguru library to log messages.
    """
    def trace(self, text: str):
        self._logger.trace(ellipsis(text=text))

    def debug(self, text: str):
        self._logger.debug(ellipsis(text=text))

    def info(self, text: str):
        self._logger.info(ellipsis(text=text))

    def warning(self, text: str):
        self._logger.warning(ellipsis(text=text))

    def error(self, e: Exception):
        self._logger.error(ellipsis(text=str(e)))

    def critical(self, e: Exception):
        self._logger.critical(ellipsis(text=str(e)))

    def __init__(self):
        from sys import stderr
        from loguru import logger as loguru_logger
        self._logger = loguru_logger
        self._logger.remove()  # Remove the default logger
        self._logger.add(stderr, level="ERROR", backtrace=True, diagnose=True)
        self._logger.add("app.log", rotation="10 MB", level="DEBUG", backtrace=True, diagnose=True)
    

def ellipsis(*args, text: str, max_length:int = 100) -> str:
    """
    A utility function to truncate text with an ellipsis if it exceeds a certain length.
    
    Args:
        *args: Additional arguments (not used in this implementation).
        text (str): The text to truncate.
        
    Returns:
        str: The truncated text with an ellipsis if it was too long.
    """
    if len(text) > max_length:
        return text[:max_length] + '...'
    return text