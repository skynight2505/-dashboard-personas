# Dashboard de Personas

Sistema de gestion de personas con clasificacion automatica (vivo/sitio actual, desaparecido, fallecido).
Procesa documentos PDF, Excel y Word desde Google Drive o carga directa.

## Stack

- Backend: Python + FastAPI
- Base de datos: PostgreSQL (produccion) / SQLite (local)
- Frontend: HTML + CSS + JS vanilla
- Dashboard: Google Looker Studio
- Despliegue: Render

## Estructura

```
backend/
  main.py              API REST
  database.py          Conexion BD
  models.py            Modelo Persona
  schemas.py           Validacion
  clasificador.py      Clasificacion automatica
  drive_watcher.py     Sincronizacion Google Drive
  procesadores/
    pdf_processor.py   Lectura de PDFs
    excel_processor.py Lectura de Excel
    word_processor.py  Lectura de Word
frontend/
  index.html           Interfaz web
  css/style.css        Estilos
  js/app.js            Logica frontend
render.yaml            Configuracion Render
```

## Instalacion Local

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload
```

Abrir http://localhost:8000

## Paso 1: Google Drive

1. Ir a https://console.cloud.google.com/ → Nuevo Proyecto
2. Habilitar Google Drive API
3. Crear Service Account (IAM & Admin → Service Accounts)
4. Descargar clave JSON como `backend/service-account.json`
5. Crear en Drive la carpeta `DashboardPersonas`
6. Dentro, crear subcarpetas: `Vivos`, `Desaparecidos`, `Fallecidos`
7. Compartir `DashboardPersonas` con el email de la service account (Lector)

## Paso 2: Render (Produccion)

1. Subir proyecto a GitHub
2. En render.com → New Web Service → conectar repo
3. Render detectara `render.yaml` automaticamente
4. Agregar variable de entorno:
   - Key: `GOOGLE_CREDENTIALS_JSON`
   - Value: el contenido de `service-account.json` codificado en base64
5. Hacer deploy

### Codificar service-account a base64:

```bash
# Linux/Mac:
cat backend/service-account.json | base64

# Windows PowerShell:
[Convert]::ToBase64String([IO.File]::ReadAllBytes("backend\service-account.json"))
```

## Paso 3: Google Looker Studio

1. Ir a https://lookerstudio.google.com/
2. Crear → Informe en blanco
3. Agregar datos → Conector JSON/API → pegar URL:
   `https://TU-SERVICIO.onrender.com/api/export`
4. Looker Studio detectara automaticamente los campos
5. Crear tabla, graficos y filtros
