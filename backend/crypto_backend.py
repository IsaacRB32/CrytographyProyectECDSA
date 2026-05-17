# backend/crypto_backend.py
import base64
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

def verificar_firma_ecdsa(llave_publica_b64: str, hash_documento: str, firma_digital_b64: str) -> bool:
    """
    Verifica matemáticamente una firma digital ECDSA utilizando la curva NIST P-256.
    
    :param llave_publica_b64: Llave pública en formato SPKI codificada en Base64.
    :param hash_documento: El hash SHA-256 en texto plano (hexadecimal) firmado.
    :param firma_digital_b64: La firma digital (r, s) codificada en Base64.
    :return: True si la firma es íntegra y legítima, False si fue alterada.
    """
    try:
        # 1. Decodificar la llave pública SPKI desde Base64 a bytes crudos (DER)
        public_key_bytes = base64.b64decode(llave_publica_b64)
        
        # 2. Reconstruir el objeto geométrico de la llave pública
        public_key = load_der_public_key(public_key_bytes)
        
        # 3. Decodificar la firma digital de Base64 a bytes
        signature_bytes = base64.b64decode(firma_digital_b64)
        
        # 4. Validar la ecuación de la curva elíptica P-256
        public_key.verify(
            signature_bytes,
            hash_documento.encode('utf-8'),
            ec.ECDSA(hashes.SHA256())
        )
        return True
    except Exception as e:
        print(f"⚠️ Fallo matemático en verificación ECDSA: {e}")
        return False