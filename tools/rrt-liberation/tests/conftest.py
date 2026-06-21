import sys
from pathlib import Path

# Ensure project root is importable for `tests.fixtures` and `pipeline`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
