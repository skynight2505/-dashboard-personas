import pandas as pd
import logging
import re

logger = logging.getLogger(__name__)

COLUMNAS_CEDULA = re.compile(r"\b(cedula|cedula_identidad|identificacion|documento|id|dni|c\.i\.|ci)\b", re.IGNORECASE)
COLUMNAS_NOMBRE = re.compile(r"\b(nombre|nombre_completo|apellido|nombres|nom|name|fullname)\b", re.IGNORECASE)


def procesar_excel(ruta_archivo: str) -> list[dict]:
    try:
        dfs = pd.read_excel(ruta_archivo, sheet_name=None, dtype=str)
    except Exception as e:
        logger.error(f"Error al leer Excel {ruta_archivo}: {e}")
        raise

    personas = []
    for nombre_hoja, df in dfs.items():
        df = df.fillna("")
        columnas = [str(c).lower().strip() for c in df.columns]

        col_cedula = None
        col_nombre = None

        for i, col in enumerate(columnas):
            if COLUMNAS_CEDULA.search(col):
                col_cedula = df.columns[i]
            if COLUMNAS_NOMBRE.search(col):
                col_nombre = df.columns[i]

        if len(df.columns) >= 2:
            if col_nombre is None:
                col_nombre = df.columns[0]
            if col_cedula is None:
                col_cedula = df.columns[1]

        for _, row in df.iterrows():
            nombre = str(row.get(col_nombre, "")).strip() if col_nombre else ""
            cedula = str(row.get(col_cedula, "")).strip() if col_cedula else ""

            if not nombre or nombre == "nan" or len(nombre) < 3:
                continue
            if cedula == "nan":
                cedula = ""
            if cedula:
                cedula = re.sub(r"[^a-zA-Z0-9]", "", cedula)

            personas.append({
                "nombre_completo": nombre,
                "cedula": cedula if cedula else None
            })

    return personas
