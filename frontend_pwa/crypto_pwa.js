/* frontend_pwa/crypto_pwa.js */

// 1. Genera las curvas elípticas P-256 en el hardware del celular
async function generarParDeLlaves() {
    return await window.crypto.subtle.generateKey(
        {
            name: "ECDSA",
            namedCurve: "P-256",
        },
        true, // Permite que la llave privada sea extraíble para guardarla en el celular
        ["sign", "verify"]
    );
}

// 2. Exporta la llave pública a Base64 para mandarla a Render
async function exportarLlavePublicaB64(publicKey) {
    const spkiBuffer = await window.crypto.subtle.exportKey("spki", publicKey);
    const spkiArray = new Uint8Array(spkiBuffer);
    const spkiString = String.fromCharCode.apply(null, spkiArray);
    return btoa(spkiString);
}

// 3. Firma un contrato usando la llave privada local
async function firmarHashDocumento(privateKey, hashHex) {
    const hashBuffer = new Uint8Array(hashHex.match(/[\da-f]{2}/gi).map(h => parseInt(h, 16)));
    
    const firmaBuffer = await window.crypto.subtle.sign(
        { name: "ECDSA", hash: { name: "SHA-256" } },
        privateKey,
        hashBuffer
    );
    
    // Convertir a Base64 de forma segura
    const firmaArray = new Uint8Array(firmaBuffer);
    let binary = "";
    firmaArray.forEach(b => binary += String.fromCharCode(b));
    return btoa(binary);
}