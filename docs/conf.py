# Configuration file for the Sphinx documentation builder.

import os
import sys
from datetime import datetime

# Add the source directory to the path so that autodoc can find the modules
sys.path.insert(0, os.path.abspath("../src"))

# -- Project information -----------------------------------------------------
project = "FastAPI Payments"
copyright = f"{datetime.now().year}, InnerKore"
author = "InnerKore"

# The full version, including alpha/beta/rc tags
release = "0.1.0"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx.ext.autosummary",
    "autodocsumm",
    "sphinx_copybutton",
    "sphinxcontrib.httpdomain",
    "myst_parser",
    "notfound.extension",
    "sphinxext.opengraph",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
source_suffix = ".rst"
master_doc = "index"
language = "en"

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = [
    "css/custom.css",
]
html_logo = "_static/logo.png"
html_favicon = "_static/favicon.ico"
html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": False,
    "logo_only": False,
}

# Output file base name for HTML help builder
htmlhelp_basename = "FastAPIPaymentsdoc"

# -- Extension configuration -------------------------------------------------
autodoc_default_options = {
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "show-inheritance": True,
    "autosummary": True,
}
autodoc_member_order = "bysource"
autodoc_typehints = "description"

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_attr_annotations = True

# MyST parser settings
myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "deflist",
    "dollarmath",
    "linkify",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3

# -- Intersphinx mapping ----------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "fastapi": ("https://fastapi.tiangolo.com", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}
