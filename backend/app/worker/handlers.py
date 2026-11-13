"""Every module that registers outbox handlers. Importing this module registers them
all in `registry.REGISTRY`; the worker does so before it starts (`main.py`)."""

import app.modules.messaging.handlers  # noqa: F401 -- notify_on_message, publish_live
