# init_db.py
import sys
import os

# Aseguramos que Python pueda encontrar la carpeta 'backend' para importar modularmente
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))
from database import get_db_connection

def crear_tablas():
    commands = (
        # 1. Tabla de Usuarios del Sistema (Vendedores, Finanzas, Clientes)
        """
        CREATE TABLE IF NOT EXISTS users (
            idUser SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL -- 'Ventas', 'Finanzas', 'Cliente'
        )
        """,
        # 2. Tabla de Clientes (Contiene la llave pública ECDSA de su PWA)
        """
        CREATE TABLE IF NOT EXISTS Cliente (
            idCliente SERIAL PRIMARY KEY,
            NombreEmpresa VARCHAR(255) NOT NULL,
            RazonSocial VARCHAR(255),
            llave_publica TEXT, -- Formato SPKI Base64 enviado por la PWA
            idUser INTEGER REFERENCES users(idUser) ON DELETE SET NULL
        )
        """,
        # 3. Tabla de Plantillas de Cotizaciones (Para agilizar ventas)
        """
        CREATE TABLE IF NOT EXISTS Plantilla (
            idPlantilla SERIAL PRIMARY KEY,
            nombre_destino VARCHAR(255) NOT NULL,
            monto_base DECIMAL(10, 2) NOT NULL,
            detalles_base TEXT
        )
        """,
        # 4. Tabla de Cotizaciones (El documento transaccional central)
        """
        CREATE TABLE IF NOT EXISTS Cotizacion (
            idCotizacion SERIAL PRIMARY KEY,
            idCliente INTEGER REFERENCES Cliente(idCliente) ON DELETE CASCADE,
            idVendedor INTEGER REFERENCES users(idUser) ON DELETE SET NULL,
            monto DECIMAL(10, 2) NOT NULL,
            detalles TEXT,
            estado VARCHAR(20) DEFAULT 'Pendiente', -- 'Pendiente', 'Firmada', 'Alterada', 'Pagada'
            hash_original VARCHAR(64), -- Hash SHA-256 del contenido
            firma_digital TEXT,        -- Sello criptográfico ECDSA
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_firma TIMESTAMP
        )
        """,
        # 5. Registro de Auditoría (El perro guardián criptográfico)
        """
        CREATE TABLE IF NOT EXISTS Registro_Auditoria (
            idAuditoria SERIAL PRIMARY KEY,
            idCotizacion INTEGER REFERENCES Cotizacion(idCotizacion) ON DELETE CASCADE,
            idUsuario INTEGER REFERENCES users(idUser) ON DELETE SET NULL,
            accion VARCHAR(50) NOT NULL, -- 'INTENTO_MODIFICACION', 'FIRMA_INVALIDA'
            datos_anteriores TEXT,
            fecha_evento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    
    conn = get_db_connection()
    if not conn:
        print("❌ No se pudo iniciar la inicialización: Conexión fallida.")
        return

    try:
        with conn.cursor() as cur:
            print("🛠️  Desplegando el esquema transaccional en Render...")
            for command in commands:
                cur.execute(command)
        conn.commit()
        print("✅ ¡Esquema de producción desplegado exitosamente en la nube!")
    except Exception as e:
        print(f"❌ Error durante el despliegue de tablas: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    crear_tablas()