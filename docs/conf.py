# Configuration file for the Sphinx documentation builder.

import os
import sys

# Add scripts directory to Python path
sys.path.insert(0, os.path.abspath("../scripts"))

# -- Project information -----------------------------------------------------

project = "llama-gguf-inference"
copyright = "2024, llama-gguf-inference contributors"
author = "llama-gguf-inference contributors"
release = "1.0.0"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",  # Auto-generate docs from docstrings
    "sphinx.ext.napoleon",  # Support for Google/NumPy style docstrings
    "sphinx.ext.viewcode",  # Add links to source code
    "sphinx.ext.githubpages",  # Create .nojekyll file for GitHub Pages
    "sphinxcontrib.mermaid",  # Mermaid diagram support
    "myst_parser",  # Markdown support
]

# Mermaid configuration
mermaid_version = "10.6.1"
mermaid_init_js = """
mermaid.initialize({
    startOnLoad: true,
    theme: 'default',
    securityLevel: 'loose',
});
"""

# MyST parser configuration (for Markdown files)
myst_enable_extensions = [
    "colon_fence",  # ::: fences
    "deflist",  # Definition lists
    "html_image",  # HTML images
]

# Configure MyST to recognize mermaid code blocks as directives
# This prevents "Pygments lexer name 'mermaid' is not known" warnings
myst_fence_as_directive = ["mermaid"]

# Support both .rst and .md files
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]  # Changed from [] to ['_static']

# Theme options
html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": False,
}

# -- Extension configuration -------------------------------------------------

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

# Napoleon settings (for Google/NumPy docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Suppress warnings for auto-generated docs with missing cross-references
suppress_warnings = [
    "myst.xref_missing",  # Missing cross-references in auto-generated docs
]
