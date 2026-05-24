import base64
import binascii  # 1. Importa esto para convertir de hex a bytes
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

def verificar_firma_ecdsa(llave_publica_b64: str, hash_documento: str, firma_digital_b64: str) -> bool:
    try:
        public_key_bytes = base64.b64decode(llave_publica_b64)
        signature_bytes = base64.b64decode(firma_digital_b64)
        
        # --- NUEVO: Conversión Crítica de Raw P1363 (Web) a DER (Python) ---
        # Una firma P-256 en Web Crypto mide exactamente 64 bytes (32 para r, 32 para s).
        if len(signature_bytes) == 64:
            r = int.from_bytes(signature_bytes[:32], byteorder='big')
            s = int.from_bytes(signature_bytes[32:], byteorder='big')
            signature_bytes = encode_dss_signature(r, s)
            
        public_key = load_der_public_key(public_key_bytes)
        hash_bytes = binascii.unhexlify(hash_documento)
        
        public_key.verify(
            signature_bytes,
            hash_bytes, 
            ec.ECDSA(hashes.SHA256())
        )
        return True
    except Exception as e:
        print(f"⚠️ Fallo matemático en verificación ECDSA: {e}")
        return False