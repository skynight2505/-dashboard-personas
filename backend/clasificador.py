import re
import logging
from models import CategoriaPersona

logger = logging.getLogger(__name__)

PALABRAS_FALLECIDO = re.compile(
    r"\b(fallecid[oa]s?|murió|muert[oa]s?|cadáver|sin\s*vida|occis[oa]|"
    r"finad[oa]|difunt[oa]|deceso|exequias|velatori[oa]|"
    r"levantamiento\s*de\s*cadáver|necropsia|autopsia)\b",
    re.IGNORECASE
)

PALABRAS_VIVO = re.compile(
    r"\b(hospitalizad[oa]|herid[oa]s?|lesionad[oa]s?|atendid[oa]s?|"
    r"ingresad[oa]s?|hospital|clínica|trasladad[oa]s?|"
    r"v[ií]ctima\s*con\s*vida|sobreviviente|"
    r"recibe\s*alta|estable|recuperándos[ea])\b",
    re.IGNORECASE
)

PALABRAS_DESAPARECIDO = re.compile(
    r"\b(desaparecid[oa]s?|paradero|no\s*localizad[oa]|"
    r"b[úu]squeda|extraviad[oa]s?|no\s*aparic[ei]ó|"
    r"se\s*desconoce\s*su\s*paradero|ausente|"
    r"reportad[oa]\s*como\s*desaparecid[oa])\b",
    re.IGNORECASE
)


def clasificar_por_archivo(nombre_archivo: str, texto_contenido: str = "") -> CategoriaPersona:
    nombre_lower = nombre_archivo.lower()
    texto = nombre_lower + " " + texto_contenido.lower()

    if PALABRAS_FALLECIDO.search(texto):
        return CategoriaPersona.fallecido

    if PALABRAS_VIVO.search(texto):
        return CategoriaPersona.vivo_sitio_actual

    if PALABRAS_DESAPARECIDO.search(texto):
        return CategoriaPersona.desaparecido

    if "hospital" in texto or "clínica" in texto or "heridos" in texto:
        return CategoriaPersona.vivo_sitio_actual

    return CategoriaPersona.desaparecido
