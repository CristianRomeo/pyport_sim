import matplotlib

import _pyport  # noqa: F401  (makes the PyPort Sim packages importable)

matplotlib.use("Agg")  # no window: the plot tests only save files
