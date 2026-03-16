"""Root pytest configuration.

Adds the project root to sys.path so that top-level packages (e.g. ``config``)
are importable from test files without ``sys.path`` manipulation in each file.
"""

import sys
from pathlib import Path

# Insert project root at position 0 so that the `config/` package is found
# before `src/config.py` (which is added by tests/__init__.py later).
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
