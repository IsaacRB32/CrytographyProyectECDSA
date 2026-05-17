# backend/database.py
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from pathlib import Path

# Buscamos la raíz del proyecto de forma absoluta basada en la ubicación de este archivo
# __file__ es backend/database.py -> .parent es backend/ -> .parent.parent es ProyectoCryptography/
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / ".env"

# Cargamos el archivo .env garantizando la ruta exacta
load_dotenv(dotenv_path=dotenv_path)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """
    Establece y retorna una conexión activa a la base de datos de PostgreSQL en Render.
    """
    try:
        if not DATABASE_URL:
            raise ValueError("❌ La variable DATABASE_URL está vacía. Revisa que el archivo .env exista en la raíz.")
            
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"❌ Error de infraestructura: No se pudo conectar a PostgreSQL: {e}")
        return None