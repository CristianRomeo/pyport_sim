"""Make the PyPort Sim packages (models, simulation, config, ...) importable.

PyPort Sim is included as a git submodule in external/pyport_sim. To use another copy of it,
set the environment variable PYPORT_PATH to its folder.
"""
import os
import sys
from pathlib import Path

_path = Path(os.environ.get("PYPORT_PATH", Path(__file__).resolve().parent / "external" / "pyport_sim"))
if not (_path / "simulation").is_dir():
    raise ImportError(
        f"PyPort Sim not found in {_path}. Run 'git submodule update --init' "
        "or set PYPORT_PATH to the folder of PyPort Sim."
    )
if str(_path) not in sys.path:
    sys.path.insert(0, str(_path))
