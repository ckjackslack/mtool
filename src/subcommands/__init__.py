import sys
from pathlib import Path

toplevel = Path(".").parent.absolute()
sys.path.append(str(toplevel))