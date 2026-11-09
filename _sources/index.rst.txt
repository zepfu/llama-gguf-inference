llama-gguf-inference Documentation
===================================

**GGUF model inference server using llama.cpp**

Welcome to the documentation for llama-gguf-inference, a production-ready inference server for GGUF models.

.. toctree::
   :maxdepth: 2
   :caption: User Guides:

   API_REFERENCE
   AUTHENTICATION
   CONFIGURATION
   DEPLOYMENT
   MIGRATION
   TESTING
   TROUBLESHOOTING

.. toctree::
   :maxdepth: 2
   :caption: Auto-Generated:

   auto/CHANGELOG
   auto/ARCHITECTURE_AUTO
   auto/REPO_MAP
   auto/WORKFLOW_REGISTRY

Quick Start
-----------

.. code-block:: bash

   # Run with Docker
   docker run --gpus all \
     -v /path/to/models:/data/models \
     -e MODEL_NAME=your-model.gguf \
     -p 8000:8000 \
     ghcr.io/zepfu/llama-gguf-inference

Features
--------

* **OpenAI-compatible API** - Drop-in replacement
* **Authentication** - API key-based access control
* **Streaming support** - Real-time token streaming
* **Health monitoring** - Separate health check port
* **Platform agnostic** - Works anywhere Docker runs

API Reference
-------------

Gateway Module
~~~~~~~~~~~~~~

.. automodule:: gateway
   :members:
   :undoc-members:
   :show-inheritance:

Authentication Module
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: auth
   :members:
   :undoc-members:
   :show-inheritance:

Health Server Module
~~~~~~~~~~~~~~~~~~~~

.. automodule:: health_server
   :members:
   :undoc-members:
   :show-inheritance:

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
