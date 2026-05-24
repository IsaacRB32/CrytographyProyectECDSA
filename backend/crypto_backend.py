import base64
import binascii  # 1. Importa esto para convertir de hex a bytes
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

def verificar_firma_ecdsa(llave_publica_b64: str, hash_documento: str, firma_digital_b64: str) -> bool:
    try:
        # 1. Decodificar llave y firma desde Base64
        public_key_bytes = base64.b64decode(llave_publica_b64)
        signature_bytes = base64.b64decode(firma_digital_b64)
        
        # 2. Reconstruir objeto de llave pública
        public_key = load_der_public_key(public_key_bytes)
        
        # 3. CONVERSIÓN CRÍTICA: De hexadecimal a bytes binarios puros
        # Ejemplo: "e3b0c..." (texto) -> 0xe3, 0xb0, ... (bytes)
        hash_bytes = binascii.unhexlify(hash_documento)
        
        # 4. Verificar firma
        public_key.verify(
            signature_bytes,
            hash_bytes, # Pasamos los bytes puros, no el texto codificado
            ec.ECDSA(hashes.SHA256())
        )
        # Dentro de verificar_firma_ecdsa
        print(f"DEBUG: Llave pública recibida: {llave_publica_b64[:20]}...")
        print(f"DEBUG: Hash a verificar (bytes): {binascii.hexlify(hash_bytes)}")
        return True
    except Exception as e:
        print(f"⚠️ Fallo matemático en verificación ECDSA: {e}")
        return False