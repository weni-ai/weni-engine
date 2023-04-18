from random import randint


class COLORS(object):
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    PURPLE = '\033[35m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'


class LogController(object):

    def warning(self, logText: str):
        print(f'{COLORS.WARNING} Warning: {logText}{COLORS.ENDC}')

    def fail(self, logText: str):
        print(f'{COLORS.FAIL} Fail: {logText}{COLORS.ENDC}')

    def header(self, logText: str):
        print(f'{COLORS.HEADER}{logText}{COLORS.ENDC}')

    def cyanText(self, logText: str):
        print(f'{COLORS.BLUE}RUNNING:\n{COLORS.CYAN} └─ {logText}{COLORS.ENDC}')

    def success(self):
        print(f'{COLORS.GREEN} └──── SUCCESS')

    def purpleText(self, logText: str):
        print(f'{COLORS.BLUE}RUNNING:\n{COLORS.PURPLE} └─ {logText}{COLORS.ENDC}')

    def greenText(self, logText: str):
        print(f'{COLORS.BLUE}RUNNING:\n{COLORS.GREEN} └─ {logText}{COLORS.ENDC}')

    def blueText(self, logText: str):
        print(f'{COLORS.BLUE}RUNING:\n{COLORS.BLUE} └─ {logText}{COLORS.ENDC}')

    def coloredText(self, logText: str):
        colors = [COLORS.BLUE, COLORS.GREEN, COLORS.CYAN, COLORS.PURPLE]
        print(f'{colors[(randint(1, 100000007) * randint(1, 100000007) * randint(1, 100000007)) % 4]}{logText}')
