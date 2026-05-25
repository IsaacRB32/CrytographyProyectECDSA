async function generarParDeLlaves() {
    return await window.crypto.subtle.generateKey(
        {
            name: "ECDSA",
            namedCurve: "P-256",
        },
        true,
        ["sign", "verify"]
    );
}

async function exportarLlavePublicaB64(publicKey) {
    const spkiBuffer = await window.crypto.subtle.exportKey("spki", publicKey);
    const spkiArray = new Uint8Array(spkiBuffer);
    const spkiString = String.fromCharCode.apply(null, spkiArray);
    return btoa(spkiString);
}

async function firmarHashDocumento(privateKey, hashHex) {
    const hashBuffer = new Uint8Array(hashHex.match(/[\da-f]{2}/gi).map(h => parseInt(h, 16)));
    
    const firmaBuffer = await window.crypto.subtle.sign(
        { name: "ECDSA", hash: { name: "SHA-256" } },
        privateKey,
        hashBuffer
    );
    
    const firmaArray = new Uint8Array(firmaBuffer);
    let binary = "";
    firmaArray.forEach(b => binary += String.fromCharCode(b));
    return btoa(binary);
}