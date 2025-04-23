# -*- coding: utf-8 -*-
import cv2
import os
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Spinbox
import threading
import time
import math
import traceback

# --- VALORES POR DEFECTO ---
margins_top_files_default = { 'top': 260, 'bottom': 350, 'left': 50, 'right': 55 }
margins_bottom_files_default = { 'top': 280, 'bottom': 400, 'left': 80, 'right': 10 }
valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')
default_output_folder_name = "Recortes_Recursivo"
default_jpeg_quality = 50
default_png_compression = 2
tiff_compression_options = {
    1: "Ninguna", 5: "LZW (Lossless)", 8: "ZIP (Lossless)", 7: "JPEG (Lossy)"
}
default_tiff_compression_flag = 7
output_formats = { "JPEG (*.jpg)": ".jpg", "TIFF (*.tif)": ".tif" }
default_output_format_key = "JPEG (*.jpg)"

# --- FUNCIÓN AUXILIAR PARA FORMATEAR TIEMPO ---
def format_time(seconds):
    if seconds < 0: seconds = 0
    seconds = math.floor(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"

# --- LÓGICA DE RECORTE (Indentación CORREGIDA) ---
def crop_image_with_margins(image_path, output_path, margins, compression_params, log_callback):
    t_start_read = time.perf_counter()
    image_to_save = None
# --- INICIO CORRECCIÓN INDENTACIÓN ---
    try:
        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            log_callback(f"  Error carga: {os.path.basename(image_path)}\n")
            return False, 0.0, 0.0, 0.0

        t_end_read = time.perf_counter()
        t_start_process = time.perf_counter()
        has_alpha = image.shape[2] == 4 if len(image.shape) > 2 else False
        img_h, img_w = image.shape[:2]
        margin_top=margins.get('top',0); margin_bottom=margins.get('bottom',0)
        margin_left=margins.get('left',0); margin_right=margins.get('right',0)
        y_start, y_end = margin_top, img_h - margin_bottom
        x_start, x_end = margin_left, img_w - margin_right

        if y_start >= y_end or x_start >= x_end:
            log_callback(f"  Error márgenes: '{os.path.basename(image_path)}'. Alto={y_end-y_start}, Ancho={x_end-x_start}. Se omite.\n")
            t_end_process=time.perf_counter()
            return False, (t_end_read-t_start_read), (t_end_process-t_start_process), 0.0

        y_start=max(0,y_start); y_end=min(img_h,y_end)
        x_start=max(0,x_start); x_end=min(img_w,x_end)
        cropped_image = image[y_start:y_end, x_start:x_end]
        image_to_save = cropped_image # Default
        t_end_process = time.perf_counter()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        t_start_write = time.perf_counter()
        write_params = []
        file_ext = os.path.splitext(output_path)[1].lower()
        log_prefix = f"  Guardando {os.path.basename(output_path)} como {file_ext.upper()} con: "
        original_dtype = cropped_image.dtype

        # --- Lógica de Conversión y Guardado ---
        if file_ext in ['.jpg', '.jpeg']:
            quality = compression_params.get('jpeg_quality', default_jpeg_quality)
            write_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
            log_callback(f"{log_prefix}JPEG Calidad={quality}\n")
            temp_image, conversion_log = convert_to_bgr_uint8(cropped_image, "JPEG")
            if conversion_log: log_callback(conversion_log)
            if temp_image is None: return False, t_end_read-t_start_read, t_end_process-t_start_process, 0.0
            image_to_save = temp_image

        elif file_ext == '.png':
            level = compression_params.get('png_compression', default_png_compression)
            write_params = [cv2.IMWRITE_PNG_COMPRESSION, level]
            log_callback(f"{log_prefix}PNG Compresión={level}\n")
            image_to_save = cropped_image

        elif file_ext in ['.tif', '.tiff']:
            tiff_flag = compression_params.get('tiff_compression_flag', default_tiff_compression_flag)
            write_params = [cv2.IMWRITE_TIFF_COMPRESSION, tiff_flag]
            tiff_option_name = tiff_compression_options.get(tiff_flag, f"Desconocido ({tiff_flag})")
            log_callback(f"{log_prefix}TIFF Compresión={tiff_option_name}")

            if tiff_flag == 7: # JPEG en TIFF
                quality = compression_params.get('jpeg_quality', default_jpeg_quality)
                write_params.extend([cv2.IMWRITE_JPEG_QUALITY, quality])
                log_callback(f" (Calidad={quality})\n")
                temp_image, conversion_log = convert_to_bgr_uint8(cropped_image, "JPEG en TIFF")
                if conversion_log: log_callback(conversion_log)
                if temp_image is None: return False, t_end_read-t_start_read, t_end_process-t_start_process, 0.0
                image_to_save = temp_image
            else: # Compresión TIFF sin pérdida
                log_callback("\n")
                current_dtype = cropped_image.dtype
                temp_image = cropped_image
                if current_dtype in [np.float32, np.float64]:
                    log_callback(f"    Advertencia: Convirtiendo {current_dtype} a uint16 para TIFF sin pérdida (asume rango 0-1).\n")
                    temp_image_clipped = np.clip(temp_image, 0.0, 1.0)
                    image_to_save = (temp_image_clipped * 65535.0).astype(np.uint16)
                elif current_dtype not in [np.uint8, np.uint16]:
                    log_callback(f"    Advertencia: Convirtiendo tipo no estándar {current_dtype} a uint8 para TIFF sin pérdida.\n")
                    try:
                        if np.issubdtype(current_dtype, np.integer):
                            min_val, max_val = np.iinfo(current_dtype).min, np.iinfo(current_dtype).max
                            temp_image_clipped = np.clip(temp_image, 0, 255) if min_val < 0 or max_val > 255 else temp_image
                            image_to_save = temp_image_clipped.astype(np.uint8)
                        else: # bool, etc.
                             image_to_save = temp_image.astype(np.uint8) * 255
                    except Exception as conv_err:
                        log_callback(f"    Error convirtiendo {current_dtype} a uint8: {conv_err}. Omitiendo guardado.\n")
                        return False, t_end_read-t_start_read, t_end_process-t_start_process, 0.0
                # else: image_to_save = cropped_image (default)

        elif file_ext == '.bmp':
             log_callback(f"{log_prefix}BMP (sin compresión)\n")
             temp_image, conversion_log = convert_to_bgr_uint8(cropped_image, "BMP")
             if conversion_log: log_callback(conversion_log)
             if temp_image is None: return False, t_end_read-t_start_read, t_end_process-t_start_process, 0.0
             image_to_save = temp_image

        if image_to_save is None:
             log_callback(f"    Error: No se pudo preparar imagen para guardar ({os.path.basename(output_path)}). Tipo original: {original_dtype}. Omitiendo.\n")
             return False, t_end_read-t_start_read, t_end_process-t_start_process, 0.0

        success = cv2.imwrite(output_path, image_to_save, write_params)
        t_end_write = time.perf_counter()

        if success:
            return True, (t_end_read-t_start_read), (t_end_process-t_start_process), (t_end_write-t_start_write)
        else:
            log_callback(f"  Fallo cv2.imwrite para: {os.path.basename(output_path)} (ver logs, permisos, espacio)\n")
            return False, (t_end_read-t_start_read), (t_end_process-t_start_process), (t_end_write-t_start_write)

    except Exception as e:
        t_now = time.perf_counter()
        log_callback(f"!! Excepción interna en crop_image_with_margins para {os.path.basename(image_path)}: {e}\n")
        log_callback(f"   Traceback: {traceback.format_exc()}\n")
        t_read = t_end_read - t_start_read if 't_end_read' in locals() else t_now - t_start_read
        t_proc = t_end_process - t_start_process if 't_end_process' in locals() else 0.0
        t_write = t_end_write - t_start_write if 't_end_write' in locals() else 0.0
        return False, t_read, t_proc, t_write


# --- FUNCIÓN AUXILIAR para convertir a BGR uint8 ---
def convert_to_bgr_uint8(img, format_name):
    logs = ""; current_dtype = img.dtype; current_channels = img.shape[2] if len(img.shape) > 2 else 1; temp_image = img
    if current_dtype != np.uint8:
        logs += f"    Advertencia: Convirtiendo {current_dtype} a uint8 para {format_name}.\n";
        if current_dtype == np.uint16: temp_image = (img / 256).astype(np.uint8)
        elif current_dtype in [np.float32, np.float64]: temp_image_clipped = np.clip(img, 0.0, 1.0); temp_image = (temp_image_clipped * 255.0).astype(np.uint8)
        else:
            try: temp_image_clipped = np.clip(img, 0, 255); temp_image = temp_image_clipped.astype(np.uint8);
            except Exception as conv_err: logs += f"    Error convirtiendo {current_dtype} a uint8: {conv_err}.\n"; return None, logs
        current_channels = temp_image.shape[2] if len(temp_image.shape) > 2 else 1

    if current_channels == 4:
        logs += f"    Advertencia: Eliminando canal Alfa para {format_name}.\n"; image_converted = cv2.cvtColor(temp_image, cv2.COLOR_BGRA2BGR)
    elif current_channels == 1:
        image_converted = cv2.cvtColor(temp_image, cv2.COLOR_GRAY2BGR)
    elif current_channels == 3:
        image_converted = temp_image
    else:
        logs += f"    Error: Canales ({current_channels}) no soportados para {format_name}.\n"; return None, logs
    return image_converted, logs


# --- CLASE DE LA APLICACIÓN GUI ---
class BatchCropperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Recortador de Imágenes v1.0")
        self.root.geometry("800x680")

        self.input_folder_path = tk.StringVar(); self.output_folder_path = tk.StringVar()
        self.output_folder_name_var = tk.StringVar(value=default_output_folder_name)
        self.jpeg_quality_var = tk.IntVar(value=default_jpeg_quality)
        self.png_compression_var = tk.IntVar(value=default_png_compression)
        self.tiff_compression_var = tk.StringVar()
        self.tiff_flag_map = {v: k for k, v in tiff_compression_options.items()}
        self.output_format_var = tk.StringVar(value=default_output_format_key)

        self.progress_var = tk.DoubleVar(value=0.0); self.etr_var = tk.StringVar(value="Restante: --:--")
        self.progress_percent_var = tk.StringVar(value="0%"); self.cancel_event = threading.Event()
        self.elapsed_time_var = tk.StringVar(value="Transcurrido: 00:00")

        style = ttk.Style(self.root); style.configure("Progress.TLabel", foreground="black", anchor=tk.CENTER)
        try: style.configure("Progress.TLabel", background=style.lookup('TProgressbar', 'troughcolor'))
        except tk.TclError: style.configure("Progress.TLabel", background="lightgrey")

        main_frame = ttk.Frame(root, padding="10"); main_frame.pack(fill=tk.BOTH, expand=True); main_frame.columnconfigure(0, weight=1)

        top_frame = ttk.LabelFrame(main_frame, text="Configuración Principal", padding="10"); top_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 10)); top_frame.columnconfigure(1, weight=1); top_frame.columnconfigure(2, weight=0)
        ttk.Button(top_frame, text="Seleccionar Carpeta Origen", command=self.select_input_folder).grid(row=0, column=0, padx=5, pady=2, sticky="w"); ttk.Label(top_frame, textvariable=self.input_folder_path, wraplength=380, anchor="w").grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ttk.Label(top_frame, text="Nombre Carpeta Salida:").grid(row=1, column=0, padx=5, pady=2, sticky="w"); self.output_name_entry = ttk.Entry(top_frame, textvariable=self.output_folder_name_var, width=30); self.output_name_entry.grid(row=1, column=1, padx=5, pady=2, sticky="w"); self.output_folder_name_var.trace_add("write", self.update_output_path_display)
        ttk.Label(top_frame, text="Ruta Carpeta Salida:").grid(row=2, column=0, padx=5, pady=2, sticky="w"); ttk.Label(top_frame, textvariable=self.output_folder_path, wraplength=380, foreground="grey", anchor="w").grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        button_frame = ttk.Frame(top_frame); button_frame.grid(row=0, column=2, rowspan=3, padx=(10, 5), pady=5, sticky="ns"); self.start_button = ttk.Button(button_frame, text="Iniciar", command=self.start_processing_thread, width=10); self.start_button.pack(pady=5, fill=tk.X); self.cancel_button = ttk.Button(button_frame, text="Cancelar", command=self.cancel_processing, width=10, state=tk.DISABLED); self.cancel_button.pack(pady=5, fill=tk.X)

        margins_frame = ttk.LabelFrame(main_frame, text="Márgenes (px)", padding="10"); margins_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5); margins_frame.columnconfigure(1, weight=0); margins_frame.columnconfigure(2, weight=1); margins_frame.columnconfigure(3, weight=0); margins_frame.columnconfigure(4, weight=1); margins_frame.columnconfigure(5, weight=0); margins_frame.columnconfigure(6, weight=1); margins_frame.columnconfigure(7, weight=0); margins_frame.columnconfigure(8, weight=1)
        ttk.Label(margins_frame, text="Top:", font="-weight bold").grid(row=0, column=0, padx=(0,10), pady=2, sticky="w"); self.spinboxes_top = self.create_margin_spinboxes_inline(margins_frame, margins_top_files_default, target_row=0)
        ttk.Label(margins_frame, text="Bottom:", font="-weight bold").grid(row=1, column=0, padx=(0,10), pady=2, sticky="w"); self.spinboxes_bottom = self.create_margin_spinboxes_inline(margins_frame, margins_bottom_files_default, target_row=1)

        format_comp_frame = ttk.LabelFrame(main_frame, text="Formato Salida y Compresión", padding="10"); format_comp_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5); format_comp_frame.columnconfigure(1, weight=1); format_comp_frame.columnconfigure(3, weight=1); format_comp_frame.columnconfigure(5, weight=0)
        ttk.Label(format_comp_frame, text="Formato Salida:").grid(row=0, column=0, padx=5, pady=5, sticky="w"); self.output_format_combo = ttk.Combobox(format_comp_frame, textvariable=self.output_format_var, values=list(output_formats.keys()), state="readonly", width=15); self.output_format_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w"); self.output_format_var.set(default_output_format_key)
        ttk.Label(format_comp_frame, text="JPEG (0-100):").grid(row=1, column=0, padx=5, pady=5, sticky="w"); self.jpeg_quality_slider = ttk.Scale(format_comp_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.jpeg_quality_var, command=lambda s: self.jpeg_quality_var.set(int(float(s))), length=150); self.jpeg_quality_slider.grid(row=1, column=1, padx=5, pady=5, sticky="ew"); self.jpeg_quality_label = ttk.Label(format_comp_frame, textvariable=self.jpeg_quality_var, width=4); self.jpeg_quality_label.grid(row=1, column=2, padx=(0, 15), pady=5)
        ttk.Label(format_comp_frame, text="TIFF Compresión:").grid(row=1, column=3, padx=5, pady=5, sticky="w"); self.tiff_compression_combo = ttk.Combobox(format_comp_frame, textvariable=self.tiff_compression_var, values=list(tiff_compression_options.values()), state="readonly", width=18); default_tiff_name = tiff_compression_options.get(default_tiff_compression_flag, "LZW (Lossless)"); self.tiff_compression_var.set(default_tiff_name); self.tiff_compression_combo.grid(row=1, column=4, columnspan=2, padx=5, pady=5, sticky="w")

        progress_frame = ttk.Frame(main_frame, padding=(5, 0, 5, 5)); progress_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(10, 0)); progress_frame.columnconfigure(0, weight=1); progress_frame.columnconfigure(1, weight=0); progress_frame.columnconfigure(2, weight=0)
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=100, mode="determinate", variable=self.progress_var); self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.progress_percent_label = ttk.Label(progress_frame, textvariable=self.progress_percent_var, style="Progress.TLabel"); self.progress_percent_label.place(in_=self.progress_bar, relx=0.5, rely=0.5, anchor=tk.CENTER); self.progress_percent_label.lift()
        self.elapsed_label = ttk.Label(progress_frame, textvariable=self.elapsed_time_var, width=20); self.elapsed_label.grid(row=0, column=1, sticky="w", padx=(0, 10))
        self.etr_label = ttk.Label(progress_frame, textvariable=self.etr_var, width=18); self.etr_label.grid(row=0, column=2, sticky="e")

        log_frame = ttk.Frame(main_frame); log_frame.grid(row=4, column=0, sticky="nsew", padx=5, pady=(5, 5)); main_frame.rowconfigure(4, weight=1); log_frame.columnconfigure(0, weight=1); log_frame.rowconfigure(1, weight=1)
        log_label = ttk.Label(log_frame, text="Registro de Proceso:"); log_label.grid(row=0, column=0, sticky="w", pady=(0, 5)); self.log_area = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD, state=tk.DISABLED); self.log_area.grid(row=1, column=0, sticky="nsew")

        self.update_output_path_display()

    # --- Métodos auxiliares ---
    def create_margin_spinboxes_inline(self, parent_frame, defaults, target_row):
        spinboxes = {}; keys_order = ['top', 'bottom', 'left', 'right']; labels_text = {'top': 'Arriba:', 'bottom': 'Abajo:', 'left': 'Izquierda:', 'right': 'Derecha:'}; current_col = 1
        for key in keys_order: ttk.Label(parent_frame, text=labels_text[key]).grid(row=target_row, column=current_col, padx=(5, 2), pady=2, sticky="e"); current_col += 1; spinbox_var = tk.IntVar(value=defaults.get(key, 0)); spinbox = Spinbox(parent_frame, from_=0, to=9999, increment=1, textvariable=spinbox_var, width=5); spinbox.grid(row=target_row, column=current_col, padx=(0, 10), pady=2, sticky="w"); spinboxes[key] = spinbox_var; current_col += 1
        return spinboxes

    def select_input_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.input_folder_path.set(folder_selected)
            self.log_message(f"Origen: {folder_selected}\n")
            self.update_output_path_display()

    def update_output_path_display(self, *args):
        input_dir = self.input_folder_path.get(); output_name = self.output_folder_name_var.get().strip(); parent_dir = os.path.dirname(input_dir) if input_dir else None
        if parent_dir and output_name: self.output_folder_path.set(os.path.join(parent_dir, output_name))
        elif input_dir: self.output_folder_path.set("<-- Nombre carpeta salida")
        else: self.output_folder_path.set("")

    def log_message(self, message):
        def _log():
            if self.log_area:
                try: self.log_area.config(state=tk.NORMAL); self.log_area.insert(tk.END, message); self.log_area.see(tk.END); self.log_area.config(state=tk.DISABLED)
                except tk.TclError as e: print(f"Error logging: {e}")
        if self.root:
            try: self.root.after(0, _log)
            except tk.TclError: pass

    def get_margins_from_gui(self):
        margins_top = {}; margins_bottom = {}
        try:
            for key, var in self.spinboxes_top.items(): margins_top[key] = var.get()
            for key, var in self.spinboxes_bottom.items(): margins_bottom[key] = var.get()
            all_margin_values = list(margins_top.values()) + list(margins_bottom.values())
            for val in all_margin_values:
                if val < 0: raise ValueError("Márgenes no negativos.")
            return margins_top, margins_bottom
        except (ValueError, tk.TclError) as e: messagebox.showerror("Error Entrada", f"Valor inválido márgenes: {e}."); return None, None

    def get_compression_params_from_gui(self):
        tiff_scheme_name = self.tiff_compression_var.get(); tiff_flag = self.tiff_flag_map.get(tiff_scheme_name, default_tiff_compression_flag)
        return { 'jpeg_quality': self.jpeg_quality_var.get(), 'png_compression': self.png_compression_var.get(), 'tiff_compression_flag': tiff_flag }

    def reset_progress(self):
        self.cancel_event.clear()
        self.progress_var.set(0.0)
        self.progress_percent_var.set("0%")
        self.elapsed_time_var.set("Transcurrido: 00:00")
        self.etr_var.set("Restante: Calculando...")
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        if self.root:
            self.root.update_idletasks()

    def update_progress(self, current_value, total_value, elapsed_time):
        if total_value == 0: return
        progress_percent = (current_value / total_value) * 100
        self.progress_var.set(progress_percent)
        self.progress_percent_var.set(f"{progress_percent:.0f}%")
        self.elapsed_time_var.set(f"Transcurrido: {format_time(elapsed_time)}")
        if current_value > 0 and current_value < total_value:
            time_per_item = elapsed_time / current_value
            remaining_items = total_value - current_value
            etr_seconds = time_per_item * remaining_items
            self.etr_var.set(f"Restante: {format_time(etr_seconds)}")
        elif current_value == 0 and total_value > 0:
            self.etr_var.set("Restante: Calculando...")
        else: # Completado
            self.etr_var.set("Restante: 00:00")

    def finalize_progress(self, start_time, was_cancelled=False):
        total_time = time.perf_counter() - start_time
        status_message = "Cancelado" if was_cancelled else "Completado"
        self.progress_var.set(100.0)
        if not was_cancelled:
            self.progress_percent_var.set("100%")
        self.elapsed_time_var.set(f"Transcurrido: {format_time(total_time)}")
        self.etr_var.set(f"{status_message} en: {format_time(total_time)}")
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        if self.root:
            self.root.update_idletasks()

    def cancel_processing(self):
        if not self.cancel_event.is_set():
            self.log_message("--- Cancelación solicitada por el usuario ---\n")
            self.cancel_event.set()
            self.cancel_button.config(state=tk.DISABLED)

    # --- Lógica de Procesamiento Principal ---
    def start_processing_thread(self):
        input_dir=self.input_folder_path.get(); output_name=self.output_folder_name_var.get().strip(); output_dir=self.output_folder_path.get()
        if not input_dir or not os.path.isdir(input_dir): messagebox.showwarning("Inválido", "Carpeta origen inválida."); return
        if not output_name: messagebox.showwarning("Requerido", "Nombre carpeta salida."); return
        if not output_dir or "<--" in output_dir: messagebox.showerror("Error", "No se pudo determinar ruta salida."); return
        margins_top, margins_bottom = self.get_margins_from_gui();
        if margins_top is None: return
        compression_params = self.get_compression_params_from_gui()
        selected_output_format_key = self.output_format_var.get()
        selected_output_ext = output_formats.get(selected_output_format_key, ".jpg")
        tiff_scheme_name = self.tiff_compression_var.get()

        self.reset_progress()
        self.log_message("\n--- Iniciando Proceso Recursivo ---\n")
        self.log_message(f"Origen: {input_dir}\nSalida Base: {output_dir}\n")
        self.log_message(f"Márgenes Top: {margins_top}\nBottom: {margins_bottom}\n")
        self.log_message(f"Formato Salida: {selected_output_format_key}\n")
        self.log_message(f"Compresión:\n JPEG Calidad: {compression_params['jpeg_quality']}\n PNG Nivel: {compression_params['png_compression']} (No aplicable)\n TIFF Esquema: {tiff_scheme_name} (Si salida=TIFF)\n BMP: (No aplicable)\n")

        processing_thread = threading.Thread(target=self.run_batch_crop_recursive, args=(input_dir, output_dir, margins_top, margins_bottom, compression_params, selected_output_ext), daemon=True)
        processing_thread.start()

    def run_batch_crop_recursive(self, input_base_dir, output_base_dir, margins_top, margins_bottom, compression_params, selected_output_ext):
        thread_start_time = time.perf_counter(); was_cancelled = False; processed_count, skipped_count, error_count = 0, 0, 0; total_read_time, total_process_time, total_write_time = 0.0, 0.0, 0.0; num_files = 0; files_to_process_list = []

        self.log_message("Buscando archivos (recursivamente)...\n")
        try:
            for current_dir_path, _, filenames in os.walk(input_base_dir):
                for filename in filenames:
                    if filename.lower().endswith(valid_extensions):
                        input_file_path = os.path.join(current_dir_path, filename)
                        files_to_process_list.append(input_file_path)
        except OSError as e: self.log_message(f"Error fatal al buscar archivos en '{input_base_dir}': {e}\n"); self.root.after(0, lambda: messagebox.showerror("Error Búsqueda", f"No se pudo recorrer: {e}")); self.root.after(0, self.finalize_progress, thread_start_time, was_cancelled); return

        num_files = len(files_to_process_list)
        if not files_to_process_list: self.log_message("No se encontraron archivos válidos.\n"); self.root.after(0, self.finalize_progress, thread_start_time, was_cancelled); return
        else: self.log_message(f"Encontrados {num_files} archivos.\n"); self.root.after(0, self.update_progress, 0, num_files, 0)

        file_index = 0
        try:
            for input_file_path in files_to_process_list:
                if self.cancel_event.is_set(): was_cancelled = True; self.log_message(f"--- Cancelado antes de '{os.path.basename(input_file_path)}' ---\n"); break
                relative_path = os.path.relpath(os.path.dirname(input_file_path), input_base_dir); output_subdir = os.path.join(output_base_dir, relative_path) if relative_path != '.' else output_base_dir
                try: os.makedirs(output_subdir, exist_ok=True)
                except OSError as make_err: self.log_message(f"  Error creando dir '{output_subdir}': {make_err}.\n"); error_count += 1; file_index += 1; elapsed_thread_time = time.perf_counter()-thread_start_time; self.root.after(0, self.update_progress, file_index, num_files, elapsed_thread_time); continue
                base_name, _ = os.path.splitext(os.path.basename(input_file_path)); output_filename = base_name + selected_output_ext; output_file_path = os.path.normpath(os.path.join(output_subdir, output_filename))
                log_display_path_in = os.path.join(os.path.basename(input_base_dir), os.path.relpath(input_file_path, input_base_dir)); log_display_path_out = os.path.join(os.path.basename(output_base_dir), os.path.relpath(output_file_path, output_base_dir))
                self.log_message(f"[{file_index+1}/{num_files}] Proc: '{log_display_path_in}' -> '{log_display_path_out}'...")
                filename_for_margins = os.path.basename(input_file_path)
                if "Top" in filename_for_margins: current_margins = margins_top
                elif "Bottom" in filename_for_margins: current_margins = margins_bottom
                else: self.log_message(" omitido (no Top/Bottom).\n"); skipped_count += 1; file_index += 1; elapsed_thread_time = time.perf_counter()-thread_start_time; self.root.after(0, self.update_progress, file_index, num_files, elapsed_thread_time); continue
                success, t_read, t_proc, t_write = crop_image_with_margins(input_file_path, output_file_path, current_margins, compression_params, self.log_message)
                total_read_time += t_read; total_process_time += t_proc; total_write_time += t_write
                if success:
                    processed_count += 1; size_info = "";
                    try:
                        if os.path.exists(output_file_path): input_size_kb = os.path.getsize(input_file_path)/1024; output_size_kb = os.path.getsize(output_file_path)/1024; reduction = 100*(1-output_size_kb/input_size_kb) if input_size_kb > 0 else 0; size_info = f" ({output_size_kb:.1f}kB, Red:{reduction:.1f}%)"
                    except OSError as e: size_info = f" (Err tamaño:{e.strerror})"
                    self.log_message(f" ¡OK!{size_info}\n")
                else: error_count += 1
                file_index += 1
                elapsed_thread_time = time.perf_counter() - thread_start_time
                self.root.after(0, self.update_progress, file_index, num_files, elapsed_thread_time)
        except Exception as e: was_cancelled = self.cancel_event.is_set(); self.log_message(f"\n!!! Error General: {e} !!!\n"); self.log_message(f"Traceback: {traceback.format_exc()}\n"); self.root.after(0, lambda: messagebox.showerror("Error Grave", f"Error: {e}"))
        finally:
            final_status = "--- Proceso Cancelado ---\n" if was_cancelled else "--- Proceso Completado ---\n"; self.log_message(f"\n{final_status}")
            self.log_message(f"Resumen: Procesados:{processed_count} | Omitidos:{skipped_count} | Errores:{error_count} (de {num_files} archivos encontrados)\n")
            if processed_count > 0: avg_read=total_read_time/processed_count; avg_proc=total_process_time/processed_count; avg_write=total_write_time/processed_count; self.log_message(f"Tiempos(s) Avg: Lect:{avg_read:.3f}|Proc:{avg_proc:.3f}|Escr:{avg_write:.3f}\n")
            self.root.after(0, self.finalize_progress, thread_start_time, was_cancelled)

# --- EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":
    root = tk.Tk()
    app = BatchCropperApp(root)
    root.mainloop()