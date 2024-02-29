from abc import ABC, abstractstaticmethod


class BaseParser(ABC):
    @abstractstaticmethod
    def parse(stream, encoding=None):
        pass
