"""``NetworkStatus`` with the same names and values as hummingbot's enum (no hummingbot import)."""

from enum import Enum


class NetworkStatus(Enum):
    STOPPED = 0
    NOT_CONNECTED = 1
    CONNECTED = 2
