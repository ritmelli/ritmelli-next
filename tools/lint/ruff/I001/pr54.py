from __future__ import annotations

import contextlib
import itertools
import sys
from collections.abc import Callable, Iterator
from typing import Any

from ritmelli.machine.installed import ANY_NODE, ASSOCIATION, CAPTURE_KEY
from ritmelli.machine.installed import CREATED_SLOTS, EFX, EFX_LIST, EFX_MODES, LFX
from ritmelli.machine.installed import FILTER_CLSID, OUR_CLSIDS
from ritmelli.machine.installed import MFX_LIST, MODE_DEFAULT, MODE_RAW
from ritmelli.machine.installed import NO_ENHANCEMENTS, SAVED_KEY, SAVED_SLOTS, SFX
from ritmelli.machine.installed import SAVED_VERSION
