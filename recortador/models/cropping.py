# -*- coding: utf-8 -*-
"""Lógica de recorte, conversión y guardado de imágenes con OpenCV."""

from __future__ import annotations

import os
import time
import traceback
from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np

from recortador.config import (
    DEFAULT_JPEG_QUALITY,
    DEFAULT_PNG_COMPRESSION,
    DEFAULT_TIFF_COMPRESSION_FLAG,
    TIFF_COMPRESSION_OPTIONS,
)

LogCallback = Callable[[str], None]


@dataclass(frozen=True)
class CropResult:
    """Resultado de procesar una imagen."""

    success: bool
    read_time: float = 0.0
    process_time: float = 0.0
    write_time: float = 0.0


def convert_to_bgr_uint8(
    image: np.ndarray, format_name: str
) -> tuple[np.ndarray | None, str]:
    """Convierte la imagen a BGR uint8 si es necesario para JPG, BMP o TIFF/JPEG."""
    logs = ""
    current_dtype = image.dtype
    current_channels = image.shape[2] if len(image.shape) > 2 else 1
    temp_image = image

    if current_dtype != np.uint8:
        logs += f"    Advertencia: Convirtiendo {current_dtype} a uint8 para {format_name}.\n"
        if current_dtype == np.uint16:
            temp_image = (image / 257.0).astype(np.uint8)
            logs += "      (Asumiendo rango 16-bit completo)\n"
        elif current_dtype in [np.float32, np.float64]:
            logs += "      (Asumiendo rango flotante 0.0-1.0)\n"
            temp_image_clipped = np.clip(image, 0.0, 1.0)
            temp_image = (temp_image_clipped * 255.0).astype(np.uint8)
        elif np.issubdtype(current_dtype, np.integer):
            logs += "      (Clipping a rango 0-255)\n"
            temp_image_clipped = np.clip(image, 0, 255)
            temp_image = temp_image_clipped.astype(np.uint8)
        else:
            try:
                logs += f"      (Intentando conversión directa desde {current_dtype})\n"
                temp_image = image.astype(np.uint8)
                if np.issubdtype(current_dtype, np.bool_):
                    temp_image = temp_image * 255
            except Exception as conversion_error:
                logs += (
                    f"    Error crítico convirtiendo {current_dtype} a uint8: "
                    f"{conversion_error}.\n"
                )
                return None, logs
        current_channels = temp_image.shape[2] if len(temp_image.shape) > 2 else 1

    if current_channels == 4:
        logs += f"    Advertencia: Eliminando canal Alfa para {format_name}.\n"
        image_converted = cv2.cvtColor(temp_image, cv2.COLOR_BGRA2BGR)
    elif current_channels == 1:
        image_converted = cv2.cvtColor(temp_image, cv2.COLOR_GRAY2BGR)
    elif current_channels == 3:
        image_converted = temp_image
    else:
        logs += (
            f"    Error: Número de canales ({current_channels}) no soportado para "
            f"conversión a BGR para {format_name}.\n"
        )
        return None, logs

    return image_converted, logs


def crop_image_with_margins(
    image_path: str,
    output_path: str,
    margins: dict[str, int],
    compression_params: dict[str, int],
    log_callback: LogCallback,
) -> CropResult:
    """Recorta una imagen y la guarda en el formato indicado por la extensión."""
    t_start_read = time.perf_counter()
    image_to_save = None
    t_end_read = t_start_read
    t_start_process = t_start_read
    t_end_process = t_start_read
    t_start_write = t_start_read
    t_end_write = t_start_read

    try:
        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            log_callback(f"  Error carga: {os.path.basename(image_path)}\n")
            return CropResult(False)

        t_end_read = time.perf_counter()
        t_start_process = time.perf_counter()
        img_h, img_w = image.shape[:2]
        margin_top = margins.get("top", 0)
        margin_bottom = margins.get("bottom", 0)
        margin_left = margins.get("left", 0)
        margin_right = margins.get("right", 0)
        y_start, y_end = margin_top, img_h - margin_bottom
        x_start, x_end = margin_left, img_w - margin_right

        if y_start >= y_end or x_start >= x_end:
            log_callback(
                f"  Error márgenes: '{os.path.basename(image_path)}'. "
                f"Alto={y_end - y_start}, Ancho={x_end - x_start}. Se omite.\n"
            )
            t_end_process = time.perf_counter()
            return CropResult(
                False,
                read_time=t_end_read - t_start_read,
                process_time=t_end_process - t_start_process,
            )

        y_start = max(0, y_start)
        y_end = min(img_h, y_end)
        x_start = max(0, x_start)
        x_end = min(img_w, x_end)
        cropped_image = image[y_start:y_end, x_start:x_end]
        image_to_save = cropped_image
        t_end_process = time.perf_counter()

        output_dir_path = os.path.dirname(output_path)
        if output_dir_path:
            os.makedirs(output_dir_path, exist_ok=True)

        t_start_write = time.perf_counter()
        write_params: list[int] = []
        file_ext = os.path.splitext(output_path)[1].lower()
        log_prefix = (
            f"  Guardando {os.path.basename(output_path)} como "
            f"{file_ext.upper()} con: "
        )
        original_dtype = cropped_image.dtype

        if file_ext in [".jpg", ".jpeg"]:
            quality = compression_params.get("jpeg_quality", DEFAULT_JPEG_QUALITY)
            write_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
            log_callback(f"{log_prefix}JPEG Calidad={quality}\n")
            temp_image, conversion_log = convert_to_bgr_uint8(cropped_image, "JPEG")
            if conversion_log:
                log_callback(conversion_log)
            if temp_image is None:
                return CropResult(
                    False,
                    read_time=t_end_read - t_start_read,
                    process_time=t_end_process - t_start_process,
                )
            image_to_save = temp_image

        elif file_ext == ".png":
            level = compression_params.get("png_compression", DEFAULT_PNG_COMPRESSION)
            write_params = [cv2.IMWRITE_PNG_COMPRESSION, level]
            log_callback(f"{log_prefix}PNG Compresión={level}\n")
            image_to_save = cropped_image

        elif file_ext in [".tif", ".tiff"]:
            tiff_flag = compression_params.get(
                "tiff_compression_flag", DEFAULT_TIFF_COMPRESSION_FLAG
            )
            write_params = [cv2.IMWRITE_TIFF_COMPRESSION, tiff_flag]
            tiff_option_name = TIFF_COMPRESSION_OPTIONS.get(
                tiff_flag, f"Desconocido ({tiff_flag})"
            )
            log_callback(f"{log_prefix}TIFF Compresión={tiff_option_name}")

            if tiff_flag == 7:
                quality = compression_params.get("jpeg_quality", DEFAULT_JPEG_QUALITY)
                write_params.extend([cv2.IMWRITE_JPEG_QUALITY, quality])
                log_callback(f" (Calidad={quality})\n")
                temp_image, conversion_log = convert_to_bgr_uint8(
                    cropped_image, "JPEG en TIFF"
                )
                if conversion_log:
                    log_callback(conversion_log)
                if temp_image is None:
                    return CropResult(
                        False,
                        read_time=t_end_read - t_start_read,
                        process_time=t_end_process - t_start_process,
                    )
                image_to_save = temp_image
            else:
                log_callback("\n")
                current_dtype = cropped_image.dtype
                temp_image = cropped_image
                if current_dtype in [np.float32, np.float64]:
                    log_callback(
                        f"    Advertencia: Convirtiendo {current_dtype} a uint16 para "
                        "TIFF sin pérdida (asume rango 0-1).\n"
                    )
                    temp_image_clipped = np.clip(temp_image, 0.0, 1.0)
                    image_to_save = (temp_image_clipped * 65535.0).astype(np.uint16)
                elif current_dtype == np.uint16:
                    image_to_save = temp_image
                elif current_dtype == np.uint8:
                    image_to_save = temp_image
                else:
                    log_callback(
                        f"    Advertencia: Convirtiendo tipo no estándar "
                        f"{current_dtype} a uint8 para TIFF sin pérdida.\n"
                    )
                    try:
                        if np.issubdtype(current_dtype, np.integer):
                            min_val = np.iinfo(current_dtype).min
                            max_val = np.iinfo(current_dtype).max
                            if min_val < 0 or max_val > 255:
                                temp_image_clipped = np.clip(temp_image, 0, 255)
                                image_to_save = temp_image_clipped.astype(np.uint8)
                                log_callback(
                                    "      (Valores fuera de 0-255 detectados, se hizo "
                                    "clipping a uint8)\n"
                                )
                            else:
                                image_to_save = temp_image.astype(np.uint8)
                        elif np.issubdtype(current_dtype, np.bool_):
                            image_to_save = temp_image.astype(np.uint8) * 255
                        else:
                            log_callback(
                                f"      Tipo {current_dtype} no manejado específicamente, "
                                "intentando conversión directa a uint8.\n"
                            )
                            image_to_save = temp_image.astype(np.uint8)
                    except Exception as conversion_error:
                        log_callback(
                            f"    Error crítico convirtiendo {current_dtype} a uint8: "
                            f"{conversion_error}. Omitiendo guardado.\n"
                        )
                        return CropResult(
                            False,
                            read_time=t_end_read - t_start_read,
                            process_time=t_end_process - t_start_process,
                        )

        elif file_ext == ".bmp":
            log_callback(f"{log_prefix}BMP (sin compresión)\n")
            temp_image, conversion_log = convert_to_bgr_uint8(cropped_image, "BMP")
            if conversion_log:
                log_callback(conversion_log)
            if temp_image is None:
                return CropResult(
                    False,
                    read_time=t_end_read - t_start_read,
                    process_time=t_end_process - t_start_process,
                )
            image_to_save = temp_image

        if image_to_save is None:
            log_callback(
                f"    Error: No se pudo preparar imagen para guardar "
                f"({os.path.basename(output_path)}). Tipo original: {original_dtype}. "
                "Omitiendo.\n"
            )
            return CropResult(
                False,
                read_time=t_end_read - t_start_read,
                process_time=t_end_process - t_start_process,
            )

        success = cv2.imwrite(output_path, image_to_save, write_params)
        t_end_write = time.perf_counter()

        if success:
            return CropResult(
                True,
                read_time=t_end_read - t_start_read,
                process_time=t_end_process - t_start_process,
                write_time=t_end_write - t_start_write,
            )

        log_callback(
            f"  Fallo cv2.imwrite para: {os.path.basename(output_path)} "
            f"(verificar permisos, espacio, formato compatible con tipo de dato: "
            f"{image_to_save.dtype})\n"
        )
        return CropResult(
            False,
            read_time=t_end_read - t_start_read,
            process_time=t_end_process - t_start_process,
            write_time=t_end_write - t_start_write,
        )

    except Exception as error:
        t_now = time.perf_counter()
        log_callback(
            f"!! Excepción interna en crop_image_with_margins para "
            f"{os.path.basename(image_path)}: {error}\n"
        )
        log_callback(f"   Tipo Excepción: {type(error).__name__}\n")
        log_callback(f"   Traceback: {traceback.format_exc()}\n")
        t_read = t_end_read - t_start_read if t_end_read != t_start_read else t_now - t_start_read
        t_proc = t_end_process - t_start_process if t_end_process != t_start_process else 0.0
        t_write = t_end_write - t_start_write if t_end_write != t_start_write else 0.0
        return CropResult(False, t_read, t_proc, t_write)
