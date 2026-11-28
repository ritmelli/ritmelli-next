# sounddevice has no types: what the device check takes from it is Any.
from typing import Any

def __getattr__(name: str) -> Any: ...
