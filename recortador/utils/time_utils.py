# -*- coding: utf-8 -*-
"""Utilidades de formato de tiempo."""

from __future__ import annotations

import math


def format_time(seconds: float) -> str:
    """Formatea una cantidad de segundos como mm:ss o h:mm:ss."""
    if seconds < 0:
        seconds = 0
    seconds = math.floor(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
