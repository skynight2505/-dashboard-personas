import os
import sys
import subprocess

# Ensure we're in the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Try to install dependencies if needed
try:
    import fastapi
except ImportError:
    print("Instalando dependencias...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    )

import uvicorn
from main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Iniciando servidor en puerto {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
