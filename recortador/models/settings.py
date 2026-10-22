# -*- coding: utf-8 -*-
"""Modelo y persistencia de la configuración de la aplicación."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from recortador.config import (
    DEFAULT_BOTTOM_IDENTIFIER,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_OUTPUT_FOLDER_NAME,
    DEFAULT_OUTPUT_FORMAT_KEY,
    DEFAULT_TIFF_COMPRESSION_NAME,
    DEFAULT_TOP_IDENTIFIER,
    MARGINS_BOTTOM_DEFAULT,
    MARGINS_TOP_DEFAULT,
)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, default: str) -> str:
    if value is None:
        return default
    return str(value)


def _read_margins(value: Any, default: dict[str, int]) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    return {
        key: _safe_int(source.get(key, default_value), default_value)
        for key, default_value in default.items()
    }


@dataclass
class Settings:
    """Configuración completa de la aplicación."""

    output_folder_name: str = DEFAULT_OUTPUT_FOLDER_NAME
    jpeg_quality: int = DEFAULT_JPEG_QUALITY
    output_format_key: str = DEFAULT_OUTPUT_FORMAT_KEY
    top_identifier: str = DEFAULT_TOP_IDENTIFIER
    bottom_identifier: str = DEFAULT_BOTTOM_IDENTIFIER
    tiff_compression_name: str = DEFAULT_TIFF_COMPRESSION_NAME
    margins_top: dict[str, int] = field(default_factory=lambda: dict(MARGINS_TOP_DEFAULT))
    margins_bottom: dict[str, int] = field(default_factory=lambda: dict(MARGINS_BOTTOM_DEFAULT))
    last_input_folder: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        """Construye la configuración desde el JSON, aplicando valores por defecto."""
        return cls(
            output_folder_name=_safe_str(
                data.get("output_folder_name"), DEFAULT_OUTPUT_FOLDER_NAME
            ),
            jpeg_quality=_safe_int(
                data.get("jpeg_quality"), DEFAULT_JPEG_QUALITY
            ),
            output_format_key=_safe_str(
                data.get("output_format_key"), DEFAULT_OUTPUT_FORMAT_KEY
            ),
            top_identifier=_safe_str(
                data.get("top_identifier"), DEFAULT_TOP_IDENTIFIER
            ),
            bottom_identifier=_safe_str(
                data.get("bottom_identifier"), DEFAULT_BOTTOM_IDENTIFIER
            ),
            tiff_compression_name=_safe_str(
                data.get("tiff_compression_name"), DEFAULT_TIFF_COMPRESSION_NAME
            ),
            margins_top=_read_margins(
                data.get("margins_top"), MARGINS_TOP_DEFAULT
            ),
            margins_bottom=_read_margins(
                data.get("margins_bottom"), MARGINS_BOTTOM_DEFAULT
            ),
            last_input_folder=_safe_str(data.get("last_input_folder"), ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Devuelve la configuración con el mismo esquema usado por la app anterior."""
        return {
            "output_folder_name": self.output_folder_name,
            "jpeg_quality": self.jpeg_quality,
            "output_format_key": self.output_format_key,
            "top_identifier": self.top_identifier,
            "bottom_identifier": self.bottom_identifier,
            "tiff_compression_name": self.tiff_compression_name,
            "margins_top": dict(self.margins_top),
            "margins_bottom": dict(self.margins_bottom),
            "last_input_folder": self.last_input_folder,
        }


class SettingsStore:
    """Carga y guarda la configuración en un archivo JSON."""

    def __init__(self, path: str) -> None:
        self.path = path

    def load(self) -> tuple[Settings, str]:
        """Carga la configuración y devuelve un mensaje para el registro."""
        if not os.path.exists(self.path):
            return (
                Settings(),
                f"Archivo de configuración no encontrado en '{self.path}'. "
                "Usando valores por defecto.",
            )

        try:
            with open(self.path, "r", encoding="utf-8") as config_file:
                data = json.load(config_file)
            if not isinstance(data, dict):
                raise ValueError("El contenido del archivo no es un objeto JSON.")
            return (
                Settings.from_dict(data),
                "Configuración anterior cargada correctamente.",
            )
        except json.JSONDecodeError as error:
            return (
                Settings(),
                f"Error al leer el archivo de configuración JSON: {error}. "
                "Usando valores por defecto.",
            )
        except Exception as error:
            return (
                Settings(),
                f"Error inesperado al cargar la configuración: {error}. "
                "Usando valores por defecto.",
            )

    def save(self, settings: Settings) -> None:
        """Guarda la configuración, creando el directorio si es necesario."""
        config_dir = os.path.dirname(self.path)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as config_file:
            json.dump(settings.to_dict(), config_file, indent=4, ensure_ascii=False)
