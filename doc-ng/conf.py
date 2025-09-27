# Configuration file for the Sphinx documentation builder.

# Python Environment Extensions

import sys
from pathlib import Path

MMH_BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MMH_BASE))

import makemehappy.utilities as mmh  # noqa: E402

# Basic Information

project = 'MakeMeHappy'
author = 'Frank Terbeck'
release = mmh.stdoutProcess(str(MMH_BASE / 'version'))[0]

extensions = []
# templates_path = ['_templates']
exclude_patterns = ['build', '.env']

# HTML Output Setup

html_theme = 'pydata_sphinx_theme'
# html_static_path = ['_static']
html_show_sourcelink = False

# LaTeX/PDF Output Setup

latex_theme = 'manual'
latex_elements = {
    'fncychap': '\\usepackage[Glenn]{fncychap}'
}
