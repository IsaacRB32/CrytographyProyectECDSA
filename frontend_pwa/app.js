const API_URL = "https://crytographyproyectecdsa.onrender.com/api/v1";

let usuarioSesion = null;
let llavePrivadaLocal = null;
let cotizacionesEnBandeja = [];
let cotizacionSeleccionada = null;

// ─── Sistema de Modales (unificado con el dashboard) ─────────────────
function mostrarModal({ tipo = 'info', titulo, mensaje, botones = [] }) {
    return new Promise((resolve) => {
        const overlay = document.getElementById('modalOverlay');
        const iconEl = document.getElementById('modalIcon');
        const titleEl = document.getElementById('modalTitle');
        const msgEl = document.getElementById('modalMessage');
        const actionsEl = document.getElementById('modalActions');

        const iconMap = {
            warning: { bg: 'warning', text: '!' },
            danger: { bg: 'danger', text: '✕' },
            success: { bg: 'success', text: '✓' },
            info: { bg: 'info', text: 'i' }
        };
        const iconCfg = iconMap[tipo] || iconMap.info;
        iconEl.className = `modal-icon ${iconCfg.bg}`;
        iconEl.innerText = iconCfg.text;

        titleEl.innerText = titulo || 'Notificación';
        msgEl.innerText = mensaje || '';

        actionsEl.innerHTML = '';
        botones.forEach((btn, index) => {
            const button = document.createElement('button');
            button.innerText = btn.texto;
            button.className = btn.clase || 'btn-outline';
            button.addEventListener('click', () => {
                cerrarModal();
                resolve(btn.valor !== undefined ? btn.valor : index);
            });
            actionsEl.appendChild(button);
        });

        if (botones.length === 0) {
            const defaultBtn = document.createElement('button');
            defaultBtn.innerText = 'Aceptar';
            defaultBtn.className = 'btn-primary';
            defaultBtn.addEventListener('click', () => {
                cerrarModal();
                resolve(undefined);
            });
            actionsEl.appendChild(defaultBtn);
        }

        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';

        const handleEsc = (e) => { if (e.key === 'Escape') { cerrarModal(); resolve(undefined); } };
        document.addEventListener('keydown', handleEsc, { once: true });

        function cerrarModal() {
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        }
    });
}

function mostrarAlerta(mensaje, tipo = 'info', tituloPersonalizado = null) {
    const titulos = {
        success: 'Operación Exitosa',
        danger: 'Error',
        warning: 'Advertencia',
        info: 'Información'
    };
    return mostrarModal({
        tipo,
        titulo: tituloPersonalizado || titulos[tipo] || 'Notificación',
        mensaje,
        botones: [{ texto: 'Aceptar', clase: 'btn-primary', valor: true }]
    });
}

function mostrarConfirmacion(mensaje, tituloPersonalizado = null) {
    return mostrarModal({
        tipo: 'warning',
        titulo: tituloPersonalizado || 'Confirmación Requerida',
        mensaje,
        botones: [
            { texto: 'Cancelar', clase: 'btn-outline', valor: false },
            { texto: 'Confirmar', clase: 'btn-danger', valor: true }
        ]
    });
}

// ─── Lógica de la PWA ─────────────────────────────────
function cambiarVista(idVistaObjetivo) {
    document.querySelectorAll('.view').forEach(vista => vista.classList.add('hidden'));
    document.getElementById(idVistaObjetivo).classList.remove('hidden');
}

// Login
document.getElementById('formLoginPWA').onsubmit = async (e) => {
    e.preventDefault();
    const btnLogin = document.getElementById('btnLogin');
    const originalText = btnLogin.innerText;
    btnLogin.innerText = "Verificando...";
    btnLogin.disabled = true;

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
            await mostrarAlerta(errData.detail || "Credenciales inválidas.", "danger", "Error de Autenticación");
            btnLogin.innerText = originalText;
            btnLogin.disabled = false;
            return;
        }

        const data = await response.json();
        
        if (data.role !== "Cliente") {
            await mostrarAlerta("Acceso denegado: Esta aplicación móvil es exclusiva para perfiles Cliente.", "danger", "Acceso Restringido");
            btnLogin.innerText = originalText;
            btnLogin.disabled = false;
            return;
        }

        localStorage.setItem("clienteSesion", JSON.stringify(data));
        usuarioSesion = data;
        btnLogin.innerText = originalText;
        btnLogin.disabled = false;
        
        await verificarEstadoYConsultarBandeja();

    } catch (err) {
        await mostrarAlerta("Error de conexión. El servicio central está fuera de línea.", "danger", "Error de Red");
        btnLogin.innerText = originalText;
        btnLogin.disabled = false;
    }
};

async function verificarEstadoYConsultarBandeja() {
    try {
        const response = await fetch(`${API_URL}/clientes/${usuarioSesion.id_cliente}/cotizaciones`, {
            cache: 'no-store'
        });
        const data = await response.json();
        cotizacionesEnBandeja = data.cotizaciones_pendientes;

        llavePrivadaLocal = await cargarLlavePrivadaDelCelular();

        if (data.tiene_llave_registrada === false) {
            cambiarVista('view-setup-keys');
            document.getElementById('logSetup').innerText = "Llavero vacío. Se requiere aprovisionamiento inicial.";
            document.getElementById('logSetup').className = 'status-box';
        } 
        else if (data.tiene_llave_registrada === true && llavePrivadaLocal === null) {
            cambiarVista('view-setup-keys');
            const logEl = document.getElementById('logSetup');
            logEl.className = 'status-box warning';
            logEl.innerText = "Dispositivo no reconocido. Se requiere generar un nuevo llavero para este equipo (Re-enrolamiento).";
        } 
        else {
            if (!llavePrivadaLocal) {
                llavePrivadaLocal = await cargarLlavePrivadaDelCelular();
            }
            cargarVistaBandejaInbox();
        }
    } catch (err) {
        await mostrarAlerta("Error descargando información transaccional.", "danger");
    }
}

function cargarVistaBandejaInbox() {
    document.getElementById('lblNombreCliente').innerText = usuarioSesion.username;
    document.getElementById('lblIdCliente').innerText = `#${usuarioSesion.id_cliente}`;
    
    const contenedorLista = document.getElementById('listaCotizaciones');
    contenedorLista.innerHTML = "";

    if (cotizacionesEnBandeja.length === 0) {
        contenedorLista.innerHTML = `<p style="text-align:center; color:var(--text-secondary); font-size:0.85rem; margin: 30px 0;">No tienes cotizaciones pendientes de firma.</p>`;
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

// Setup de llaves
document.getElementById('btnRegistrarLlaves').onclick = async () => {
    const logDiv = document.getElementById('logSetup');
    const btnRegistrar = document.getElementById('btnRegistrarLlaves');
    logDiv.className = 'status-box';
    logDiv.innerText = "Calculando curvas elípticas en hardware local...";
    btnRegistrar.disabled = true;
    btnRegistrar.innerText = "Generando...";

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
            await mostrarAlerta("¡Contrato sellado e íntegro! Transacción autorizada.", "success", "Firma Exitosa");
            await verificarEstadoYConsultarBandeja();
        } else {
            // 1. Se muestra tu mensaje discreto y profesional
            await mostrarAlerta(data.detail || "Firma rechazada.", "danger");

            // 2. 🔥 Forzamos visualmente a la PWA a salir de los detalles y regresar a la lista
            volverAlInbox();

            // 3. 🔥 Recargamos la bandeja con la petición (que ahora ignorará la caché)
            await verificarEstadoYConsultarBandeja();
        }
    } catch (err) {
        logDiv.className = 'status-box error';
        logDiv.innerText += `\nFallo en hardware crypto: ${err.message}`;
        await mostrarAlerta("Error generando el par de llaves.", "danger");
    } finally {
        btnRegistrar.disabled = false;
        btnRegistrar.innerText = "Generar y Registrar Identidad";
    }
};

function verDetalleCotizacion(cot) {
    cotizacionSeleccionada = cot;
    
    document.getElementById('detId').innerText = cot.idcotizacion;
    document.getElementById('detMonto').innerText = cot.monto;
    document.getElementById('detEspecificaciones').innerText = cot.detalles;
    document.getElementById('detHash').innerText = cot.hash_original;
    
    cambiarVista('view-details');
}

function volverAlInbox() {
    cotizacionSeleccionada = null;
    cambiarVista('view-inbox');
}

document.getElementById('btnRechazar').onclick = async () => {
    const confirmado = await mostrarConfirmacion("¿Está seguro de que desea rechazar esta cotización?", "Rechazar Cotización");
    if (!confirmado) return;

    const btnRechazar = document.getElementById('btnRechazar');
    btnRechazar.disabled = true;
    btnRechazar.innerText = "Procesando...";
    
    try {
        const res = await fetch(`${API_URL}/cotizaciones/${cotizacionSeleccionada.idcotizacion}/rechazar`, { method: "POST" });
        if(res.ok) {
            await mostrarAlerta("Cotización rechazada correctamente.", "success");
            await verificarEstadoYConsultarBandeja();
        } else {
            const data = await res.json();
            await mostrarAlerta(data.detail || "Error al rechazar.", "danger");
        }
    } catch (err) { 
        await mostrarAlerta("Error al procesar acción.", "danger");
    } finally {
        btnRechazar.disabled = false;
        btnRechazar.innerText = "Rechazar";
    }
};

document.getElementById('btnFirmarAceptar').onclick = async () => {
    const hashContrato = document.getElementById('detHash').innerText;
    const btnFirmar = document.getElementById('btnFirmarAceptar');
    
    if (!llavePrivadaLocal) {
        await mostrarAlerta("Llave privada no encontrada. Re-enrole su dispositivo.", "danger", "Error de Integridad");
        return;
    }

    // 1. Deshabilitamos el botón inmediatamente
    btnFirmar.disabled = true;
    btnFirmar.innerText = "Firmando...";

    try {
        const firmaB64 = await firmarHashDocumento(llavePrivadaLocal, hashContrato);
        
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
            await mostrarAlerta("¡Contrato sellado e íntegro! Transacción autorizada.", "success", "Firma Exitosa");
            volverAlInbox();
            await verificarEstadoYConsultarBandeja();
        } else {
            // 2. Mostramos el mensaje discreto de error
            await mostrarAlerta(data.detail || "Firma rechazada.", "danger");
            
            // 3. 🔥 FIX: Obligamos a la PWA a salir de los detalles de la cotización alterada
            volverAlInbox();
            
            // 4. 🔥 FIX: Recargamos la bandeja en tiempo real (ahora ignorará la caché)
            await verificarEstadoYConsultarBandeja();
        }

    } catch (err) {
        await mostrarAlerta("Error de conexión al firmar.", "danger");
    } finally {
        // Se reactiva el botón oculto para que esté listo en la siguiente cotización sana que se abra
        btnFirmar.disabled = false;
        btnFirmar.innerText = "Sellar y Aceptar";
    }
};

// Persistencia de llaves
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
}

// Inicialización
async function inicializarPWA() {
    const sesionGuardada = localStorage.getItem("clienteSesion");
    
    if (sesionGuardada && sesionGuardada !== "undefined") {
        try {
            usuarioSesion = JSON.parse(sesionGuardada);
            if (usuarioSesion && usuarioSesion.id_cliente) {
                await verificarEstadoYConsultarBandeja();
                return;
            }
        } catch (e) {
            console.error("Error crítico al restaurar la sesión persistente: ", e);
        }
    }
    
    cambiarVista('view-login');
}

window.addEventListener("load", inicializarPWA);