# backend/main.py
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import os
import hashlib
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
def registrar_usuario(usuario: UsuarioCreate):  # Conservamos tu modelo original 🟢
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")
    
    try:
        with conn.cursor() as cur:
            # 1. Insertar en la tabla general de credenciales (users)
            cur.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s) RETURNING idUser",
                (usuario.username, usuario.password, usuario.role)
            )
            id_usuario = cur.fetchone()["iduser"]
            
            # 2. Normalizar el texto del rol para evitar fallos por minúsculas o espacios extra 🛡️
            rol_normalizado = usuario.role.strip().capitalize()
            
            # 3. Crear automáticamente el expediente relacional si es Cliente
            if rol_normalizado == "Cliente":
                cur.execute(
                    "INSERT INTO Cliente (NombreEmpresa, idUser) VALUES (%s, %s)",
                    (usuario.username, id_usuario)
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
            # --- SOLUCIÓN DE INTEGRIDAD: Forzar exactamente 2 decimales ---
            monto_formateado = f"{cotizacion.monto:.2f}"
            cadena_contrato = f"{monto_formateado}|{cotizacion.detalles}"
            hash_calculado = hashlib.sha256(cadena_contrato.encode('utf-8')).hexdigest()
            
            # Guardamos la cotización y su hash en la misma transacción
            cur.execute(
                """INSERT INTO Cotizacion (idCliente, idVendedor, monto, detalles, estado, hash_original) 
                   VALUES (%s, %s, %s, %s, 'Pendiente', %s) RETURNING idCotizacion""",
                (cotizacion.id_cliente, cotizacion.id_vendedor, cotizacion.monto, cotizacion.detalles, hash_calculado)
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
            # 1. Traemos los datos actuales, incluyendo ahora el idVendedor para auditoría 🛡️
            cur.execute("""
                SELECT c.llave_publica, cot.monto, cot.detalles, cot.idVendedor 
                FROM Cliente c 
                JOIN Cotizacion cot ON c.idCliente = cot.idCliente 
                WHERE cot.idCotizacion = %s
            """, (id_cotizacion,))
            result = cur.fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="Cotización no encontrada")

            # 2. RECALCULAMOS EL HASH CON LA REALIDAD DE LA BASE DE DATOS (Forzando 2 decimales)
            monto_db_formateado = f"{float(result['monto']):.2f}"
            cadena_actual = f"{monto_db_formateado}|{result['detalles']}"
            hash_actual_db = hashlib.sha256(cadena_actual.encode('utf-8')).hexdigest()

            # 3. EL PERRO GUARDIÁN: Si el hash de la DB no es el que el cliente firmó, hubo fraude.
            if hash_actual_db != payload.hash_original:
                # 📈 REGISTRO ENRIQUECIDO: Guardamos el idVendedor en la columna idUsuario
                cur.execute(
                    """INSERT INTO Registro_Auditoria (idCotizacion, idUsuario, accion, datos_anteriores) 
                       VALUES (%s, %s, 'INTENTO_ALTERACION_MONTO', %s)""",
                    (
                        id_cotizacion, 
                        result['idvendedor'], 
                        f"Discrepancia de integridad. El cliente intentó firmar datos que no coinciden con la BD de producción. Cotización emitida originalmente por el agente de ventas (Usuario ID: {result['idvendedor']})."
                    )
                )
                # Al cambiar a 'Alterada', automáticamente dejará de listarse en las pendientes del cliente
                cur.execute("UPDATE Cotizacion SET estado = 'Alterada' WHERE idCotizacion = %s", (id_cotizacion,))
                conn.commit()
                
                # 🤫 MENSAJE DISCRETO Y PROFESIONAL PARA EL CLIENTE:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="La cotización seleccionada ya no se encuentra disponible para firma o requiere una actualización de valores. Por favor, póngase en contacto con su asesor comercial."
                )

            # 4. Si todo está en orden, verificamos la firma matemática (Código original)
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
                # 📈 REGISTRO ENRIQUECIDO: Alerta de fallo matemático asociado al vendedor
                cur.execute(
                    """INSERT INTO Registro_Auditoria (idCotizacion, idUsuario, accion, datos_anteriores) 
                       VALUES (%s, %s, 'FIRMA_INVALIDA', %s)""",
                    (
                        id_cotizacion, 
                        result['idvendedor'], 
                        f"Fallo en la validación geométrica de la curva elíptica. Hash enviado: {payload.hash_original}. Agente responsable de la cotización: Usuario ID {result['idvendedor']}."
                    )
                )
                cur.execute("UPDATE Cotizacion SET estado = 'Alterada' WHERE idCotizacion = %s", (id_cotizacion,))
                conn.commit()
                
                # 🤫 MENSAJE DISCRETO Y PROFESIONAL PARA EL CLIENTE:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="No se pudo completar el proceso de autenticación digital de la oferta. Por motivos de seguridad, el documento ha sido retirado. Solicite una nueva cotización a su asesor."
                )
    finally:
        conn.close()

@app.post("/api/v1/auditoria/verificar_firmadas")
def verificar_cotizaciones_firmadas():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")
    
    alertas_detectadas = 0
    try:
        with conn.cursor() as cur:
            # 1. Traer todas las cotizaciones que supuestamente ya están firmadas
            cur.execute("""
                SELECT cot.idCotizacion, cot.monto, cot.detalles, cot.firma_digital, cot.idVendedor, c.llave_publica
                FROM Cotizacion cot
                JOIN Cliente c ON cot.idCliente = c.idCliente
                WHERE cot.estado = 'Firmada'
            """)
            cotizaciones = cur.fetchall()

            for cot in cotizaciones:
                # 2. Recalcular el HASH con lo que HOY existe en la base de datos
                monto_db_formateado = f"{float(cot['monto']):.2f}"
                cadena_actual = f"{monto_db_formateado}|{cot['detalles']}"
                hash_actual_db = hashlib.sha256(cadena_actual.encode('utf-8')).hexdigest()

                # 3. Verificar la firma guardada contra el hash actual de la DB
                # Si alguien alteró el monto en la DB, el hash cambió y la firma fallará matemáticamente
                es_valida = verificar_firma_ecdsa(
                    llave_publica_b64=cot['llave_publica'],
                    hash_documento=hash_actual_db,
                    firma_digital_b64=cot['firma_digital']
                )

                if not es_valida:
                    # ¡ALERTA ROJA! El registro fue modificado DESPUÉS de haber sido firmado.
                    alertas_detectadas += 1
                    
                    # Rompemos el estado de la cotización
                    cur.execute(
                        "UPDATE Cotizacion SET estado = 'Alterada' WHERE idCotizacion = %s",
                        (cot['idcotizacion'],)
                    )
                    
                    # Registramos el fraude post-firma en la auditoría
                    cur.execute(
                        """INSERT INTO Registro_Auditoria (idCotizacion, idUsuario, accion, datos_anteriores) 
                           VALUES (%s, %s, 'ALTERACION_POST_FIRMA', %s)""",
                        (
                            cot['idcotizacion'],
                            cot['idvendedor'],
                            f"CRÍTICO: El documento con firma digital válida fue modificado de forma no autorizada en la base de datos de producción. El sello criptográfico original quedó roto."
                        )
                    )
        conn.commit()
        return {
            "status": "success", 
            "mensaje": f"Inspección finalizada. Se auditaron {len(cotizaciones)} contratos. Alertas post-firma encontradas: {alertas_detectadas}."
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
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
def obtener_historial_auditoria():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")
    
    try:
        # Usamos RealDictCursor para que psycopg2 devuelva los datos como diccionarios JSON
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Consulta Forense con LEFT JOIN y COALESCE para protección contra borrado de usuarios
            cur.execute("""
                SELECT 
                    ra.idAuditoria,
                    ra.idCotizacion,
                    ra.idUsuario,
                    COALESCE(u.username, 'Usuario Eliminado/Desconocido') AS nombre_vendedor,
                    ra.accion,
                    ra.datos_anteriores,
                    ra.fecha_evento
                FROM Registro_Auditoria ra
                LEFT JOIN users u ON ra.idUsuario = u.idUser
                ORDER BY ra.fecha_evento DESC
            """)
            registros = cur.fetchall()
            
            # Formateamos fechas para el JSON si es necesario
            for reg in registros:
                if reg['fecha_evento']:
                    reg['fecha_evento'] = reg['fecha_evento'].isoformat()
                    
        return {"status": "success", "data": registros}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando auditoría: {str(e)}")
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
                SELECT idCotizacion, monto, detalles, estado, fecha_creacion, hash_original 
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

# --- NUEVO: ENDPOINTS DE ADMINISTRACIÓN Y CONTROL CRUD PARA MANTENIMIENTO ---

@app.get("/api/v1/admin/tablas_resumen")
def obtener_resumen_tablas():
    """Retorna una lista completa de las cotizaciones y clientes para gestión directa."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error al conectar con PostgreSQL")
    try:
        with conn.cursor() as cur:
            # Obtener todas las cotizaciones con sus estados actuales
            cur.execute("""
                SELECT idCotizacion, idCliente, idVendedor, monto, estado, fecha_creacion 
                FROM Cotizacion 
                ORDER BY idCotizacion DESC
            """)
            cotizaciones = cur.fetchall()
            
            # Obtener todos los clientes registrados
            cur.execute("""
                SELECT idCliente, NombreEmpresa, llave_publica 
                FROM Cliente 
                ORDER BY idCliente DESC
            """)
            clientes = cur.fetchall()
            
            return {
                "status": "success",
                "cotizaciones": cotizaciones,
                "clientes": clientes
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en consulta administrativa: {e}")
    finally:
        conn.close()

@app.delete("/api/v1/admin/cotizaciones/{id_cotizacion}")
def eliminar_cotizacion_individual(id_cotizacion: int):
    """Elimina una cotización específica y su historial de auditoría asociado."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Primero borramos los registros hijos (El historial de auditoría)
            # Esto evita el error de violación de llave foránea (foreign key constraint)
            cur.execute("DELETE FROM Registro_Auditoria WHERE idCotizacion = %s", (id_cotizacion,))
            
            # 2. Ahora sí podemos borrar al padre (La cotización)
            cur.execute("DELETE FROM Cotizacion WHERE idCotizacion = %s RETURNING idCotizacion", (id_cotizacion,))
            result = cur.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="La cotización seleccionada no existe")
                
        conn.commit()
        return {"status": "success", "mensaje": f"Cotización #{id_cotizacion} y su historial eliminados del sistema."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.post("/api/v1/admin/vaciar_registros_sandbox")
def vaciar_registros_sandbox():
    """Limpia por completo las cotizaciones y las alertas de auditoría para reiniciar pruebas."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Se elimina primero la tabla dependiente por integridad referencial (llaves foráneas)
            cur.execute("TRUNCATE TABLE Registro_Auditoria RESTART IDENTITY CASCADE")
            cur.execute("TRUNCATE TABLE Cotizacion RESTART IDENTITY CASCADE")
        conn.commit()
        return {"status": "success", "mensaje": "🔄 Tablas transaccionales limpiadas e IDs reiniciados con éxito."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al truncar registros de prueba: {e}")
    finally:
        conn.close()