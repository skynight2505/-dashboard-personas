import fitz
import re
import logging

logger = logging.getLogger(__name__)


def extraer_texto_pdf(ruta_archivo: str) -> str:
    texto_completo = ""
    try:
        doc = fitz.open(ruta_archivo)
        for pagina in doc:
            texto_completo += pagina.get_text()
        doc.close()
    except Exception as e:
        logger.error(f"Error al procesar PDF {ruta_archivo}: {e}")
        raise
    return texto_completo


PATRON_CEDULA = re.compile(r"\b(\d{1,2}\.?\d{3}\.?\d{3}-?\d|[A-Za-z]-\d{1,2}\.?\d{3}\.?\d{3})\b")
PATRON_NOMBRE = re.compile(r"^([A-ZÁÉÍÓÚÑa-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+){1,6})")

# Patrones flexibles: cédula seguido de nombre, o nombre seguido de cédula
PATRON_CEDULA_NOMBRE = re.compile(
    r"(\d{1,2}\.?\d{3}\.?\d{3}-?\d?)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,5})"
)
PATRON_NOMBRE_CEDULA = re.compile(
    r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,5})\s+(\d{1,2}\.?\d{3}\.?\d{3}-?\d?)"
)


def extraer_personas_desde_texto(texto: str) -> list[dict]:
    personas = []
    lineas = texto.split("\n")
    for linea in lineas:
        linea = linea.strip()
        if not linea or len(linea) < 5:
            continue

        cedula = None
        nombre = None

        match_ced_nom = PATRON_CEDULA_NOMBRE.search(linea)
        if match_ced_nom:
            cedula = match_ced_nom.group(1).replace(".", "").replace("-", "").strip()
            nombre = match_ced_nom.group(2).strip()
            if nombre and cedula:
                personas.append({"cedula": cedula, "nombre_completo": nombre})
                continue

        match_nom_ced = PATRON_NOMBRE_CEDULA.search(linea)
        if match_nom_ced:
            nombre = match_nom_ced.group(1).strip()
            cedula = match_nom_ced.group(2).replace(".", "").replace("-", "").strip()
            if nombre and cedula:
                personas.append({"cedula": cedula, "nombre_completo": nombre})
                continue

        cedula_match = PATRON_CEDULA.search(linea)
        if cedula_match:
            cedula_raw = cedula_match.group(1).replace(".", "").replace("-", "").strip()
            resto = linea.replace(cedula_match.group(1), "").strip()
            if resto and len(resto) > 3:
                personas.append({
                    "cedula": cedula_raw,
                    "nombre_completo": resto
                })

    return personas


def procesar_pdf(ruta_archivo: str) -> list[dict]:
    texto = extraer_texto_pdf(ruta_archivo)
    return extraer_personas_desde_texto(texto)
