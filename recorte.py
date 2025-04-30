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
import json
import sys  # <--- IMPORTADO PARA MANEJO DE RUTA EN EJECUTABLE

# --- VALORES POR DEFECTO ---
margins_top_files_default = { 'top': 260, 'bottom': 350, 'left': 50, 'right': 55 }
margins_bottom_files_default = { 'top': 280, 'bottom': 400, 'left': 80, 'right': 10 }
valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')
default_output_folder_name = "Imagenes_pro"
default_jpeg_quality = 90
default_png_compression = 3
tiff_compression_options = { 1: "Ninguna", 5: "LZW (Lossless)", 8: "ZIP (Lossless)", 7: "JPEG (Lossy)" }
default_tiff_compression_flag = 5
output_formats = { "JPEG (*.jpg)": ".jpg", "TIFF (*.tif)": ".tif" }
default_output_format_key = "JPEG (*.jpg)"
default_top_identifier = "Top"
default_bottom_identifier = "Bottom"

# --- RUTA ARCHIVO CONFIGURACIÓN (MEJORADA PARA EJECUTABLES) ---
def get_base_path():
    """ Obtiene la ruta base correcta, ya sea para script o ejecutable empaquetado. """
    if getattr(sys, 'frozen', False):
        # Si está empaquetado (ejecutable), usa la ruta del directorio del ejecutable
        application_path = os.path.dirname(sys.executable)
        # print(f"DEBUG: Running bundled. Base path: {application_path}") # Descomenta para depurar
    else:
        # Si se ejecuta como script, usa la ruta del directorio del script
        application_path = os.path.dirname(os.path.abspath(__file__))
        # print(f"DEBUG: Running as script. Base path: {application_path}") # Descomenta para depurar
    return application_path

CONFIG_FILE_NAME = "recortador_config.json"
# Define la ruta completa al archivo de configuración usando la función get_base_path()
CONFIG_FILE = os.path.join(get_base_path(), CONFIG_FILE_NAME)
# print(f"DEBUG: Config file path determined as: {CONFIG_FILE}") # Descomenta para depurar la ruta final

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

# --- LÓGICA DE RECORTE ---
def crop_image_with_margins(image_path, output_path, margins, compression_params, log_callback):
    t_start_read = time.perf_counter()
    image_to_save = None
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

        output_dir_path = os.path.dirname(output_path)
        if output_dir_path:
            os.makedirs(output_dir_path, exist_ok=True)

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
            image_to_save = cropped_image # PNG soporta más tipos, no siempre necesita conversión

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
                # Manejo de tipos de datos para TIFF sin pérdida
                if current_dtype in [np.float32, np.float64]:
                    log_callback(f"    Advertencia: Convirtiendo {current_dtype} a uint16 para TIFF sin pérdida (asume rango 0-1).\n")
                    temp_image_clipped = np.clip(temp_image, 0.0, 1.0)
                    image_to_save = (temp_image_clipped * 65535.0).astype(np.uint16)
                elif current_dtype == np.uint16:
                     image_to_save = temp_image # Ya está en formato adecuado
                elif current_dtype == np.uint8:
                     image_to_save = temp_image # Ya está en formato adecuado
                else: # Otros tipos (int32, bool, etc.) -> convertir a uint8 como fallback seguro
                    log_callback(f"    Advertencia: Convirtiendo tipo no estándar {current_dtype} a uint8 para TIFF sin pérdida.\n")
                    try:
                        if np.issubdtype(current_dtype, np.integer):
                            min_val, max_val = np.iinfo(current_dtype).min, np.iinfo(current_dtype).max
                            # Escala si es necesario, clip a 0-255
                            if min_val < 0 or max_val > 255:
                                temp_image_clipped = np.clip(temp_image, 0, 255)
                                image_to_save = temp_image_clipped.astype(np.uint8)
                                log_callback(f"      (Valores fuera de 0-255 detectados, se hizo clipping a uint8)\n")
                            else: # El rango ya cabe en uint8
                                image_to_save = temp_image.astype(np.uint8)
                        elif np.issubdtype(current_dtype, np.bool_):
                             image_to_save = temp_image.astype(np.uint8) * 255
                        else: # Otros tipos flotantes o complejos no manejados explícitamente
                             log_callback(f"      Tipo {current_dtype} no manejado específicamente, intentando conversión directa a uint8.\n")
                             image_to_save = temp_image.astype(np.uint8) # Conversión directa, puede perder información
                    except Exception as conv_err:
                        log_callback(f"    Error crítico convirtiendo {current_dtype} a uint8: {conv_err}. Omitiendo guardado.\n")
                        return False, t_end_read-t_start_read, t_end_process-t_start_process, 0.0

        elif file_ext == '.bmp':
             log_callback(f"{log_prefix}BMP (sin compresión)\n")
             temp_image, conversion_log = convert_to_bgr_uint8(cropped_image, "BMP")
             if conversion_log: log_callback(conversion_log)
             if temp_image is None: return False, t_end_read-t_start_read, t_end_process-t_start_process, 0.0
             image_to_save = temp_image

        # Verificar antes de intentar guardar
        if image_to_save is None:
             log_callback(f"    Error: No se pudo preparar imagen para guardar ({os.path.basename(output_path)}). Tipo original: {original_dtype}. Omitiendo.\n")
             return False, t_end_read-t_start_read, t_end_process-t_start_process, 0.0

        # Intentar guardar la imagen
        success = cv2.imwrite(output_path, image_to_save, write_params)
        t_end_write = time.perf_counter()

        if success:
            return True, (t_end_read-t_start_read), (t_end_process-t_start_process), (t_end_write-t_start_write)
        else:
            log_callback(f"  Fallo cv2.imwrite para: {os.path.basename(output_path)} (verificar permisos, espacio, formato compatible con tipo de dato: {image_to_save.dtype})\n")
            return False, (t_end_read-t_start_read), (t_end_process-t_start_process), (t_end_write-t_start_write)

    except Exception as e:
        t_now = time.perf_counter()
        log_callback(f"!! Excepción interna en crop_image_with_margins para {os.path.basename(image_path)}: {e}\n")
        log_callback(f"   Tipo Excepción: {type(e).__name__}\n")
        log_callback(f"   Traceback: {traceback.format_exc()}\n")
        # Calcula tiempos parciales si es posible
        t_read = t_end_read - t_start_read if 't_end_read' in locals() else t_now - t_start_read
        t_proc = t_end_process - t_start_process if 't_end_process' in locals() else 0.0
        t_write = t_end_write - t_start_write if 't_end_write' in locals() else 0.0
        return False, t_read, t_proc, t_write
# --- FIN FUNCIÓN CROP ---

# --- FUNCIÓN AUXILIAR convert_to_bgr_uint8 ---
def convert_to_bgr_uint8(img, format_name):
    """Convierte la imagen a BGR uint8 si es necesario para formatos como JPG, BMP."""
    logs = ""
    current_dtype = img.dtype
    current_channels = img.shape[2] if len(img.shape) > 2 else 1
    temp_image = img # Imagen a modificar

    # 1. Conversión de tipo de dato a uint8 si es necesario
    if current_dtype != np.uint8:
        logs += f"    Advertencia: Convirtiendo {current_dtype} a uint8 para {format_name}.\n"
        if current_dtype == np.uint16:
            # Asume rango 0-65535 -> 0-255
            temp_image = (img / 257.0).astype(np.uint8) # Usar 257 para mapeo más preciso
            logs += "      (Asumiendo rango 16-bit completo)\n"
        elif current_dtype in [np.float32, np.float64]:
            # Asume rango 0.0-1.0 -> 0-255
            logs += "      (Asumiendo rango flotante 0.0-1.0)\n"
            temp_image_clipped = np.clip(img, 0.0, 1.0)
            temp_image = (temp_image_clipped * 255.0).astype(np.uint8)
        elif np.issubdtype(current_dtype, np.integer):
            # Otros enteros (e.g., int32). Clip a 0-255
            logs += "      (Clipping a rango 0-255)\n"
            min_val, max_val = np.iinfo(current_dtype).min, np.iinfo(current_dtype).max
            temp_image_clipped = np.clip(img, 0, 255)
            temp_image = temp_image_clipped.astype(np.uint8)
        else:
            # Otros tipos (bool, etc.) - Intenta convertir directamente
            try:
                logs += f"      (Intentando conversión directa desde {current_dtype})\n"
                temp_image = img.astype(np.uint8)
                # Si era booleano, multiplicar por 255 para que True sea blanco
                if np.issubdtype(current_dtype, np.bool_):
                    temp_image = temp_image * 255
            except Exception as conv_err:
                logs += f"    Error crítico convirtiendo {current_dtype} a uint8: {conv_err}.\n"
                return None, logs # No se puede convertir
        # Actualizar canales por si la conversión cambió la estructura (poco probable aquí)
        current_channels = temp_image.shape[2] if len(temp_image.shape) > 2 else 1

    # 2. Conversión de canales a BGR (3 canales) si es necesario
    if current_channels == 4:
        logs += f"    Advertencia: Eliminando canal Alfa para {format_name}.\n"
        image_converted = cv2.cvtColor(temp_image, cv2.COLOR_BGRA2BGR)
    elif current_channels == 1:
        # Convertir escala de grises a BGR
        image_converted = cv2.cvtColor(temp_image, cv2.COLOR_GRAY2BGR)
    elif current_channels == 3:
        # Ya está en BGR (o RGB, OpenCV maneja BGR por defecto)
        image_converted = temp_image
    else:
        logs += f"    Error: Número de canales ({current_channels}) no soportado para conversión a BGR para {format_name}.\n"
        return None, logs # Formato no soportado

    return image_converted, logs

# --- CLASE DE LA APLICACIÓN GUI ---
class BatchCropperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Recortador de Imágenes v1.1")
        self.root.geometry("800x710")

        # --- Variables Tkinter ---
        self.input_folder_path = tk.StringVar()
        self.output_folder_path = tk.StringVar()
        self.output_folder_name_var = tk.StringVar(value=default_output_folder_name)
        self.jpeg_quality_var = tk.IntVar(value=default_jpeg_quality)
        self.png_compression_var = tk.IntVar(value=default_png_compression) # Aunque no se use mucho, se guarda/carga
        self.tiff_compression_var = tk.StringVar() # Nombre legible de la compresión TIFF
        self.tiff_flag_map = {v: k for k, v in tiff_compression_options.items()} # Mapa inverso para obtener flag
        self.output_format_var = tk.StringVar(value=default_output_format_key)
        self.top_identifier_var = tk.StringVar(value=default_top_identifier)
        self.bottom_identifier_var = tk.StringVar(value=default_bottom_identifier)
        self.margins_top_vars = {key: tk.IntVar(value=val) for key, val in margins_top_files_default.items()}
        self.margins_bottom_vars = {key: tk.IntVar(value=val) for key, val in margins_bottom_files_default.items()}

        self.progress_var = tk.DoubleVar(value=0.0)
        self.etr_var = tk.StringVar(value="Restante: --:--")
        self.progress_percent_var = tk.StringVar(value="0%")
        self.cancel_event = threading.Event()
        self.elapsed_time_var = tk.StringVar(value="Transcurrido: 00:00")

        # --- Estilo ---
        style = ttk.Style(self.root)
        style.configure("Progress.TLabel", foreground="black", anchor=tk.CENTER)
        try:
            # Intenta obtener el color de fondo de la barra de progreso para el texto
            style.configure("Progress.TLabel", background=style.lookup('TProgressbar', 'troughcolor'))
        except tk.TclError:
            # Fallback si el estilo no lo soporta
            style.configure("Progress.TLabel", background="lightgrey")

        # --- Layout Principal ---
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1) # Columna principal expandible

        # --- Frame Configuración Principal ---
        top_frame = ttk.LabelFrame(main_frame, text="Configuración Principal", padding="10")
        top_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 10))
        top_frame.columnconfigure(1, weight=1) # Hacer columna de la ruta expandible
        top_frame.columnconfigure(2, weight=0) # Columna de botones no expandible

        ttk.Button(top_frame, text="Seleccionar Carpeta Origen", command=self.select_input_folder).grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Label(top_frame, textvariable=self.input_folder_path, wraplength=380, anchor="w").grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        ttk.Label(top_frame, text="Nombre Carpeta Salida:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.output_name_entry = ttk.Entry(top_frame, textvariable=self.output_folder_name_var, width=30)
        self.output_name_entry.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.output_folder_name_var.trace_add("write", self.update_output_path_display) # Actualizar ruta al cambiar nombre

        ttk.Label(top_frame, text="Ruta Carpeta Salida:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        ttk.Label(top_frame, textvariable=self.output_folder_path, wraplength=380, foreground="grey", anchor="w").grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        # Frame para botones Iniciar/Cancelar
        button_frame = ttk.Frame(top_frame)
        button_frame.grid(row=0, column=2, rowspan=3, padx=(10, 5), pady=5, sticky="ns")
        self.start_button = ttk.Button(button_frame, text="Iniciar", command=self.start_processing_thread, width=10)
        self.start_button.pack(pady=5, fill=tk.X)
        self.cancel_button = ttk.Button(button_frame, text="Cancelar", command=self.cancel_processing, width=10, state=tk.DISABLED)
        self.cancel_button.pack(pady=5, fill=tk.X)

        # --- Frame Identificadores y Márgenes ---
        margins_frame = ttk.LabelFrame(main_frame, text="Identificadores y Márgenes (px)", padding="10")
        margins_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        margins_frame.columnconfigure(1, weight=1) # Columna para identificador top
        margins_frame.columnconfigure(3, weight=1) # Columna para identificador bottom

        ttk.Label(margins_frame, text="Identificador 'Frente':").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.top_id_entry = ttk.Entry(margins_frame, textvariable=self.top_identifier_var, width=20)
        self.top_id_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(margins_frame, text="Identificador 'Reverso':").grid(row=0, column=2, padx=(15, 5), pady=5, sticky="w")
        self.bottom_id_entry = ttk.Entry(margins_frame, textvariable=self.bottom_identifier_var, width=20)
        self.bottom_id_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        #ttk.Separator(margins_frame, orient=tk.HORIZONTAL).grid(row=1, column=0, columnspan=8, pady=(10, 5), sticky="ew") # Separador opcional

        ttk.Label(margins_frame, text="Márgenes para Identificador 'Frente':", font="-weight bold").grid(row=2, column=0, columnspan=4, padx=5, pady=(10, 2), sticky="w")
        self.spinboxes_top_widgets = self.create_margin_spinboxes_inline(margins_frame, self.margins_top_vars, target_row=3)

        ttk.Label(margins_frame, text="Márgenes para Identificador 'Reverso':", font="-weight bold").grid(row=4, column=0, columnspan=4, padx=5, pady=(10, 2), sticky="w")
        self.spinboxes_bottom_widgets = self.create_margin_spinboxes_inline(margins_frame, self.margins_bottom_vars, target_row=5)

        # --- Frame Formato Salida y Compresión ---
        format_comp_frame = ttk.LabelFrame(main_frame, text="Formato Salida y Compresión", padding="10")
        format_comp_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        # Configurar columnas para mejor distribución
        format_comp_frame.columnconfigure(1, weight=1)
        format_comp_frame.columnconfigure(4, weight=1)

        # Formato Salida
        ttk.Label(format_comp_frame, text="Formato Salida:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.output_format_combo = ttk.Combobox(format_comp_frame, textvariable=self.output_format_var, values=list(output_formats.keys()), state="readonly", width=15)
        self.output_format_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        # Añadir tooltip (si quieres, requiere libreria externa o más código)
        # ToolTip(self.output_format_combo, "Elige el formato de archivo para las imágenes procesadas.")

        # Calidad JPEG
        ttk.Label(format_comp_frame, text="JPEG Calidad (0-100):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.jpeg_quality_slider = ttk.Scale(format_comp_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.jpeg_quality_var, command=lambda s: self.jpeg_quality_var.set(int(float(s))), length=150)
        self.jpeg_quality_slider.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.jpeg_quality_label = ttk.Label(format_comp_frame, textvariable=self.jpeg_quality_var, width=4)
        self.jpeg_quality_label.grid(row=1, column=2, padx=(0, 15), pady=5, sticky="w") # Alineado a la izquierda

        # Compresión TIFF
        ttk.Label(format_comp_frame, text="TIFF Compresión:").grid(row=1, column=3, padx=(15, 5), pady=5, sticky="w") # Añadir padding izquierdo
        self.tiff_compression_combo = ttk.Combobox(format_comp_frame, textvariable=self.tiff_compression_var, values=list(tiff_compression_options.values()), state="readonly", width=18)
        self.tiff_compression_combo.grid(row=1, column=4, columnspan=2, padx=5, pady=5, sticky="w")
        # ToolTip(self.tiff_compression_combo, "Elige el método de compresión para archivos TIFF. LZW y ZIP son sin pérdida.")

        # --- Frame Progreso ---
        progress_frame = ttk.Frame(main_frame, padding=(5, 0, 5, 5))
        progress_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(10, 0))
        progress_frame.columnconfigure(0, weight=1) # Barra de progreso expandible
        progress_frame.columnconfigure(1, weight=0) # Etiqueta tiempo transcurrido
        progress_frame.columnconfigure(2, weight=0) # Etiqueta tiempo restante

        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=100, mode="determinate", variable=self.progress_var)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        # Etiqueta de porcentaje centrada sobre la barra
        self.progress_percent_label = ttk.Label(progress_frame, textvariable=self.progress_percent_var, style="Progress.TLabel")
        # Usar place para centrarla respecto a la barra
        self.progress_percent_label.place(in_=self.progress_bar, relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.progress_percent_label.lift() # Asegurar que esté por encima de la barra

        self.elapsed_label = ttk.Label(progress_frame, textvariable=self.elapsed_time_var, width=20, anchor="w")
        self.elapsed_label.grid(row=0, column=1, sticky="w", padx=(0, 10))

        self.etr_label = ttk.Label(progress_frame, textvariable=self.etr_var, width=18, anchor="e")
        self.etr_label.grid(row=0, column=2, sticky="e")

        # --- Frame Log ---
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=5, pady=(5, 5))
        main_frame.rowconfigure(4, weight=1) # Hacer fila del log expandible
        log_frame.columnconfigure(0, weight=1) # Columna del log expandible
        log_frame.rowconfigure(1, weight=1) # Fila del ScrolledText expandible

        log_label = ttk.Label(log_frame, text="Registro de Proceso:")
        log_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.log_area = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.log_area.grid(row=1, column=0, sticky="nsew")

        # --- Carga Inicial y Configuración Final ---
        self.load_settings() # Carga la configuración usando la ruta CONFIG_FILE corregida

        # Asegurarse de que los combobox tengan un valor inicial si la carga falla o el archivo no existe
        if not self.tiff_compression_var.get():
            self.tiff_compression_var.set(tiff_compression_options.get(default_tiff_compression_flag))
        if not self.output_format_var.get():
            self.output_format_var.set(default_output_format_key)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing) # Guardar config al cerrar
        self.update_output_path_display() # Mostrar ruta de salida inicial

    # --- Métodos auxiliares GUI ---
    def create_margin_spinboxes_inline(self, parent_frame, margin_vars_dict, target_row):
        """Crea los spinboxes para márgenes en una fila."""
        spinboxes_widgets = {}
        keys_order = ['top', 'bottom', 'left', 'right']
        labels_text = {'top': 'Arriba:', 'bottom': 'Abajo:', 'left': 'Izquierda:', 'right': 'Derecha:'}
        current_col = 0
        column_weights = {} # Para distribuir espacio equitativamente

        for i, key in enumerate(keys_order):
            label_col = current_col
            ttk.Label(parent_frame, text=labels_text[key]).grid(row=target_row, column=label_col, padx=(5 if i > 0 else 0, 2), pady=1, sticky="e")
            current_col += 1

            spinbox_col = current_col
            spinbox_var = margin_vars_dict.get(key)
            if spinbox_var:
                spinbox = Spinbox(parent_frame, from_=0, to=9999, increment=1, textvariable=spinbox_var, width=6) # Ancho reducido
                spinbox.grid(row=target_row, column=spinbox_col, padx=(0, 10), pady=1, sticky="w")
                spinboxes_widgets[key] = spinbox
                # Asignar peso a la columna del spinbox para expansión
                parent_frame.columnconfigure(spinbox_col, weight=1)
            current_col += 1

        return spinboxes_widgets

    def select_input_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.input_folder_path.set(folder_selected)
            self.log_message(f"Carpeta Origen seleccionada: {folder_selected}\n")
            self.update_output_path_display() # Actualizar ruta salida al cambiar origen

    def update_output_path_display(self, *args):
        """Actualiza la etiqueta de la ruta de salida basada en la carpeta de entrada y el nombre."""
        input_dir = self.input_folder_path.get()
        output_name = self.output_folder_name_var.get().strip()
        # La carpeta de salida se crea al mismo nivel que la carpeta de entrada
        parent_dir = os.path.dirname(input_dir) if input_dir and os.path.isdir(input_dir) else None

        if parent_dir and output_name:
            # Construye la ruta completa de salida
            output_dir_path = os.path.join(parent_dir, output_name)
            self.output_folder_path.set(output_dir_path)
        elif input_dir:
            # Si hay carpeta de entrada pero no nombre de salida, indica que falta el nombre
            self.output_folder_path.set(f"<-- Falta Nombre Carpeta Salida (se creará en {os.path.dirname(input_dir)})")
        else:
            # Si no hay carpeta de entrada, limpia la ruta de salida
            self.output_folder_path.set("")

    def log_message(self, message):
        """Añade un mensaje al área de log de forma segura para hilos."""
        def _log():
            if self.log_area:
                try:
                    self.log_area.config(state=tk.NORMAL)
                    self.log_area.insert(tk.END, message)
                    self.log_area.see(tk.END) # Auto-scroll
                    self.log_area.config(state=tk.DISABLED)
                except tk.TclError as e:
                    # Puede ocurrir si la ventana se cierra mientras se loguea
                    print(f"Error logging to Tkinter widget: {e}")
        if self.root and self.log_area.winfo_exists(): # Verificar si la ventana y el widget existen
            try:
                self.root.after(0, _log) # Ejecutar en el hilo principal de Tkinter
            except tk.TclError:
                # La ventana podría estar destruyéndose
                pass

    def get_margins_from_gui(self):
        """Obtiene y valida los valores de los márgenes desde los Spinboxes."""
        margins_top = {}
        margins_bottom = {}
        try:
            for key, var in self.margins_top_vars.items():
                margins_top[key] = var.get()
            for key, var in self.margins_bottom_vars.items():
                margins_bottom[key] = var.get()

            # Validar que todos los márgenes sean no negativos
            all_margin_values = list(margins_top.values()) + list(margins_bottom.values())
            for val in all_margin_values:
                if val < 0:
                    raise ValueError("Los márgenes no pueden ser negativos.")
            return margins_top, margins_bottom
        except (ValueError, tk.TclError) as e:
            messagebox.showerror("Error de Entrada", f"Valor inválido en los márgenes: {e}. Por favor, introduce números enteros no negativos.")
            return None, None # Indicar fallo

    def get_compression_params_from_gui(self):
        """Obtiene los parámetros de compresión desde la GUI."""
        tiff_scheme_name = self.tiff_compression_var.get()
        # Busca el flag numérico correspondiente al nombre seleccionado
        tiff_flag = self.tiff_flag_map.get(tiff_scheme_name, default_tiff_compression_flag)
        return {
            'jpeg_quality': self.jpeg_quality_var.get(),
            'png_compression': self.png_compression_var.get(), # Aunque no se use mucho, lo incluimos
            'tiff_compression_flag': tiff_flag
        }

    # --- Métodos de Control de Progreso y Proceso ---
    def reset_progress(self):
        """Resetea la barra de progreso y los controles al iniciar."""
        self.cancel_event.clear() # Resetea el evento de cancelación
        self.progress_var.set(0.0)
        self.progress_percent_var.set("0%")
        self.elapsed_time_var.set("Transcurrido: 00:00")
        self.etr_var.set("Restante: Calculando...")
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        if self.root:
            self.root.update_idletasks() # Asegura que la GUI se actualice

    def update_progress(self, current_value, total_value, elapsed_time):
        """Actualiza la barra de progreso, porcentaje y tiempos estimados."""
        if total_value == 0: return # Evitar división por cero

        progress_percent = (current_value / total_value) * 100
        self.progress_var.set(progress_percent)
        self.progress_percent_var.set(f"{progress_percent:.0f}%")
        self.elapsed_time_var.set(f"Transcurrido: {format_time(elapsed_time)}")

        # Calcular Tiempo Estimado Restante (ETR)
        if current_value > 0 and current_value < total_value:
            time_per_item = elapsed_time / current_value
            remaining_items = total_value - current_value
            etr_seconds = time_per_item * remaining_items
            self.etr_var.set(f"Restante: {format_time(etr_seconds)}")
        elif current_value == 0 and total_value > 0:
            self.etr_var.set("Restante: Calculando...")
        else: # Proceso completado o total = 0
            self.etr_var.set("Restante: 00:00")

    def finalize_progress(self, start_time, was_cancelled=False):
        """Actualiza la GUI al finalizar el proceso (completado o cancelado)."""
        total_time = time.perf_counter() - start_time
        status_message = "Cancelado" if was_cancelled else "Completado"

        if not was_cancelled:
            self.progress_var.set(100.0)
            self.progress_percent_var.set("100%")
        # Si fue cancelado, el progreso se queda donde estaba

        self.elapsed_time_var.set(f"Transcurrido: {format_time(total_time)}")
        self.etr_var.set(f"{status_message} en: {format_time(total_time)}")
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        if self.root:
            self.root.update_idletasks() # Refrescar GUI

    def cancel_processing(self):
        """Establece el evento de cancelación."""
        if not self.cancel_event.is_set():
            self.log_message("--- Cancelación solicitada por el usuario ---\n")
            self.cancel_event.set()
            self.cancel_button.config(state=tk.DISABLED) # Deshabilitar botón tras pulsar

    # --- Métodos de Carga/Guardado de Configuración ---
    def load_settings(self):
        """Carga la configuración desde el archivo JSON."""
        self.log_message(f"Intentando cargar configuración desde: {CONFIG_FILE}\n")
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                    # Cargar cada valor, usando el valor por defecto si no existe en el archivo
                    self.output_folder_name_var.set(settings.get('output_folder_name', default_output_folder_name))
                    self.jpeg_quality_var.set(settings.get('jpeg_quality', default_jpeg_quality))
                    self.output_format_var.set(settings.get('output_format_key', default_output_format_key))
                    self.top_identifier_var.set(settings.get('top_identifier', default_top_identifier))
                    self.bottom_identifier_var.set(settings.get('bottom_identifier', default_bottom_identifier))

                    # Cargar compresión TIFF por nombre legible
                    saved_tiff_comp_name = settings.get('tiff_compression_name', tiff_compression_options.get(default_tiff_compression_flag))
                    if saved_tiff_comp_name in self.tiff_flag_map: # Verificar si el nombre es válido
                        self.tiff_compression_var.set(saved_tiff_comp_name)
                    else: # Usar valor por defecto si el nombre guardado no es válido
                        self.tiff_compression_var.set(tiff_compression_options.get(default_tiff_compression_flag))

                    # Cargar márgenes, usando valores por defecto si falta alguna clave
                    margins_top_saved = settings.get('margins_top', margins_top_files_default)
                    margins_bottom_saved = settings.get('margins_bottom', margins_bottom_files_default)
                    for key, var in self.margins_top_vars.items():
                        var.set(margins_top_saved.get(key, margins_top_files_default.get(key, 0))) # Fallback a 0 si todo falla
                    for key, var in self.margins_bottom_vars.items():
                        var.set(margins_bottom_saved.get(key, margins_bottom_files_default.get(key, 0)))

                    # Cargar última carpeta de entrada usada
                    self.input_folder_path.set(settings.get('last_input_folder', ''))

                    self.log_message("Configuración anterior cargada correctamente.\n")
            else:
                # El archivo de configuración no existe, usar valores por defecto (ya establecidos en las variables)
                self.log_message(f"Archivo de configuración no encontrado en '{CONFIG_FILE}'. Usando valores por defecto.\n")
                # Asegurarse de que los comboboxes tengan un valor por defecto explícito
                if not self.tiff_compression_var.get():
                    self.tiff_compression_var.set(tiff_compression_options.get(default_tiff_compression_flag))
                if not self.output_format_var.get():
                    self.output_format_var.set(default_output_format_key)

        except json.JSONDecodeError as e:
            self.log_message(f"Error al leer el archivo de configuración JSON: {e}\nEl archivo puede estar corrupto. Usando valores por defecto.\n")
            # Establecer valores por defecto explícitamente en caso de error de lectura
            self.set_defaults_after_load_error()
        except KeyError as e:
            self.log_message(f"Error: Falta la clave '{e}' en el archivo de configuración. Usando valores por defecto.\n")
            self.set_defaults_after_load_error()
        except Exception as e:
            self.log_message(f"Error inesperado al cargar configuración desde '{CONFIG_FILE}': {e}\nTipo de error: {type(e).__name__}\nUsando valores por defecto.\n")
            # traceback.print_exc() # Descomenta para ver traceback completo en consola si es necesario
            self.set_defaults_after_load_error()

    def set_defaults_after_load_error(self):
        """Función auxiliar para reestablecer defaults si la carga falla."""
        self.output_folder_name_var.set(default_output_folder_name)
        self.jpeg_quality_var.set(default_jpeg_quality)
        self.output_format_var.set(default_output_format_key)
        self.top_identifier_var.set(default_top_identifier)
        self.bottom_identifier_var.set(default_bottom_identifier)
        self.tiff_compression_var.set(tiff_compression_options.get(default_tiff_compression_flag))
        for key, var in self.margins_top_vars.items():
            var.set(margins_top_files_default.get(key, 0))
        for key, var in self.margins_bottom_vars.items():
            var.set(margins_bottom_files_default.get(key, 0))
        self.input_folder_path.set('') # Limpiar última carpeta

    def save_settings(self):
        """Guarda la configuración actual en el archivo JSON."""
        settings = {
            'output_folder_name': self.output_folder_name_var.get(),
            'jpeg_quality': self.jpeg_quality_var.get(),
            'output_format_key': self.output_format_var.get(),
            'top_identifier': self.top_identifier_var.get(),
            'bottom_identifier': self.bottom_identifier_var.get(),
            'tiff_compression_name': self.tiff_compression_var.get(), # Guardar nombre legible
            'margins_top': {key: var.get() for key, var in self.margins_top_vars.items()},
            'margins_bottom': {key: var.get() for key, var in self.margins_bottom_vars.items()},
            'last_input_folder': self.input_folder_path.get()
        }
        self.log_message(f"Intentando guardar configuración en: {CONFIG_FILE}\n")
        try:
            # Asegurarse de que el directorio exista (importante si la base es una ruta compleja)
            config_dir = os.path.dirname(CONFIG_FILE)
            if config_dir: # Solo crear si no es la raíz
                os.makedirs(config_dir, exist_ok=True)

            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                 json.dump(settings, f, indent=4, ensure_ascii=False) # ensure_ascii=False para UTF-8
            self.log_message("Configuración guardada correctamente.\n")
        except Exception as e:
            self.log_message(f"Error al guardar configuración en '{CONFIG_FILE}': {e}\nTipo de error: {type(e).__name__}\n")
            # Podrías mostrar un messagebox aquí si fallar al guardar es crítico
            # messagebox.showerror("Error Guardado", f"No se pudo guardar la configuración:\n{e}")

    def on_closing(self):
        """Se ejecuta al cerrar la ventana."""
        self.save_settings() # Intenta guardar la configuración
        self.root.destroy() # Cierra la aplicación

    # --- Lógica de Procesamiento Principal ---
    def start_processing_thread(self):
        """Valida las entradas e inicia el procesamiento en un hilo separado."""
        input_dir = self.input_folder_path.get()
        output_name = self.output_folder_name_var.get().strip()
        output_dir = self.output_folder_path.get() # Ruta completa calculada

        # --- Validaciones ---
        if not input_dir or not os.path.isdir(input_dir):
            messagebox.showwarning("Entrada Inválida", "Por favor, selecciona una carpeta de origen válida.")
            return
        if not output_name:
            messagebox.showwarning("Entrada Requerida", "Por favor, introduce un nombre para la carpeta de salida.")
            return
        if not output_dir or "<--" in output_dir: # Verificar si la ruta de salida es válida
            messagebox.showerror("Error de Configuración", "No se pudo determinar la ruta de la carpeta de salida. Verifica la carpeta de origen y el nombre de salida.")
            return
        if output_dir == input_dir:
             if not messagebox.askyesno("Confirmación", "La carpeta de salida es la misma que la de origen. Esto sobrescribirá archivos si los nombres coinciden. ¿Deseas continuar?"):
                 return

        margins_top, margins_bottom = self.get_margins_from_gui()
        if margins_top is None: return # Error ya mostrado por get_margins_from_gui

        compression_params = self.get_compression_params_from_gui()
        selected_output_format_key = self.output_format_var.get()
        selected_output_ext = output_formats.get(selected_output_format_key, ".jpg") # Fallback a jpg
        tiff_scheme_name = self.tiff_compression_var.get() # Nombre legible para log

        top_id = self.top_identifier_var.get().strip()
        bottom_id = self.bottom_identifier_var.get().strip()
        if not top_id and not bottom_id:
            messagebox.showwarning("Advertencia", "Debes proporcionar al menos un identificador ('Frente' o 'Reverso') para que el programa sepa qué márgenes aplicar.")
            return

        # --- Preparar e iniciar Hilo ---
        self.reset_progress()
        self.log_area.config(state=tk.NORMAL) # Limpiar log anterior
        self.log_area.delete('1.0', tk.END)
        self.log_area.config(state=tk.DISABLED)

        self.log_message("\n--- Iniciando Proceso de Recorte ---\n")
        self.log_message(f"Carpeta Origen: {input_dir}\n")
        self.log_message(f"Carpeta Salida: {output_dir}\n")
        self.log_message(f"Identificador 'Frente' ('{top_id}'): Márgenes={margins_top}\n")
        self.log_message(f"Identificador 'Reverso' ('{bottom_id}'): Márgenes={margins_bottom}\n")
        self.log_message(f"Formato de Salida: {selected_output_format_key}\n")
        self.log_message(f"Parámetros de Compresión:\n")
        self.log_message(f"  JPEG Calidad: {compression_params['jpeg_quality']} (Aplicable si salida=JPEG o TIFF/JPEG)\n")
        # self.log_message(f"  PNG Nivel: {compression_params['png_compression']} (Aplicable si salida=PNG)\n") # Opcional mostrar PNG
        self.log_message(f"  TIFF Esquema: {tiff_scheme_name} (Flag={compression_params['tiff_compression_flag']}) (Aplicable si salida=TIFF)\n")

        self.save_settings() # Guardar configuración antes de empezar

        # Crear y lanzar el hilo de procesamiento
        processing_thread = threading.Thread(
            target=self.run_batch_crop_recursive,
            args=(input_dir, output_dir, margins_top, margins_bottom, compression_params, selected_output_ext, top_id, bottom_id),
            daemon=True # Permite cerrar la app aunque el hilo esté corriendo
        )
        processing_thread.start()

    def run_batch_crop_recursive(self, input_base_dir, output_base_dir, margins_top, margins_bottom, compression_params, selected_output_ext, top_identifier, bottom_identifier):
        """Realiza el recorte de imágenes recursivamente."""
        thread_start_time = time.perf_counter()
        was_cancelled = False
        processed_count, skipped_count, error_count = 0, 0, 0
        total_read_time, total_process_time, total_write_time = 0.0, 0.0, 0.0
        num_files = 0
        files_to_process_list = []

        # 1. Encontrar todos los archivos válidos recursivamente
        self.log_message("Buscando archivos de imagen válidos (recursivamente)...\n")
        try:
            for current_dir_path, _, filenames in os.walk(input_base_dir):
                # Omitir la propia carpeta de salida si está dentro de la de entrada
                if os.path.normpath(current_dir_path).startswith(os.path.normpath(output_base_dir)):
                    self.log_message(f"  Omitiendo subdirectorio de salida: {current_dir_path}\n")
                    continue

                for filename in filenames:
                    # Comprobar extensión en minúsculas
                    if filename.lower().endswith(valid_extensions):
                        files_to_process_list.append(os.path.join(current_dir_path, filename))
        except OSError as e:
            self.log_message(f"Error fatal al buscar archivos en '{input_base_dir}': {e}\n")
            self.root.after(0, lambda: messagebox.showerror("Error de Búsqueda", f"No se pudo recorrer la carpeta de origen:\n{e}"))
            self.root.after(0, self.finalize_progress, thread_start_time, False) # Finalizar indicando no cancelado (error)
            return

        num_files = len(files_to_process_list)
        if not files_to_process_list:
            self.log_message("No se encontraron archivos de imagen con extensiones válidas en la carpeta de origen.\n")
            self.root.after(0, self.finalize_progress, thread_start_time, False)
            return
        else:
            self.log_message(f"Se encontraron {num_files} archivos de imagen para procesar.\n")
            # Actualizar progreso inicial (0 de num_files)
            self.root.after(0, self.update_progress, 0, num_files, 0)

        # 2. Procesar cada archivo encontrado
        file_index = 0
        try:
            for input_file_path in files_to_process_list:
                if self.cancel_event.is_set():
                    was_cancelled = True
                    self.log_message(f"\n--- Cancelado por el usuario antes de procesar '{os.path.basename(input_file_path)}' ---\n")
                    break # Salir del bucle for

                # Calcular ruta de salida manteniendo estructura de subdirectorios
                relative_path_dir = os.path.relpath(os.path.dirname(input_file_path), input_base_dir)
                output_subdir = os.path.join(output_base_dir, relative_path_dir) if relative_path_dir != '.' else output_base_dir

                # Crear directorio de salida si no existe
                try:
                    if not os.path.exists(output_subdir):
                        os.makedirs(output_subdir, exist_ok=True)
                        self.log_message(f"  Directorio creado: {output_subdir}\n")
                except OSError as make_err:
                    self.log_message(f"!! Error Crítico: No se pudo crear el directorio de salida '{output_subdir}': {make_err}. Omitiendo archivo.\n")
                    error_count += 1
                    file_index += 1
                    elapsed_thread_time = time.perf_counter()-thread_start_time
                    self.root.after(0, self.update_progress, file_index, num_files, elapsed_thread_time)
                    continue # Pasar al siguiente archivo

                # Construir nombre y ruta de archivo de salida
                base_name, _ = os.path.splitext(os.path.basename(input_file_path))
                output_filename = base_name + selected_output_ext
                output_file_path = os.path.normpath(os.path.join(output_subdir, output_filename))

                # Log más corto para la ruta relativa
                log_display_path_in = os.path.relpath(input_file_path, input_base_dir)
                log_display_path_out = os.path.relpath(output_file_path, os.path.dirname(output_base_dir)) # Relativa al padre de la carpeta de salida

                self.log_message(f"[{file_index+1}/{num_files}] Procesando: '{log_display_path_in}' -> '{log_display_path_out}'...")

                # Determinar qué márgenes usar basado en el identificador en el nombre de archivo
                filename_for_margins = os.path.basename(input_file_path)
                current_margins = None
                margin_id_used = "Ninguno"
                if top_identifier and top_identifier in filename_for_margins:
                    current_margins = margins_top
                    margin_id_used = f"Frente ('{top_identifier}')"
                    self.log_message(f" (ID: {margin_id_used})")
                elif bottom_identifier and bottom_identifier in filename_for_margins:
                    current_margins = margins_bottom
                    margin_id_used = f"Reverso ('{bottom_identifier}')"
                    self.log_message(f" (ID: {margin_id_used})")

                # Si no se encontró identificador, omitir el archivo
                if current_margins is None:
                    self.log_message(" omitido (ningún identificador coincide).\n")
                    skipped_count += 1
                else:
                    # Llamar a la función de recorte
                    success, t_read, t_proc, t_write = crop_image_with_margins(
                        input_file_path,
                        output_file_path,
                        current_margins,
                        compression_params,
                        self.log_message # Pasar la función de log para mensajes internos
                    )

                    # Acumular tiempos
                    total_read_time += t_read
                    total_process_time += t_proc
                    total_write_time += t_write

                    # Contar resultados
                    if success:
                        processed_count += 1
                        size_info = ""
                        try:
                            # Calcular info de tamaño (opcional)
                            if os.path.exists(output_file_path):
                                input_size_bytes = os.path.getsize(input_file_path)
                                output_size_bytes = os.path.getsize(output_file_path)
                                input_size_kb = input_size_bytes / 1024
                                output_size_kb = output_size_bytes / 1024
                                reduction = 100 * (1 - output_size_bytes / input_size_bytes) if input_size_bytes > 0 else 0
                                size_info = f" ({output_size_kb:.1f}kB, Reducción: {reduction:.1f}%)"
                        except OSError as e:
                            size_info = f" (Error al obtener tamaño: {e.strerror})"
                        self.log_message(f" ¡OK!{size_info}\n")
                    else:
                        # El error ya fue logueado dentro de crop_image_with_margins
                        error_count += 1
                        self.log_message(f" ¡ERROR! (ver detalles arriba)\n") # Mensaje resumido

                # Actualizar progreso después de procesar cada archivo
                file_index += 1
                elapsed_thread_time = time.perf_counter() - thread_start_time
                self.root.after(0, self.update_progress, file_index, num_files, elapsed_thread_time)

        except Exception as e:
            # Captura errores inesperados durante el bucle de procesamiento
            was_cancelled = self.cancel_event.is_set() # Verificar si el error fue por cancelación
            self.log_message(f"\n!!! Error General Inesperado durante el Procesamiento: {e} !!!\n")
            self.log_message(f"Tipo de Error: {type(e).__name__}\n")
            self.log_message(f"Traceback: {traceback.format_exc()}\n")
            # Mostrar error grave al usuario
            self.root.after(0, lambda: messagebox.showerror("Error Grave en Procesamiento", f"Ocurrió un error inesperado:\n{e}\n\nConsulte el registro para más detalles."))
        finally:
            # 3. Finalizar y mostrar resumen (siempre se ejecuta)
            final_status = "--- Proceso Cancelado ---\n" if was_cancelled else "--- Proceso Finalizado ---\n"
            self.log_message(f"\n{final_status}")
            self.log_message(f"Resumen:\n")
            self.log_message(f"  - Archivos Procesados Correctamente: {processed_count}\n")
            self.log_message(f"  - Archivos Omitidos (sin identificador): {skipped_count}\n")
            self.log_message(f"  - Archivos con Errores: {error_count}\n")
            self.log_message(f"  - Total Archivos Encontrados: {num_files}\n")

            # Mostrar tiempos promedio si se procesó al menos uno
            if processed_count > 0:
                avg_read = total_read_time / processed_count
                avg_proc = total_process_time / processed_count
                avg_write = total_write_time / processed_count
                self.log_message(f"Tiempos Promedio por Archivo Procesado (segundos):\n")
                self.log_message(f"  - Lectura: {avg_read:.3f}\n")
                self.log_message(f"  - Procesamiento (recorte/conversión): {avg_proc:.3f}\n")
                self.log_message(f"  - Escritura: {avg_write:.3f}\n")

            # Actualizar la GUI para reflejar el estado final
            self.root.after(0, self.finalize_progress, thread_start_time, was_cancelled)

# --- EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":
    root = tk.Tk()
    app = BatchCropperApp(root)
    root.mainloop()