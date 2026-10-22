# -*- coding: utf-8 -*-
"""Vista Tkinter de la aplicación. Solo construye widgets y expone su estado."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Spinbox, ttk
from typing import Any, Callable

from recortador.config import (
    DEFAULT_BOTTOM_IDENTIFIER,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_OUTPUT_FOLDER_NAME,
    DEFAULT_OUTPUT_FORMAT_KEY,
    DEFAULT_PNG_COMPRESSION,
    DEFAULT_TIFF_COMPRESSION_NAME,
    DEFAULT_TOP_IDENTIFIER,
    MARGINS_BOTTOM_DEFAULT,
    MARGINS_TOP_DEFAULT,
    OUTPUT_FORMATS,
    TIFF_COMPRESSION_OPTIONS,
)
from recortador.utils.time_utils import format_time


class MainWindow:
    """Ventana principal de la aplicación."""

    def __init__(
        self,
        root: tk.Tk,
        settings: dict[str, Any],
        on_start: Callable[[], None],
        on_cancel: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self.root = root
        self.on_start = on_start
        self.on_cancel = on_cancel
        self.on_close = on_close

        self.root.title("Recortador de Imágenes v1.1")
        self.root.geometry("800x710")

        self.input_folder_path = tk.StringVar()
        self.output_folder_path = tk.StringVar()
        self.output_folder_name_var = tk.StringVar(value=DEFAULT_OUTPUT_FOLDER_NAME)
        self.jpeg_quality_var = tk.IntVar(value=DEFAULT_JPEG_QUALITY)
        self.png_compression_var = tk.IntVar(value=DEFAULT_PNG_COMPRESSION)
        self.tiff_compression_var = tk.StringVar(value=DEFAULT_TIFF_COMPRESSION_NAME)
        self.output_format_var = tk.StringVar(value=DEFAULT_OUTPUT_FORMAT_KEY)
        self.top_identifier_var = tk.StringVar(value=DEFAULT_TOP_IDENTIFIER)
        self.bottom_identifier_var = tk.StringVar(value=DEFAULT_BOTTOM_IDENTIFIER)
        self.margins_top_vars = {
            key: tk.IntVar(value=value) for key, value in MARGINS_TOP_DEFAULT.items()
        }
        self.margins_bottom_vars = {
            key: tk.IntVar(value=value) for key, value in MARGINS_BOTTOM_DEFAULT.items()
        }

        self.progress_var = tk.DoubleVar(value=0.0)
        self.etr_var = tk.StringVar(value="Restante: --:--")
        self.progress_percent_var = tk.StringVar(value="0%")
        self.elapsed_time_var = tk.StringVar(value="Transcurrido: 00:00")

        self._build_ui()
        self.apply_settings(settings)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_output_path_display()

    # --- Construcción de la interfaz ---
    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.configure("Progress.TLabel", foreground="black", anchor=tk.CENTER)
        try:
            style.configure(
                "Progress.TLabel",
                background=style.lookup("TProgressbar", "troughcolor"),
            )
        except tk.TclError:
            style.configure("Progress.TLabel", background="lightgrey")

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)

        top_frame = ttk.LabelFrame(
            main_frame, text="Configuración Principal", padding="10"
        )
        top_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 10))
        top_frame.columnconfigure(1, weight=1)
        top_frame.columnconfigure(2, weight=0)

        ttk.Button(
            top_frame,
            text="Seleccionar Carpeta Origen",
            command=self.select_input_folder,
        ).grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Label(
            top_frame, textvariable=self.input_folder_path, wraplength=380, anchor="w"
        ).grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        ttk.Label(top_frame, text="Nombre Carpeta Salida:").grid(
            row=1, column=0, padx=5, pady=2, sticky="w"
        )
        self.output_name_entry = ttk.Entry(
            top_frame, textvariable=self.output_folder_name_var, width=30
        )
        self.output_name_entry.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.output_folder_name_var.trace_add("write", self.update_output_path_display)

        ttk.Label(top_frame, text="Ruta Carpeta Salida:").grid(
            row=2, column=0, padx=5, pady=2, sticky="w"
        )
        ttk.Label(
            top_frame,
            textvariable=self.output_folder_path,
            wraplength=380,
            foreground="grey",
            anchor="w",
        ).grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        button_frame = ttk.Frame(top_frame)
        button_frame.grid(row=0, column=2, rowspan=3, padx=(10, 5), pady=5, sticky="ns")
        self.start_button = ttk.Button(
            button_frame, text="Iniciar", command=self.on_start, width=10
        )
        self.start_button.pack(pady=5, fill=tk.X)
        self.cancel_button = ttk.Button(
            button_frame,
            text="Cancelar",
            command=self._handle_cancel,
            width=10,
            state=tk.DISABLED,
        )
        self.cancel_button.pack(pady=5, fill=tk.X)

        margins_frame = ttk.LabelFrame(
            main_frame, text="Identificadores y Márgenes (px)", padding="10"
        )
        margins_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        margins_frame.columnconfigure(1, weight=1)
        margins_frame.columnconfigure(3, weight=1)

        ttk.Label(margins_frame, text="Identificador 'Frente':").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.top_id_entry = ttk.Entry(
            margins_frame, textvariable=self.top_identifier_var, width=20
        )
        self.top_id_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(margins_frame, text="Identificador 'Reverso':").grid(
            row=0, column=2, padx=(15, 5), pady=5, sticky="w"
        )
        self.bottom_id_entry = ttk.Entry(
            margins_frame, textvariable=self.bottom_identifier_var, width=20
        )
        self.bottom_id_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        ttk.Label(
            margins_frame,
            text="Márgenes para Identificador 'Frente':",
            font="-weight bold",
        ).grid(row=2, column=0, columnspan=4, padx=5, pady=(10, 2), sticky="w")
        self.spinboxes_top_widgets = self.create_margin_spinboxes_inline(
            margins_frame, self.margins_top_vars, target_row=3
        )

        ttk.Label(
            margins_frame,
            text="Márgenes para Identificador 'Reverso':",
            font="-weight bold",
        ).grid(row=4, column=0, columnspan=4, padx=5, pady=(10, 2), sticky="w")
        self.spinboxes_bottom_widgets = self.create_margin_spinboxes_inline(
            margins_frame, self.margins_bottom_vars, target_row=5
        )

        format_comp_frame = ttk.LabelFrame(
            main_frame, text="Formato Salida y Compresión", padding="10"
        )
        format_comp_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        format_comp_frame.columnconfigure(1, weight=1)
        format_comp_frame.columnconfigure(4, weight=1)

        ttk.Label(format_comp_frame, text="Formato Salida:").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.output_format_combo = ttk.Combobox(
            format_comp_frame,
            textvariable=self.output_format_var,
            values=list(OUTPUT_FORMATS.keys()),
            state="readonly",
            width=15,
        )
        self.output_format_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(format_comp_frame, text="JPEG Calidad (0-100):").grid(
            row=1, column=0, padx=5, pady=5, sticky="w"
        )
        self.jpeg_quality_slider = ttk.Scale(
            format_comp_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.jpeg_quality_var,
            command=lambda value: self.jpeg_quality_var.set(int(float(value))),
            length=150,
        )
        self.jpeg_quality_slider.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.jpeg_quality_label = ttk.Label(
            format_comp_frame, textvariable=self.jpeg_quality_var, width=4
        )
        self.jpeg_quality_label.grid(row=1, column=2, padx=(0, 15), pady=5, sticky="w")

        ttk.Label(format_comp_frame, text="TIFF Compresión:").grid(
            row=1, column=3, padx=(15, 5), pady=5, sticky="w"
        )
        self.tiff_compression_combo = ttk.Combobox(
            format_comp_frame,
            textvariable=self.tiff_compression_var,
            values=list(TIFF_COMPRESSION_OPTIONS.values()),
            state="readonly",
            width=18,
        )
        self.tiff_compression_combo.grid(
            row=1, column=4, columnspan=2, padx=5, pady=5, sticky="w"
        )

        progress_frame = ttk.Frame(main_frame, padding=(5, 0, 5, 5))
        progress_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(10, 0))
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.columnconfigure(1, weight=0)
        progress_frame.columnconfigure(2, weight=0)

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            length=100,
            mode="determinate",
            variable=self.progress_var,
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.progress_percent_label = ttk.Label(
            progress_frame, textvariable=self.progress_percent_var, style="Progress.TLabel"
        )
        self.progress_percent_label.place(
            in_=self.progress_bar, relx=0.5, rely=0.5, anchor=tk.CENTER
        )
        self.progress_percent_label.lift()

        self.elapsed_label = ttk.Label(
            progress_frame, textvariable=self.elapsed_time_var, width=20, anchor="w"
        )
        self.elapsed_label.grid(row=0, column=1, sticky="w", padx=(0, 10))

        self.etr_label = ttk.Label(
            progress_frame, textvariable=self.etr_var, width=18, anchor="e"
        )
        self.etr_label.grid(row=0, column=2, sticky="e")

        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=5, pady=(5, 5))
        main_frame.rowconfigure(4, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)

        ttk.Label(log_frame, text="Registro de Proceso:").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        self.log_area = scrolledtext.ScrolledText(
            log_frame, height=10, wrap=tk.WORD, state=tk.DISABLED
        )
        self.log_area.grid(row=1, column=0, sticky="nsew")

    def create_margin_spinboxes_inline(
        self, parent_frame: ttk.Frame, margin_vars_dict: dict[str, tk.IntVar], target_row: int
    ) -> dict[str, Spinbox]:
        """Crea los spinboxes de márgenes en una fila."""
        spinboxes_widgets: dict[str, Spinbox] = {}
        keys_order = ["top", "bottom", "left", "right"]
        labels_text = {
            "top": "Arriba:",
            "bottom": "Abajo:",
            "left": "Izquierda:",
            "right": "Derecha:",
        }
        current_col = 0

        for index, key in enumerate(keys_order):
            label_col = current_col
            ttk.Label(parent_frame, text=labels_text[key]).grid(
                row=target_row,
                column=label_col,
                padx=(5 if index > 0 else 0, 2),
                pady=1,
                sticky="e",
            )
            current_col += 1

            spinbox_col = current_col
            spinbox_var = margin_vars_dict.get(key)
            if spinbox_var:
                spinbox = Spinbox(
                    parent_frame,
                    from_=0,
                    to=9999,
                    increment=1,
                    textvariable=spinbox_var,
                    width=6,
                )
                spinbox.grid(
                    row=target_row, column=spinbox_col, padx=(0, 10), pady=1, sticky="w"
                )
                spinboxes_widgets[key] = spinbox
                parent_frame.columnconfigure(spinbox_col, weight=1)
            current_col += 1

        return spinboxes_widgets

    # --- Estado del formulario ---
    def apply_settings(self, settings: dict[str, Any]) -> None:
        self.output_folder_name_var.set(
            settings.get("output_folder_name", DEFAULT_OUTPUT_FOLDER_NAME)
        )
        self.jpeg_quality_var.set(
            settings.get("jpeg_quality", DEFAULT_JPEG_QUALITY)
        )
        self.output_format_var.set(
            settings.get("output_format_key", DEFAULT_OUTPUT_FORMAT_KEY)
        )
        self.top_identifier_var.set(
            settings.get("top_identifier", DEFAULT_TOP_IDENTIFIER)
        )
        self.bottom_identifier_var.set(
            settings.get("bottom_identifier", DEFAULT_BOTTOM_IDENTIFIER)
        )

        saved_tiff_name = settings.get(
            "tiff_compression_name", DEFAULT_TIFF_COMPRESSION_NAME
        )
        if saved_tiff_name in TIFF_COMPRESSION_OPTIONS.values():
            self.tiff_compression_var.set(saved_tiff_name)
        else:
            self.tiff_compression_var.set(DEFAULT_TIFF_COMPRESSION_NAME)

        margins_top = settings.get("margins_top", MARGINS_TOP_DEFAULT)
        margins_bottom = settings.get("margins_bottom", MARGINS_BOTTOM_DEFAULT)
        for key, variable in self.margins_top_vars.items():
            variable.set(margins_top.get(key, MARGINS_TOP_DEFAULT.get(key, 0)))
        for key, variable in self.margins_bottom_vars.items():
            variable.set(margins_bottom.get(key, MARGINS_BOTTOM_DEFAULT.get(key, 0)))

        self.input_folder_path.set(settings.get("last_input_folder", ""))
        self.update_output_path_display()

    def read_form(self) -> dict[str, Any]:
        """Devuelve los valores actuales del formulario sin lógica de negocio."""
        try:
            margins_top = {
                key: int(variable.get())
                for key, variable in self.margins_top_vars.items()
            }
            margins_bottom = {
                key: int(variable.get())
                for key, variable in self.margins_bottom_vars.items()
            }
            return {
                "input_dir": self.input_folder_path.get().strip(),
                "output_name": self.output_folder_name_var.get().strip(),
                "output_dir": self.output_folder_path.get(),
                "margins_top": margins_top,
                "margins_bottom": margins_bottom,
                "jpeg_quality": int(self.jpeg_quality_var.get()),
                "png_compression": int(self.png_compression_var.get()),
                "output_format_key": self.output_format_var.get(),
                "tiff_compression_name": self.tiff_compression_var.get(),
                "top_identifier": self.top_identifier_var.get().strip(),
                "bottom_identifier": self.bottom_identifier_var.get().strip(),
            }
        except (tk.TclError, ValueError) as error:
            raise ValueError(f"Valor inválido en el formulario: {error}") from error

    def collect_settings(self) -> dict[str, Any]:
        """Devuelve los valores que deben persistirse en el JSON."""
        form = self.read_form()
        return {
            "output_folder_name": form["output_name"],
            "jpeg_quality": form["jpeg_quality"],
            "output_format_key": form["output_format_key"],
            "top_identifier": form["top_identifier"],
            "bottom_identifier": form["bottom_identifier"],
            "tiff_compression_name": form["tiff_compression_name"],
            "margins_top": form["margins_top"],
            "margins_bottom": form["margins_bottom"],
            "last_input_folder": form["input_dir"],
        }

    # --- Eventos de la vista ---
    def select_input_folder(self) -> None:
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.input_folder_path.set(folder_selected)
            self.log(f"Carpeta Origen seleccionada: {folder_selected}\n")
            self.update_output_path_display()

    def update_output_path_display(self, *_: Any) -> None:
        input_dir = self.input_folder_path.get()
        output_name = self.output_folder_name_var.get().strip()
        parent_dir = (
            os.path.dirname(input_dir)
            if input_dir and os.path.isdir(input_dir)
            else None
        )

        if parent_dir and output_name:
            self.output_folder_path.set(os.path.join(parent_dir, output_name))
        elif input_dir:
            self.output_folder_path.set(
                f"<-- Falta Nombre Carpeta Salida (se creará en {os.path.dirname(input_dir)})"
            )
        else:
            self.output_folder_path.set("")

    def _handle_cancel(self) -> None:
        self.cancel_button.config(state=tk.DISABLED)
        self.on_cancel()

    # --- Actualización de la interfaz ---
    def log(self, message: str) -> None:
        if not self._window_alive():
            return
        try:
            self.log_area.config(state=tk.NORMAL)
            self.log_area.insert(tk.END, message)
            self.log_area.see(tk.END)
            self.log_area.config(state=tk.DISABLED)
        except tk.TclError:
            pass

    def clear_log(self) -> None:
        if not self._window_alive():
            return
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete("1.0", tk.END)
        self.log_area.config(state=tk.DISABLED)

    def reset_progress(self) -> None:
        self.progress_var.set(0.0)
        self.progress_percent_var.set("0%")
        self.elapsed_time_var.set("Transcurrido: 00:00")
        self.etr_var.set("Restante: Calculando...")
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.root.update_idletasks()

    def set_progress(self, current_value: int, total_value: int, elapsed_time: float) -> None:
        if total_value == 0 or not self._window_alive():
            return

        progress_percent = (current_value / total_value) * 100
        self.progress_var.set(progress_percent)
        self.progress_percent_var.set(f"{progress_percent:.0f}%")
        self.elapsed_time_var.set(f"Transcurrido: {format_time(elapsed_time)}")

        if 0 < current_value < total_value:
            time_per_item = elapsed_time / current_value
            remaining_items = total_value - current_value
            self.etr_var.set(f"Restante: {format_time(time_per_item * remaining_items)}")
        elif current_value == 0:
            self.etr_var.set("Restante: Calculando...")
        else:
            self.etr_var.set("Restante: 00:00")

    def finish_progress(self, elapsed_time: float, was_cancelled: bool) -> None:
        if not self._window_alive():
            return
        status_message = "Cancelado" if was_cancelled else "Completado"
        if not was_cancelled:
            self.progress_var.set(100.0)
            self.progress_percent_var.set("100%")
        self.elapsed_time_var.set(f"Transcurrido: {format_time(elapsed_time)}")
        self.etr_var.set(f"{status_message} en: {format_time(elapsed_time)}")
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def show_error(self, title: str, message: str) -> None:
        if self._window_alive():
            messagebox.showerror(title, message, parent=self.root)

    def show_warning(self, title: str, message: str) -> None:
        if self._window_alive():
            messagebox.showwarning(title, message, parent=self.root)

    def ask_yes_no(self, title: str, message: str) -> bool:
        return bool(messagebox.askyesno(title, message, parent=self.root))

    def _window_alive(self) -> bool:
        try:
            return bool(self.root and self.root.winfo_exists())
        except tk.TclError:
            return False
