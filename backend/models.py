from sqlalchemy import Column, Integer, String, DateTime, JSON, Enum as SAEnum
from sqlalchemy.sql import func
import enum

from database import Base


class CategoriaPersona(str, enum.Enum):
    vivo_sitio_actual = "vivo_sitio_actual"
    desaparecido = "desaparecido"
    fallecido = "fallecido"


class Persona(Base):
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True)
    cedula = Column(String(50), index=True, nullable=True)
    nombre_completo = Column(String(300), index=True)
    categoria = Column(SAEnum(CategoriaPersona), default=CategoriaPersona.desaparecido)
    fuente_documento = Column(String(300))
    url_fuente = Column(String(500), nullable=True)
    metadatos_fuente = Column(JSON, nullable=True)
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())
    datos_extra = Column(JSON, nullable=True)
