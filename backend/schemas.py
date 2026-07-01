from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class PersonaBase(BaseModel):
    cedula: Optional[str] = None
    nombre_completo: str
    categoria: str = "desaparecido"
    fuente_documento: Optional[str] = None
    url_fuente: Optional[str] = None
    metadatos_fuente: Optional[dict] = None
    datos_extra: Optional[dict] = None


class PersonaCreate(PersonaBase):
    pass


class PersonaUpdate(BaseModel):
    categoria: Optional[str] = None
    nombre_completo: Optional[str] = None
    cedula: Optional[str] = None



class PersonaResponse(PersonaBase):
    id: int
    fecha_registro: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    total: int
    vivos: int
    desaparecidos: int
    fallecidos: int


class UploadResponse(BaseModel):
    message: str
    registros_agregados: int
    registros: list[PersonaResponse]
