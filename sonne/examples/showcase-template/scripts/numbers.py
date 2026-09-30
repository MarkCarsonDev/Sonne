"""Demo data script: a per-build random number for the getting-started post."""

import random

from sonne.script_api import sonne_var

sonne_var("build_number", random.randint(1, 100))
