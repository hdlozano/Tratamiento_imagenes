# -*- coding: utf-8 -*-
"""Controlador que coordina la vista y el procesamiento por lotes."""

from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from typing import Any, Callable

from recortador.config import (
    DEFAULT_JPEG_QUALITY,
    DEFAULT_PNG_COMPRESSION,
    DEFAULT_TIFF_COMPRESSION_FLAG,
    OUTPUT_FORMATS,
    TIFF_COMPRESSION_OPTIONS,
)
from recortador.models.batch import BatchOptions, BatchProcessor, BatchSummary
from recortador.models.settings import Settings, SettingsStore
from recortador.views.main_window import MainWindow


class BatchController:
    """Conecta los eventos de la vista con el modelo de procesamiento."""

    def __init__(self, root: tk.Tk, settings_store: SettingsStore) -> None:
        self.root = root
        self.settings_store = settings_store
        self.cancel_event = threading.Event()
        self._processing = False
        self._ui_queue: queue.Queue[tuple[Callable[..., Any], tuple[Any, ...]]] = (
            queue.Queue()
        )

        settings, load_message = self.settings_store.load()
        self.view = MainWindow(
            root=root,
            settings=settings.to_dict(),
            on_start=self.start_processing,
            on_cancel=self.cancel_processing,
            on_close=self.on_closing,
        )
        self.view.log(
            f"Intentando cargar configuración desde: {self.settings_store.path}\n"
        )
        self.view.log(f"{load_message}\n")
        self.root.after(50, self._drain_ui_queue)

    def start_processing(self) -> None:
        """Valida el formulario y lanza el procesamiento en un hilo separado."""
        if self._processing:
            return

        try:
            form = self.view.read_form()
        except ValueError as error:
            self.view.show_error("Error de Entrada", str(error))
            return

        input_dir = form["input_dir"]
        output_name = form["output_name"]
        output_dir = form["output_dir"]

        if not input_dir or not os.path.isdir(input_dir):
            self.view.show_warning(
                "Entrada Inválida",
                "Por favor, selecciona una carpeta de origen válida.",
            )
            return
        if not output_name:
            self.view.show_warning(
                "Entrada Requerida",
                "Por favor, introduce un nombre para la carpeta de salida.",
            )
            return
        if not output_dir or "<--" in output_dir:
            self.view.show_error(
                "Error de Configuración",
                "No se pudo determinar la ruta de la carpeta de salida. "
                "Verifica la carpeta de origen y el nombre de salida.",
            )
            return
        if os.path.normcase(os.path.abspath(output_dir)) == os.path.normcase(
            os.path.abspath(input_dir)
        ):
            if not self.view.ask_yes_no(
                "Confirmación",
                "La carpeta de salida es la misma que la de origen. Esto "
                "sobrescribirá archivos si los nombres coinciden. ¿Deseas continuar?",
            ):
                return

        margins_top = form["margins_top"]
        margins_bottom = form["margins_bottom"]
        for value in list(margins_top.values()) + list(margins_bottom.values()):
            if value < 0:
                self.view.show_error(
                    "Error de Entrada",
                    "Los márgenes no pueden ser negativos.",
                )
                return

        top_identifier = form["top_identifier"]
        bottom_identifier = form["bottom_identifier"]
        if not top_identifier and not bottom_identifier:
            self.view.show_warning(
                "Advertencia",
                "Debes proporcionar al menos un identificador ('Frente' o 'Reverso') "
                "para que el programa sepa qué márgenes aplicar.",
            )
            return

        output_format_key = form["output_format_key"]
        output_ext = OUTPUT_FORMATS.get(output_format_key, ".jpg")
        tiff_flag_map = {name: flag for flag, name in TIFF_COMPRESSION_OPTIONS.items()}
        tiff_compression_name = form["tiff_compression_name"]
        tiff_flag = tiff_flag_map.get(
            tiff_compression_name, DEFAULT_TIFF_COMPRESSION_FLAG
        )
        compression_params = {
            "jpeg_quality": form.get("jpeg_quality", DEFAULT_JPEG_QUALITY),
            "png_compression": form.get("png_compression", DEFAULT_PNG_COMPRESSION),
            "tiff_compression_flag": tiff_flag,
        }

        self._save_settings()
        self.view.clear_log()
        self.view.reset_progress()
        self.cancel_event.clear()

        self.view.log("\n--- Iniciando Proceso de Recorte ---\n")
        self.view.log(f"Carpeta Origen: {input_dir}\n")
        self.view.log(f"Carpeta Salida: {output_dir}\n")
        self.view.log(
            f"Identificador 'Frente' ('{top_identifier}'): Márgenes={margins_top}\n"
        )
        self.view.log(
            f"Identificador 'Reverso' ('{bottom_identifier}'): Márgenes={margins_bottom}\n"
        )
        self.view.log(f"Formato de Salida: {output_format_key}\n")
        self.view.log("Parámetros de Compresión:\n")
        self.view.log(
            f"  JPEG Calidad: {compression_params['jpeg_quality']} "
            "(Aplicable si salida=JPEG o TIFF/JPEG)\n"
        )
        self.view.log(
            f"  TIFF Esquema: {tiff_compression_name} (Flag={tiff_flag}) "
            "(Aplicable si salida=TIFF)\n"
        )

        options = BatchOptions(
            input_dir=input_dir,
            output_dir=output_dir,
            margins_top=margins_top,
            margins_bottom=margins_bottom,
            compression_params=compression_params,
            output_ext=output_ext,
            top_identifier=top_identifier,
            bottom_identifier=bottom_identifier,
        )

        self._processing = True
        processing_thread = threading.Thread(
            target=self._run_batch, args=(options,), daemon=True
        )
        processing_thread.start()

    def cancel_processing(self) -> None:
        """Solicita la cancelación del lote en curso."""
        if not self.cancel_event.is_set():
            self.view.log("--- Cancelación solicitada por el usuario ---\n")
            self.cancel_event.set()

    def _run_batch(self, options: BatchOptions) -> None:
        """Ejecuta el lote en el hilo de trabajo y programa las actualizaciones de UI."""
        thread_start_time = time.perf_counter()

        def thread_log(message: str) -> None:
            self._schedule_ui(self.view.log, message)

        def thread_progress(current: int, total: int, elapsed: float) -> None:
            self._schedule_ui(self.view.set_progress, current, total, elapsed)

        summary = BatchProcessor().run(
            options=options,
            cancel_event=self.cancel_event,
            log=thread_log,
            progress=thread_progress,
        )
        elapsed_time = time.perf_counter() - thread_start_time
        self._schedule_ui(self._finish_batch, summary, elapsed_time)

    def _finish_batch(self, summary: BatchSummary, elapsed_time: float) -> None:
        """Muestra el resumen final en la interfaz."""
        final_status = (
            "--- Proceso Cancelado ---\n"
            if summary.was_cancelled
            else "--- Proceso Finalizado ---\n"
        )
        self.view.log(f"\n{final_status}")
        self.view.log("Resumen:\n")
        self.view.log(f"  - Archivos Procesados Correctamente: {summary.processed}\n")
        self.view.log(
            f"  - Archivos Omitidos (sin identificador): {summary.skipped}\n"
        )
        self.view.log(f"  - Archivos con Errores: {summary.errors}\n")
        self.view.log(f"  - Total Archivos Encontrados: {summary.total}\n")

        if summary.processed > 0:
            self.view.log("Tiempos Promedio por Archivo Procesado (segundos):\n")
            self.view.log(
                f"  - Lectura: {summary.total_read_time / summary.processed:.3f}\n"
            )
            self.view.log(
                "  - Procesamiento (recorte/conversión): "
                f"{summary.total_process_time / summary.processed:.3f}\n"
            )
            self.view.log(
                f"  - Escritura: {summary.total_write_time / summary.processed:.3f}\n"
            )

        if summary.fatal_error:
            self.view.show_error(
                "Error en Procesamiento",
                f"Ocurrió un error inesperado:\n{summary.fatal_error}\n\n"
                "Consulte el registro para más detalles.",
            )

        self.view.finish_progress(elapsed_time, summary.was_cancelled)
        self._processing = False

    def _save_settings(self) -> None:
        try:
            settings_data = self.view.collect_settings()
            settings = Settings.from_dict(settings_data)
            self.settings_store.save(settings)
            self.view.log(
                f"Configuración guardada correctamente en: {self.settings_store.path}\n"
            )
        except Exception as error:
            self.view.log(
                f"Error al guardar configuración en '{self.settings_store.path}': "
                f"{error}\n"
            )

    def on_closing(self) -> None:
        """Guarda la configuración y cierra la ventana."""
        self._save_settings()
        self.root.destroy()

    def _schedule_ui(self, callback: Callable[..., Any], *args: Any) -> None:
        """Encola una actualización para que la ejecute el hilo principal de Tk."""
        self._ui_queue.put((callback, args))

    def _drain_ui_queue(self) -> None:
        """Ejecuta en el hilo de Tk las actualizaciones enviadas por el trabajador."""
        try:
            while True:
                callback, args = self._ui_queue.get_nowait()
                try:
                    callback(*args)
                except Exception:
                    pass
        except queue.Empty:
            pass

        try:
            if self.root and self.root.winfo_exists():
                self.root.after(50, self._drain_ui_queue)
        except tk.TclError:
            pass
