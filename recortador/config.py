# -*- coding: utf-8 -*-
"""Valores por defecto y rutas de configuración de la aplicación."""

from __future__ import annotations

import os
import sys

MARGINS_TOP_DEFAULT = {"top": 260, "bottom": 350, "left": 50, "right": 55}
MARGINS_BOTTOM_DEFAULT = {"top": 280, "bottom": 400, "left": 80, "right": 10}

VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")
DEFAULT_OUTPUT_FOLDER_NAME = "Imagenes_pro"
DEFAULT_JPEG_QUALITY = 90
DEFAULT_PNG_COMPRESSION = 3

TIFF_COMPRESSION_OPTIONS = {
    1: "Ninguna",
    5: "LZW (Lossless)",
    8: "ZIP (Lossless)",
    7: "JPEG (Lossy)",
}
DEFAULT_TIFF_COMPRESSION_FLAG = 5
DEFAULT_TIFF_COMPRESSION_NAME = TIFF_COMPRESSION_OPTIONS[DEFAULT_TIFF_COMPRESSION_FLAG]

OUTPUT_FORMATS = {"JPEG (*.jpg)": ".jpg", "TIFF (*.tif)": ".tif"}
DEFAULT_OUTPUT_FORMAT_KEY = "JPEG (*.jpg)"

DEFAULT_TOP_IDENTIFIER = "Top"
DEFAULT_BOTTOM_IDENTIFIER = "Bottom"

CONFIG_FILE_NAME = "recortador_config.json"


def get_base_path() -> str:
    """Devuelve el directorio base, tanto en script como en ejecutable empaquetado."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CONFIG_FILE = os.path.join(get_base_path(), CONFIG_FILE_NAME)
