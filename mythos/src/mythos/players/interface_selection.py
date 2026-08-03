from enum import IntFlag


class PlayerInterfaces(IntFlag):
    NONE = 0
    PROGRESS = 1
    ARTIFACTS = 2
    ACCOUNTS = 4
    ALL = PROGRESS | ARTIFACTS | ACCOUNTS
