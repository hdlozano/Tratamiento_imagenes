# -*- coding: utf-8 -*-
"""Punto de arranque de la aplicación."""

from __future__ import annotations

import tkinter as tk

from recortador.config import CONFIG_FILE
from recortador.controllers.batch_controller import BatchController
from recortador.models.settings import SettingsStore


def main() -> None:
    root = tk.Tk()
    BatchController(root, SettingsStore(CONFIG_FILE))
    root.mainloop()
