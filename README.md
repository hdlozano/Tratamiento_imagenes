# Recortador de Imágenes

Aplicación de escritorio en Python para recortar imágenes por lotes aplicando
márgenes en píxeles según el identificador presente en el nombre del archivo.

## Estructura

```text
recortador/
├─ app.py                 # Arranque de la aplicación
├─ config.py              # Valores por defecto y rutas
├─ models/
│  ├─ settings.py         # Configuración y persistencia JSON
│  ├─ cropping.py         # Recorte, conversión y guardado con OpenCV
│  └─ batch.py            # Recorrido y procesamiento por lotes
├─ controllers/
│  └─ batch_controller.py # Coordinación vista-modelo e hilos
├─ views/
│  └─ main_window.py      # Interfaz Tkinter
└─ utils/
   └─ time_utils.py       # Formato de tiempos
```

La aplicación sigue una separación MVC:

- **Modelo:** lógica de recorte, recorrido de carpetas y configuración.
- **Vista:** widgets Tkinter, sin lógica de negocio ni hilos.
- **Controlador:** valida entradas, lanza el procesamiento y actualiza la UI.

## Requisitos

- Python 3.10 o superior
- OpenCV (`opencv-python`)
- NumPy
- Tkinter (incluido normalmente con Python en Windows)

## Ejecución

Desde la raíz del proyecto:

```powershell
python recorte.py
```

También se puede ejecutar como módulo:

```powershell
python -m recortador
```

## Configuración

La aplicación guarda sus preferencias en `recortador_config.json`, ubicado junto
al script o junto al ejecutable cuando está empaquetado. Incluye:

- Carpeta de salida, calidad JPEG y compresión TIFF.
- Identificadores de frente/reverso y sus márgenes.
- Última carpeta de origen utilizada.

## Empaquetado

Con PyInstaller instalado:

```powershell
pyinstaller packaging/recorte.spec
```

El ejecutable se genera en `dist/recorte.exe`.

## Versiones anteriores

Las variantes antiguas `recorte_gui.py` y `recortef_guy.py` se conservan en
`legacy/` como referencia y no forman parte de la aplicación actual.
