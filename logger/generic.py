from abc import ABC, abstractmethod

class Logger(ABC):
    """
    An abstract base class for logging messages.   This is used to provide a consistent interface
    for logging messages across the application.
    """
    @abstractmethod
    def trace(self, text: str):
        pass

    @abstractmethod
    def debug(self, text: str):
        pass

    @abstractmethod
    def info(self, text: str):
        pass

    @abstractmethod
    def warning(self, text: str):
        pass

    @abstractmethod
    def error(self, text: str):
        pass

    @abstractmethod
    def critical(self, text: str):
        pass
