import os
import io
import json
import base64
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from models import CategoriaPersona

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service-account.json")

MAPA_CARPETAS = {
    "vivo": CategoriaPersona.vivo_sitio_actual,
    "vivos": CategoriaPersona.vivo_sitio_actual,
    "hospital": CategoriaPersona.vivo_sitio_actual,
    "heridos": CategoriaPersona.vivo_sitio_actual,
    "desaparecido": CategoriaPersona.desaparecido,
    "desaparecidos": CategoriaPersona.desaparecido,
    "extraviados": CategoriaPersona.desaparecido,
    "fallecido": CategoriaPersona.fallecido,
    "fallecidos": CategoriaPersona.fallecido,
    "muertos": CategoriaPersona.fallecido,
    "occisos": CategoriaPersona.fallecido,
}

EXTENSIONES_PERMITIDAS = {".pdf", ".xlsx", ".xls", ".docx"}
PROCESADORES = {}


def autenticar_drive():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        try:
            creds_dict = json.loads(base64.b64decode(creds_json).decode())
            creds = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=SCOPES
            )
            return build("drive", "v3", credentials=creds)
        except Exception as e:
            logger.error(f"Error autenticando desde env var: {e}")

    if os.path.exists(SERVICE_ACCOUNT_FILE):
        try:
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES
            )
            return build("drive", "v3", credentials=creds)
        except Exception as e:
            logger.error(f"Error autenticando con service account: {e}")
            return None

    logger.error(
        "No se encontro service-account.json ni GOOGLE_CREDENTIALS_JSON. "
        "Descargalo desde Google Cloud Console > IAM & Admin > Service Accounts "
        "y guardalo en backend/service-account.json"
    )
    return None


def obtener_id_carpeta_raiz(service, nombre_carpeta: str) -> str | None:
    query = f"name='{nombre_carpeta}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)", pageSize=10).execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def listar_subcarpetas(service, folder_id: str) -> list[dict]:
    query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    return results.get("files", [])


def listar_archivos_en_carpeta(service, folder_id: str) -> list[dict]:
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    return results.get("files", [])


def descargar_archivo(service, file_id: str, nombre: str) -> bytes | None:
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue()
    except Exception as e:
        logger.error(f"Error descargando {nombre} (id={file_id}): {e}")
        return None


def sincronizar_desde_drive(
    nombre_carpeta_raiz: str = "DashboardPersonas",
) -> list[dict]:
    from procesadores.pdf_processor import procesar_pdf
    from procesadores.excel_processor import procesar_excel
    from procesadores.word_processor import procesar_word

    PROCESADORES[".pdf"] = procesar_pdf
    PROCESADORES[".xlsx"] = procesar_excel
    PROCESADORES[".xls"] = procesar_excel
    PROCESADORES[".docx"] = procesar_word

    service = autenticar_drive()
    if not service:
        return []

    carpeta_raiz_id = obtener_id_carpeta_raiz(service, nombre_carpeta_raiz)
    if not carpeta_raiz_id:
        logger.warning(f"Carpeta raiz '{nombre_carpeta_raiz}' no encontrada en Drive.")
        return []

    subcarpetas = listar_subcarpetas(service, carpeta_raiz_id)
    if not subcarpetas:
        logger.warning(f"No hay subcarpetas dentro de '{nombre_carpeta_raiz}'.")

    todos_registros = []

    for subcarpeta in subcarpetas:
        nombre_sub = subcarpeta["name"].lower().strip()
        categoria = MAPA_CARPETAS.get(nombre_sub)

        if not categoria:
            logger.info(f"Carpeta '{subcarpeta['name']}' no coincide con ninguna categoria. Se ignorara.")
            continue

        archivos = listar_archivos_en_carpeta(service, subcarpeta["id"])
        logger.info(f"Carpeta '{subcarpeta['name']}' -> {len(archivos)} archivo(s)")

        for archivo in archivos:
            nombre_archivo = archivo["name"]
            ext = os.path.splitext(nombre_archivo)[1].lower()
            if ext not in EXTENSIONES_PERMITIDAS:
                continue

            contenido = descargar_archivo(service, archivo["id"], nombre_archivo)
            if not contenido:
                continue

            ruta_temp = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "uploads",
                f"drive_{archivo['id']}{ext}"
            )
            with open(ruta_temp, "wb") as f:
                f.write(contenido)

            try:
                procesador = PROCESADORES[ext]
                personas = procesador(ruta_temp)
            except Exception as e:
                logger.error(f"Error procesando {nombre_archivo}: {e}")
                if os.path.exists(ruta_temp):
                    os.remove(ruta_temp)
                continue

            if os.path.exists(ruta_temp):
                os.remove(ruta_temp)

            for p in personas:
                p["categoria"] = categoria.value
                p["fuente_documento"] = nombre_archivo

            todos_registros.extend(personas)

    return todos_registros
