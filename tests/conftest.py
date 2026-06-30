import sys
from pathlib import Path

# Add the repository root directory (which contains 'plugins') to sys.path
root_dir = Path(__file__).resolve().parents[1]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
