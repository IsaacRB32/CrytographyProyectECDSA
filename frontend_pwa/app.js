/* frontend_pwa/app.js */
const API_URL = "https://crytographyproyectecdsa.onrender.com/api/v1";

// VARIABLES DE ESTADO LOCAL (Seguridad en memoria RAM)
let usuarioSesion = null;      // Datos del cliente logeado
let llavePrivadaLocal = null;  // Almacenará el objeto CryptoKey de forma efímera
let cotizacionesEnBandeja = []; // Lista de ofertas comerciales descargadas
let cotizacionSeleccionada = null;

// --- MANEJADOR DE VISTAS (TRANSICIONES) ---
function cambiarVista(idVistaObjetivo) {
    document.querySelectorAll('.view').forEach(vista => vista.classList.add('hidden'));
    document.getElementById(idVistaObjetivo).classList.remove('hidden');
}

// --- FLUJO 1: LOGEAR USUARIO ---
document.getElementById('formLoginPWA').onsubmit = async (e) => {
    e.preventDefault();
    const errorDiv = document.getElementById('statusLogin');
    errorDiv.innerText = "Validando identidad en la nube...";

    try {
        const response = await fetch(`${API_URL}/usuarios/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: document.getElementById('loginUser').value,
                password: document.getElementById('loginPass').value
            })
        });

        if (!response.ok) {
            const errData = await response.json();
            errorDiv.innerText = `❌ ${errData.detail}`;
            return;
        }

        const data = await response.json();
        
        // REGLA DE ARQUITECTURA: La PWA solo permite el acceso a Clientes
        if (data.role !== "Cliente") {
            errorDiv.innerText = "❌ Acceso denegado: Esta aplicación móvil es exclusiva para perfiles Cliente.";
            return;
        }

        // Guardamos los datos completos de sesión directamente
        localStorage.setItem("clienteSesion", JSON.stringify(data));
        usuarioSesion = data;
        errorDiv.innerText = "";
        
        // Evaluar bandeja y estado criptográfico en Render
        await verificarEstadoYConsultarBandeja();

    } catch (err) {
        errorDiv.innerText = "❌ Error: El monolito central está fuera de línea.";
    }
};

// --- FLUJO 2: INSPECCIÓN CRYPTO Y BANDEJA ---
async function verificarEstadoYConsultarBandeja() {
    try {
        const response = await fetch(`${API_URL}/clientes/${usuarioSesion.id_cliente}/cotizaciones`);
        const data = await response.json();
        cotizacionesEnBandeja = data.cotizaciones_pendientes;

        // 1. Intentamos cargar la llave privada desde el disco duro del celular (localStorage)
        llavePrivadaLocal = await cargarLlavePrivadaDelCelular();

        // 2. Evaluamos el estado real del usuario
        if (data.tiene_llave_registrada === false) {
            // Caso A: Cliente totalmente nuevo. Necesita generar llaves obligatoriamente.
            cambiarVista('view-setup-keys');
            document.getElementById('logSetup').innerText = "Llavero vacío. Se requiere aprovisionamiento inicial.";
        } 
        else if (data.tiene_llave_registrada === true && llavePrivadaLocal === null) {
            // Caso B: El backend dice que ya tiene llave, pero ESTE celular en particular NO la tiene guardada.
            cambiarVista('view-setup-keys');
            document.getElementById('logSetup').style.color = "#ff9800";
            document.getElementById('logSetup').innerText = "⚠️ Dispositivo no reconocido. Se requiere generar un nuevo llavero para este equipo (Re-enrolamiento).";
        } 
        else {
            // Caso C: El backend lo reconoce y el celular tiene la llave privada intacta en localStorage.
            if (!llavePrivadaLocal) {
                llavePrivadaLocal = await cargarLlavePrivadaDelCelular();
            }
            cargarVistaBandejaInbox();
        }
    } catch (err) {
        alert("Error descargando información transaccional.");
    }
}

function cargarVistaBandejaInbox() {
    document.getElementById('lblNombreCliente').innerText = usuarioSesion.username;
    document.getElementById('lblIdCliente').innerText = `#${usuarioSesion.id_cliente}`;
    
    const contenedorLista = document.getElementById('listaCotizaciones');
    contenedorLista.innerHTML = "";

    if (cotizacionesEnBandeja.length === 0) {
        contenedorLista.innerHTML = `<p style="text-align:center; color:#666; font-size:14px; margin: 30px 0;">🎉 ¡Al día! No tienes cotizaciones pendientes de firma.</p>`;
    } else {
        cotizacionesEnBandeja.forEach(cot => {
            const itemHtml = document.createElement('div');
            itemHtml.className = "inbox-item";
            itemHtml.onclick = () => verDetalleCotizacion(cot);
            itemHtml.innerHTML = `
                <div>
                    <h4>Cotización #${cot.idcotizacion}</h4>
                    <p>Creada el: ${new Date(cot.fecha_creacion).toLocaleDateString()}</p>
                </div>
                <span class="badge-pendiente">$${cot.monto}</span>
            `;
            contenedorLista.appendChild(itemHtml);
        });
    }
    cambiarVista('view-inbox');
}

// --- FLUJO 3: ENROLAMIENTO / GENERACIÓN DE LLAVES ASIMÉTRICAS ---
document.getElementById('btnRegistrarLlaves').onclick = async () => {
    const logDiv = document.getElementById('logSetup');
    logDiv.innerText = "Calculando curvas elípticas en hardware local...";

    try {
        const parDeLlaves = await generarParDeLlaves();
        llavePrivadaLocal = parDeLlaves.privateKey; 
        await guardarLlavePrivadaEnCelular(llavePrivadaLocal);
        
        logDiv.innerText += "\n> Exportando llave pública (Formato SPKI Base64)...";
        const pubKeyB64 = await exportarLlavePublicaB64(parDeLlaves.publicKey);

        logDiv.innerText += "\n> Guardando llave central en base de datos Render...";
        const response = await fetch(`${API_URL}/clientes/registrar_llave`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                id_cliente: usuarioSesion.id_cliente,
                llave_publica_b64: pubKeyB64
            })
        });

        if (response.ok) {
            logDiv.innerText += "\n✅ ¡Identidad registrada con éxito! Desbloqueando aplicación...";
            setTimeout(() => {
                cargarVistaBandejaInbox();
            }, 1500);
        } else {
            logDiv.innerText += "\n❌ Error registrando llave en el servidor.";
        }
    } catch (err) {
        logDiv.innerText += `\n❌ Tronó el hardware crypto: ${err.message}`;
    }
};

// --- FLUJO 4: BANDEJA DE DETALLES E INTERACCIÓN ---
function verDetalleCotizacion(cot) {
    cotizacionSeleccionada = cot;
    
    document.getElementById('detId').innerText = cot.idcotizacion;
    document.getElementById('detMonto').innerText = cot.monto;
    document.getElementById('detEspecificaciones').innerText = cot.detalles;
    document.getElementById('detHash').innerText = cot.hash_original;
    
    document.getElementById('logFirma').innerText = "Esperando dictamen del cliente...";
    cambiarVista('view-details');
}

function volverAlInbox() {
    cotizacionSeleccionada = null;
    cambiarVista('view-inbox');
}

// BOTÓN RECHAZAR
document.getElementById('btnRechazar').onclick = async () => {
    if(!confirm("¿Estás seguro de que deseas rechazar esta cotización?")) return;
    
    try {
        const res = await fetch(`${API_URL}/cotizaciones/${cotizacionSeleccionada.idcotizacion}/rechazar`, { method: "POST" });
        if(res.ok) {
            alert("Cotización rechazada.");
            await verificarEstadoYConsultarBandeja();
        }
    } catch (err) { alert("Error al procesar acción."); }
};

// BOTÓN FIRMAR Y ACEPTAR (Módulo Criptográfico Crítico)
document.getElementById('btnFirmarAceptar').onclick = async () => {
    const logDiv = document.getElementById('logFirma');
    const hashContrato = document.getElementById('detHash').innerText;
    
    logDiv.style.color = "#00ff00";
    logDiv.innerText = "Extrayendo firma digital de la llave privada local...";

    if (!llavePrivadaLocal) {
        logDiv.style.color = "#f44336";
        logDiv.innerText = "❌ ERROR DE INTEGRIDAD: La llave privada se destruyó al cerrar/refrescar la app. Por favor, cierra sesión y vuelve a enrolar tu dispositivo.";
        return;
    }

    try {
        const firmaB64 = await firmarHashDocumento(llavePrivadaLocal, hashContrato);
        logDiv.innerText += "\n> Firma geométrica calculada con éxito.";
        logDiv.innerText += "\n> Transmitiendo paquete de validación matemática al monolito...";

        console.log("Firmando este hash:", hashContrato);
        const response = await fetch(`${API_URL}/cotizaciones/${cotizacionSeleccionada.idcotizacion}/firmar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                hash_original: hashContrato,
                firma_digital: firmaB64
            })
        });

        const data = await response.json();
        
        if (response.ok) {
            logDiv.innerText += `\n✅ Dictamen del Servidor: ${data.mensaje}`;
            alert("¡Contrato sellado e íntegro! Transacción autorizada.");
            await verificarEstadoYConsultarBandeja();
        } else {
            logDiv.style.color = "#f44336";
            logDiv.innerText += `\n❌ RECHAZADO: ${data.detail}`;
        }

    } catch (err) {
        logDiv.style.color = "#f44336";
        logDiv.innerText += `\n❌ Fallo en red: ${err.message}`;
    }
};

// --- MÓDULO DE PERSISTENCIA LOCAL (STORAGE) ---
async function guardarLlavePrivadaEnCelular(privateKey) {
    const jwk = await window.crypto.subtle.exportKey("jwk", privateKey);
    localStorage.setItem(`llave_privada_ecdsa_${usuarioSesion.id_cliente}`, JSON.stringify(jwk));
}

async function cargarLlavePrivadaDelCelular() {
    const jwkStr = localStorage.getItem(`llave_privada_ecdsa_${usuarioSesion.id_cliente}`);
    if (!jwkStr) return null; 
    
    const jwk = JSON.parse(jwkStr);
    return await window.crypto.subtle.importKey(
        "jwk",
        jwk,
        { name: "ECDSA", namedCurve: "P-256" },
        true,
        ["sign"]
    );
}

function cerrarSesion() {
    localStorage.removeItem("clienteSesion");
    usuarioSesion = null;
    llavePrivadaLocal = null;
    cotizacionesEnBandeja = [];
    cotizacionSeleccionada = null;
    cambiarVista('view-login');
    document.getElementById('formLoginPWA').reset();
    document.getElementById('statusLogin').innerText = "";
}

// --- RESTAURACIÓN AUTOMÁTICA COMPLETA AL INICIAR LA PWA ---
// Usamos addEventListener para evitar colisiones con otros scripts criptográficos
window.addEventListener("load", async () => {
    const sesionGuardada = localStorage.getItem("clienteSesion");
    if (sesionGuardada && sesionGuardada !== "undefined") {
        try {
            usuarioSesion = JSON.parse(sesionGuardada);
            if (usuarioSesion && usuarioSesion.id_cliente) {
                await verificarEstadoYConsultarBandeja();
            }
        } catch (e) {
            console.error("Error al restaurar el llavero o sesión: ", e);
            cerrarSesion();
        }
    }
});