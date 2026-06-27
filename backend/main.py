import os
import sys
import uuid
import logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import engine, get_db, Base
from models import Persona, CategoriaPersona
from schemas import PersonaResponse, PersonaUpdate, StatsResponse, UploadResponse
from clasificador import clasificar_por_archivo
from procesadores.pdf_processor import procesar_pdf
from procesadores.excel_processor import procesar_excel
from procesadores.word_processor import procesar_word
from drive_watcher import sincronizar_desde_drive

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.warning(f"No se pudo crear la BD al iniciar: {e}")

app = FastAPI(title="Dashboard de Personas API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

if os.path.exists(FRONTEND_DIR):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")

EXTENSIONES_PERMITIDAS = {".pdf", ".xlsx", ".xls", ".docx"}

PROCESADORES = {
    ".pdf": procesar_pdf,
    ".xlsx": procesar_excel,
    ".xls": procesar_excel,
    ".docx": procesar_word,
}


def _obtener_personas_por_texto(db: Session, texto_busqueda: str):
    query = db.query(Persona)
    terminos = texto_busqueda.strip().split()
    for termino in terminos:
        query = query.filter(
            (Persona.nombre_completo.ilike(f"%{termino}%")) |
            (Persona.cedula.ilike(f"%{termino}%"))
        )
    return query.all()


@app.get("/")
def servir_frontend():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend no encontrado"}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_archivos(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    registros_totales = []
    personas_creadas = []

    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in EXTENSIONES_PERMITIDAS:
            raise HTTPException(
                status_code=400,
                detail=f"Formato no soportado: {ext}. Use PDF, Excel (.xlsx/.xls) o Word (.docx)"
            )

        contenido_bytes = await file.read()
        nombre_uuid = f"{uuid.uuid4()}{ext}"
        ruta_temp = os.path.join(UPLOAD_DIR, nombre_uuid)
        with open(ruta_temp, "wb") as f:
            f.write(contenido_bytes)

        try:
            procesador = PROCESADORES[ext]
            personas_extraidas = procesador(ruta_temp)
        except Exception as e:
            logger.error(f"Error procesando {file.filename}: {e}")
            os.remove(ruta_temp)
            raise HTTPException(status_code=500, detail=f"Error procesando {file.filename}: {str(e)}")

        os.remove(ruta_temp)

        if not personas_extraidas:
            continue

        texto_contenido = ""
        if ext == ".pdf":
            from procesadores.pdf_processor import extraer_texto_pdf
            try:
                texto_contenido = extraer_texto_pdf(ruta_temp)
                os.remove(ruta_temp) if os.path.exists(ruta_temp) else None
            except Exception:
                pass

        categoria = clasificar_por_archivo(file.filename, texto_contenido)

        for p in personas_extraidas:
            existing = None
            if p.get("cedula"):
                existing = db.query(Persona).filter(
                    Persona.cedula == p["cedula"]
                ).first()

            if existing:
                if existing.categoria != categoria:
                    existing.categoria = categoria
                continue

            persona = Persona(
                cedula=p.get("cedula"),
                nombre_completo=p["nombre_completo"],
                categoria=categoria,
                fuente_documento=file.filename,
            )
            db.add(persona)
            db.flush()
            personas_creadas.append(persona)

        registros_totales.extend(personas_extraidas)

    db.commit()
    for p in personas_creadas:
        db.refresh(p)

    return UploadResponse(
        message=f"Procesados {len(files)} archivo(s). {len(personas_creadas)} persona(s) agregada(s).",
        registros_agregados=len(personas_creadas),
        registros=[PersonaResponse.model_validate(p) for p in personas_creadas]
    )


@app.get("/api/personas", response_model=list[PersonaResponse])
def listar_personas(
    q: str = Query(None, description="Búsqueda por nombre o cédula"),
    categoria: str = Query(None, description="Filtrar por categoría"),
    db: Session = Depends(get_db)
):
    query = db.query(Persona)

    if q:
        query = query.filter(
            (Persona.nombre_completo.ilike(f"%{q}%")) |
            (Persona.cedula.ilike(f"%{q}%"))
        )

    if categoria:
        try:
            cat_enum = CategoriaPersona(categoria)
            query = query.filter(Persona.categoria == cat_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Categoría inválida: {categoria}")

    query = query.order_by(Persona.fecha_registro.desc())
    personas = query.all()
    return [PersonaResponse.model_validate(p) for p in personas]


@app.get("/api/personas/{persona_id}", response_model=PersonaResponse)
def obtener_persona(persona_id: int, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return PersonaResponse.model_validate(persona)


@app.put("/api/personas/{persona_id}", response_model=PersonaResponse)
def actualizar_persona(persona_id: int, datos: PersonaUpdate, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    if datos.categoria is not None:
        try:
            persona.categoria = CategoriaPersona(datos.categoria)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Categoría inválida: {datos.categoria}")
    if datos.nombre_completo is not None:
        persona.nombre_completo = datos.nombre_completo
    if datos.cedula is not None:
        persona.cedula = datos.cedula

    db.commit()
    db.refresh(persona)
    return PersonaResponse.model_validate(persona)


@app.delete("/api/personas/{persona_id}")
def eliminar_persona(persona_id: int, db: Session = Depends(get_db)):
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    db.delete(persona)
    db.commit()
    return {"message": "Persona eliminada correctamente"}


@app.get("/api/stats", response_model=StatsResponse)
def obtener_stats(db: Session = Depends(get_db)):
    total = db.query(Persona).count()
    vivos = db.query(Persona).filter(Persona.categoria == CategoriaPersona.vivo_sitio_actual).count()
    desaparecidos = db.query(Persona).filter(Persona.categoria == CategoriaPersona.desaparecido).count()
    fallecidos = db.query(Persona).filter(Persona.categoria == CategoriaPersona.fallecido).count()
    return StatsResponse(
        total=total,
        vivos=vivos,
        desaparecidos=desaparecidos,
        fallecidos=fallecidos
    )


@app.post("/api/drive/sync")
def sincronizar_drive(
    carpeta_raiz: str = Query("DashboardPersonas", description="Nombre de la carpeta raíz en Drive"),
    db: Session = Depends(get_db)
):
    try:
        registros = sincronizar_desde_drive(nombre_carpeta_raiz=carpeta_raiz)
    except Exception as e:
        logger.error(f"Error en sincronización Drive: {e}")
        raise HTTPException(status_code=500, detail=f"Error sincronizando Drive: {str(e)}")

    if not registros:
        return {"message": "No se encontraron archivos nuevos en Drive.", "registros_agregados": 0}

    personas_creadas = []
    for p in registros:
        existing = None
        if p.get("cedula"):
            existing = db.query(Persona).filter(Persona.cedula == p["cedula"]).first()
        if existing:
            if existing.categoria.value != p.get("categoria"):
                existing.categoria = CategoriaPersona(p["categoria"])
            continue

        persona = Persona(
            cedula=p.get("cedula"),
            nombre_completo=p["nombre_completo"],
            categoria=CategoriaPersona(p.get("categoria", "desaparecido")),
            fuente_documento=p.get("fuente_documento", ""),
        )
        db.add(persona)
        db.flush()
        personas_creadas.append(persona)

    db.commit()
    return {
        "message": f"Sincronización completada. {len(personas_creadas)} persona(s) agregada(s) desde Drive.",
        "registros_agregados": len(personas_creadas)
    }


@app.get("/api/export")
def exportar_datos(db: Session = Depends(get_db)):
    personas = db.query(Persona).order_by(Persona.nombre_completo).all()
    return [
        {
            "id": p.id,
            "cedula": p.cedula or "",
            "nombre_completo": p.nombre_completo,
            "categoria": p.categoria.value,
            "fuente_documento": p.fuente_documento,
            "fecha_registro": p.fecha_registro.isoformat() if p.fecha_registro else None,
        }
        for p in personas
    ]


@app.post("/api/personas/bulk-categoria")
def actualizar_categoria_masiva(
    ids: list[int],
    categoria: str,
    db: Session = Depends(get_db)
):
    try:
        cat_enum = CategoriaPersona(categoria)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Categoría inválida: {categoria}")

    actualizados = db.query(Persona).filter(Persona.id.in_(ids)).update(
        {"categoria": cat_enum}, synchronize_session=False
    )
    db.commit()
    return {"message": f"{actualizados} persona(s) actualizada(s)"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
