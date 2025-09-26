# Configuration file for the Sphinx documentation builder.

project = 'MakeMeHappy'
author = 'Frank Terbeck'
release = '0.34'

extensions = []
# templates_path = ['_templates']
exclude_patterns = ['build', '.env']

html_theme = 'pydata_sphinx_theme'
# html_static_path = ['_static']
html_show_sourcelink = False

latex_theme = 'manual'
latex_elements = {
    'fncychap': '\\usepackage[Glenn]{fncychap}'
}
