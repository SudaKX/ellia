from enum import IntFlag


class PlayerInterfaces(IntFlag):
    NONE = 0
    PROGRESS = 1
    ARTIFACTS = 2
    ACCOUNTS = 4
    CREDITS = 8
    HINTS = 16
    TASKS = 32
    ALL = PROGRESS | ARTIFACTS | ACCOUNTS | CREDITS | HINTS | TASKS
