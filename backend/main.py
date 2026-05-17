# backend/main.py
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import os

# Importaciones modulares de tu propia arquitectura
from database import get_db_connection
from crypto_backend import verificar_firma_ecdsa

app = FastAPI(
    title="API REST Monolítica - Integridad Transaccional",
    description="Backend definitivo para el Sistema de la Empresa y la PWA (ECDSA P-256)",
    version="1.0.0"
)

# Configuración obligatoria de CORS para permitir conexiones de tus frontends HTML/JS/PWA
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE VALIDACIÓN DE ENTRADA (Pydantic) ---

class UsuarioCreate(BaseModel):
    username: str = Field(..., max_length=100)
    password: str = Field(..., max_length=255)
    role: str = Field(..., description="'Ventas', 'Finanzas' o 'Cliente'")

class RegistroLlaveRequest(BaseModel):
    id_cliente: int
    llave_publica_b64: str

class CotizacionCreate(BaseModel):
    id_cliente: int
    id_vendedor: int
    monto: float
    detalles: str

class FirmaRequest(BaseModel):
    hash_original: str = Field(..., min_length=64, max_length=64, description="Hash SHA-256 en hexadecimal")
    firma_digital: str = Field(..., description="Firma ECDSA codificada en Base64")

class LoginRequest(BaseModel):
    username: str
    password: str

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {
        "status": "online",
        "mensaje": "El monolito está funcionando y conectado a la nube 🚀",
        "database": "PostgreSQL en Render listo 🟢"
    }



# 1. REGISTRAR USUARIOS DEL SISTEMA (Para control de accesos y roles)
@app.post("/api/v1/usuarios/registrar", status_code=status.HTTP_201_CREATED)
def registrar_usuario(usuario: UsuarioCreate):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s) RETURNING idUser",
                (usuario.username, usuario.password, usuario.role)
            )
            id_usuario = cur.fetchone()["iduser"]
            
            # Si el rol es Cliente, creamos automáticamente su perfil vacío en la tabla Cliente
            if usuario.role == "Cliente":
                cur.execute(
                    "INSERT INTO Cliente (NombreEmpresa, idUser) VALUES (%s, %s)",
                    (f"Empresa de {usuario.username}", id_usuario)
                )
        conn.commit()
        return {"mensaje": f"Usuario '{usuario.username}' con rol '{usuario.role}' creado exitosamente."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"El usuario ya existe o los datos son inválidos: {e}")
    finally:
        conn.close()

# 2. REGISTRAR LA LLAVE PÚBLICA DEL CLIENTE (Llamado desde la PWA una sola vez al instalarse)
@app.post("/api/v1/clientes/registrar_llave")
def registrar_llave_cliente(payload: RegistroLlaveRequest):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE Cliente SET llave_publica = %s WHERE idCliente = %s RETURNING idCliente",
                (payload.llave_publica_b64, payload.id_cliente)
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="El ID de cliente especificado no existe")
        conn.commit()
        return {"mensaje": "Llave pública criptográfica registrada con éxito en los servidores centrales."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# 3. CREAR COTIZACIÓN (Llamado por el agente de Ventas desde el sistema interno)
@app.post("/api/v1/cotizaciones/crear", status_code=status.HTTP_201_CREATED)
def crear_cotizacion(cotizacion: CotizacionCreate):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO Cotizacion (idCliente, idVendedor, monto, detalles, estado) 
                   VALUES (%s, %s, %s, %s, 'Pendiente') RETURNING idCotizacion""",
                (cotizacion.id_cliente, cotizacion.id_vendedor, cotizacion.monto, cotizacion.detalles)
            )
            id_cotizacion = cur.fetchone()["idcotizacion"]
        conn.commit()
        return {"id_cotizacion": id_cotizacion, "mensaje": "Cotización guardada con estado 'Pendiente'."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Error al enlazar llaves foráneas: {e}")
    finally:
        conn.close()

# 4. VERIFICAR Y FIRMAR COTIZACIÓN (El Endpoint Crítico de tu proyecto)
@app.post("/api/v1/cotizaciones/{id_cotizacion}/firmar")
def firmar_cotizacion(id_cotizacion: int, payload: FirmaRequest):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Recuperar de forma estricta la llave pública del cliente vinculada a esta cotización específica
            cur.execute("""
                SELECT c.llave_publica, cot.monto
                FROM Cliente c 
                JOIN Cotizacion cot ON c.idCliente = cot.idCliente 
                WHERE cot.idCotizacion = %s
            """, (id_cotizacion,))
            result = cur.fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="Cotización no encontrada")
            if not result['llave_publica']:
                raise HTTPException(status_code=400, detail="El cliente no ha registrado una identidad criptográfica (Llave Pública)")

            # Ejecutamos la validación matemática llamando a tu módulo crypto_backend
            es_valida = verificar_firma_ecdsa(
                llave_publica_b64=result['llave_publica'],
                hash_documento=payload.hash_original,
                firma_digital_b64=payload.firma_digital
            )

            if es_valida:
                # Si la geometría de la curva elíptica coincide, el documento es ÍNTEGRO
                cur.execute(
                    """UPDATE Cotizacion 
                       SET estado = 'Firmada', firma_digital = %s, hash_original = %s, fecha_firma = CURRENT_TIMESTAMP 
                       WHERE idCotizacion = %s""",
                    (payload.firma_digital, payload.hash_original, id_cotizacion)
                )
                conn.commit()
                return {"status": "success", "mensaje": "Integridad verificada matemáticamente. Transacción sellada exitosamente. ✅"}
            else:
                # Alerta: Si no coincide, significa que el hash no cuadra o la firma es falsa (Intento de Fraude)
                cur.execute(
                    """INSERT INTO Registro_Auditoria (idCotizacion, accion, datos_anteriores) 
                       VALUES (%s, 'FIRMA_INVALIDA', %s)""",
                    (id_cotizacion, f"Alerta de alteración. Hash enviado: {payload.hash_original}. Monto actual en DB: {result['monto']}")
                )
                # Actualizamos el estado para avisar visualmente a Finanzas
                cur.execute("UPDATE Cotizacion SET estado = 'Alterada' WHERE idCotizacion = %s", (id_cotizacion,))
                conn.commit()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="⚠️ CRÍTICO: Violación de integridad detectada. La firma digital no corresponde al documento."
                )
    finally:
        conn.close()

@app.post("/api/v1/usuarios/login")
def login_usuario(credenciales: LoginRequest):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Hacemos un JOIN para traer el idCliente de forma automática si el usuario es un Cliente
            cur.execute("""
                SELECT u.idUser, u.username, u.role, c.idCliente 
                FROM users u
                LEFT JOIN Cliente c ON u.idUser = c.idUser
                WHERE u.username = %s AND u.password = %s
            """, (credenciales.username, credenciales.password))
            user = cur.fetchone()
            
            if not user:
                raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
                
            return {
                "id_user": user["iduser"], 
                "username": user["username"], 
                "role": user["role"],
                "id_cliente": user["idcliente"], # Esto vendrá dinámico desde Render 🟢
                "mensaje": f"Bienvenido {user['username']}"
            }
    finally:
        conn.close()

# 5. CONSULTAR AUDITORÍA (Solo para el rol de Finanzas)
@app.get("/api/v1/auditoria")
def consultar_auditoria():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Traemos todo el registro de alteraciones ordenado por fecha
            cur.execute("""
                SELECT idAuditoria, idCotizacion, accion, datos_anteriores, fecha_evento 
                FROM Registro_Auditoria 
                ORDER BY fecha_evento DESC
            """)
            registros = cur.fetchall()
            return {"status": "success", "data": registros}
    finally:
        conn.close()

# 6. BANDEJA DE ENTRADA DEL CLIENTE (Para la PWA)
@app.get("/api/v1/clientes/{id_cliente}/cotizaciones")
def obtener_cotizaciones_cliente(id_cliente: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Primero, revisamos si el cliente ya tiene llave pública
            cur.execute("SELECT llave_publica FROM Cliente WHERE idCliente = %s", (id_cliente,))
            cliente = cur.fetchone()
            
            if not cliente:
                raise HTTPException(status_code=404, detail="Cliente no encontrado")
                
            tiene_llave = cliente["llave_publica"] is not None

            # Luego, traemos sus cotizaciones pendientes
            cur.execute("""
                SELECT idCotizacion, monto, detalles, estado, fecha_creacion 
                FROM Cotizacion 
                WHERE idCliente = %s AND estado = 'Pendiente'
                ORDER BY fecha_creacion DESC
            """, (id_cliente,))
            cotizaciones = cur.fetchall()
            
            return {
                "tiene_llave_registrada": tiene_llave,
                "cotizaciones_pendientes": cotizaciones
            }
    finally:
        conn.close()

# 7. RECHAZAR COTIZACIÓN
@app.post("/api/v1/cotizaciones/{id_cotizacion}/rechazar")
def rechazar_cotizacion(id_cotizacion: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE Cotizacion SET estado = 'Rechazada' WHERE idCotizacion = %s", (id_cotizacion,))
            conn.commit()
            return {"mensaje": "Cotización rechazada exitosamente"}
    finally:
        conn.close()