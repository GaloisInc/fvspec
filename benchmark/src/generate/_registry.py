"""Task registry for inspect_ai.

This module imports all tasks that should be discoverable by inspect_ai.
See https://inspect.aisi.org.uk/tasks.html#packaging
"""

from generate.scaffold.orchestration import fvspec

__all__ = ["fvspec"]
