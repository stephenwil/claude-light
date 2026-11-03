import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("board", "hooks"):
    sys.path.insert(0, str(ROOT / sub))
