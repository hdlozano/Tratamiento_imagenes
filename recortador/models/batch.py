# -*- coding: utf-8 -*-
"""Procesamiento por lotes de carpetas de imágenes."""

from __future__ import annotations

import os
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Callable

from recortador.config import VALID_EXTENSIONS
from recortador.models.cropping import crop_image_with_margins

LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int, float], None]


@dataclass(frozen=True)
class BatchOptions:
    """Parámetros necesarios para ejecutar un lote."""

    input_dir: str
    output_dir: str
    margins_top: dict[str, int]
    margins_bottom: dict[str, int]
    compression_params: dict[str, int]
    output_ext: str
    top_identifier: str
    bottom_identifier: str


@dataclass
class BatchSummary:
    """Resumen de un procesamiento por lotes."""

    processed: int = 0
    skipped: int = 0
    errors: int = 0
    total: int = 0
    total_read_time: float = 0.0
    total_process_time: float = 0.0
    total_write_time: float = 0.0
    was_cancelled: bool = False
    fatal_error: str | None = None


def _is_inside(path: str, parent: str) -> bool:
    try:
        path_normalized = os.path.normcase(os.path.abspath(path))
        parent_normalized = os.path.normcase(os.path.abspath(parent))
        return os.path.commonpath([path_normalized, parent_normalized]) == parent_normalized
    except ValueError:
        return False


class BatchProcessor:
    """Recorre carpetas, selecciona márgenes y guarda las imágenes recortadas."""

    def run(
        self,
        options: BatchOptions,
        cancel_event: threading.Event,
        log: LogCallback,
        progress: ProgressCallback,
    ) -> BatchSummary:
        summary = BatchSummary()
        thread_start_time = time.perf_counter()
        files_to_process: list[str] = []

        log("Buscando archivos de imagen válidos (recursivamente)...\n")
        try:
            for current_dir_path, _, filenames in os.walk(options.input_dir):
                is_root_input = os.path.normcase(os.path.abspath(current_dir_path)) == os.path.normcase(
                    os.path.abspath(options.input_dir)
                )
                if not is_root_input and _is_inside(current_dir_path, options.output_dir):
                    log(f"  Omitiendo subdirectorio de salida: {current_dir_path}\n")
                    continue

                for filename in filenames:
                    if filename.lower().endswith(VALID_EXTENSIONS):
                        files_to_process.append(os.path.join(current_dir_path, filename))
        except OSError as error:
            message = f"Error fatal al buscar archivos en '{options.input_dir}': {error}"
            log(f"{message}\n")
            summary.fatal_error = message
            return summary

        summary.total = len(files_to_process)
        if not files_to_process:
            log("No se encontraron archivos de imagen con extensiones válidas en la carpeta de origen.\n")
            return summary

        log(f"Se encontraron {summary.total} archivos de imagen para procesar.\n")
        progress(0, summary.total, 0)

        file_index = 0
        try:
            for input_file_path in files_to_process:
                if cancel_event.is_set():
                    summary.was_cancelled = True
                    log(
                        "\n--- Cancelado por el usuario antes de procesar "
                        f"'{os.path.basename(input_file_path)}' ---\n"
                    )
                    break

                relative_path_dir = os.path.relpath(
                    os.path.dirname(input_file_path), options.input_dir
                )
                output_subdir = (
                    os.path.join(options.output_dir, relative_path_dir)
                    if relative_path_dir != "."
                    else options.output_dir
                )

                try:
                    if not os.path.exists(output_subdir):
                        os.makedirs(output_subdir, exist_ok=True)
                        log(f"  Directorio creado: {output_subdir}\n")
                except OSError as error:
                    log(
                        "!! Error Crítico: No se pudo crear el directorio de salida "
                        f"'{output_subdir}': {error}. Omitiendo archivo.\n"
                    )
                    summary.errors += 1
                    file_index += 1
                    elapsed = time.perf_counter() - thread_start_time
                    progress(file_index, summary.total, elapsed)
                    continue

                base_name, _ = os.path.splitext(os.path.basename(input_file_path))
                output_filename = base_name + options.output_ext
                output_file_path = os.path.normpath(
                    os.path.join(output_subdir, output_filename)
                )

                log_display_path_in = os.path.relpath(
                    input_file_path, options.input_dir
                )
                log_display_path_out = os.path.relpath(
                    output_file_path, os.path.dirname(options.output_dir)
                )

                log(
                    f"[{file_index + 1}/{summary.total}] Procesando: "
                    f"'{log_display_path_in}' -> '{log_display_path_out}'..."
                )

                filename_for_margins = os.path.basename(input_file_path)
                current_margins: dict[str, int] | None = None
                if options.top_identifier and options.top_identifier in filename_for_margins:
                    current_margins = options.margins_top
                    log(f" (ID: Frente ('{options.top_identifier}'))")
                elif (
                    options.bottom_identifier
                    and options.bottom_identifier in filename_for_margins
                ):
                    current_margins = options.margins_bottom
                    log(f" (ID: Reverso ('{options.bottom_identifier}'))")

                if current_margins is None:
                    log(" omitido (ningún identificador coincide).\n")
                    summary.skipped += 1
                else:
                    result = crop_image_with_margins(
                        input_file_path,
                        output_file_path,
                        current_margins,
                        options.compression_params,
                        log,
                    )
                    summary.total_read_time += result.read_time
                    summary.total_process_time += result.process_time
                    summary.total_write_time += result.write_time

                    if result.success:
                        summary.processed += 1
                        size_info = ""
                        try:
                            if os.path.exists(output_file_path):
                                input_size_bytes = os.path.getsize(input_file_path)
                                output_size_bytes = os.path.getsize(output_file_path)
                                output_size_kb = output_size_bytes / 1024
                                reduction = (
                                    100 * (1 - output_size_bytes / input_size_bytes)
                                    if input_size_bytes > 0
                                    else 0
                                )
                                size_info = (
                                    f" ({output_size_kb:.1f}kB, "
                                    f"Reducción: {reduction:.1f}%)"
                                )
                        except OSError as error:
                            size_info = f" (Error al obtener tamaño: {error.strerror})"
                        log(f" ¡OK!{size_info}\n")
                    else:
                        summary.errors += 1
                        log(" ¡ERROR! (ver detalles arriba)\n")

                file_index += 1
                elapsed = time.perf_counter() - thread_start_time
                progress(file_index, summary.total, elapsed)

        except Exception as error:
            summary.was_cancelled = cancel_event.is_set()
            log(f"\n!!! Error General Inesperado durante el Procesamiento: {error} !!!\n")
            log(f"Tipo de Error: {type(error).__name__}\n")
            log(f"Traceback: {traceback.format_exc()}\n")
            summary.fatal_error = str(error)

        return summary
