"""Make the root_agent package importable when running pytest from root-agent/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
