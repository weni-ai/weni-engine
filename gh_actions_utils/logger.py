class LogStyle:
    OK = "\033[92m"
    HEADER = "\033[95m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    BOLD = "\033[1m"
    WHITE = "\033[0m"


class LogController(object):
    def __init__(self):
        self.logStyle = [
            "\033[92m",
            "\033[91m",
            "\033[0m"
        ]

    def log(self, logStyle: int, logText: str):
        print(self.logStyle[logStyle], logText)