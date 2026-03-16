"""Tests initialization file."""

import sys
from pathlib import Path

# Add src directory to path for imports (appended so that the project root
# added by conftest.py retains priority for top-level packages like `config/`)
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))
