"""Tickets (spec 6.2). Importing the package registers what messaging reads of tickets
(`hooks.py`, review M4 P9)."""

from app.modules.tickets.hooks import register

register()
