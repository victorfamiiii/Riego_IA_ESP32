#!/usr/bin/env python3
"""
decrypt_backup.py — descifra un backup generado por encrypt_backup.py.

Uso:
    export BACKUP_ENCRYPTION_KEY="hex_de_64_caracteres"
    python3 decrypt_backup.py /ruta/al/backup.zip.enc

Salida por defecto:
    /ruta/al/backup.zip
"""

import argparse
import os
import struct
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
except ImportError:
    print("ERROR: falta la librería 'cryptography'. Instala: sudo apt install python3-cryptography")
    sys.exit(1)

MAGIC = b"ESP32BAK"
VERSION = b"\x01"  # Versión 1 del formato de archivo cifrado
NONCE_SIZE = 12


def get_key() -> bytes:
    hex_key = os.environ.get("BACKUP_ENCRYPTION_KEY", "")
    if len(hex_key) != 64:
        print("ERROR: BACKUP_ENCRYPTION_KEY debe tener 64 caracteres hexadecimales (32 bytes).")
        sys.exit(1)
    try:
        return bytes.fromhex(hex_key)
    except ValueError:
        print("ERROR: BACKUP_ENCRYPTION_KEY no es hexadecimal válido.")
        sys.exit(1)


def decrypt_file(input_path: Path, output_path: Path) -> None:
    key = get_key()
    aesgcm = AESGCM(key)

    with open(input_path, "rb") as f:
        magic = f.read(8)
        if magic != MAGIC:
            print("ERROR: formato inválido (magic incorrecto).")
            sys.exit(1)

        version = f.read(1)
        if version != VERSION:
            print("ERROR: versión de formato no soportada.")
            sys.exit(1)

        nonce = f.read(NONCE_SIZE)
        if len(nonce) != NONCE_SIZE:
            print("ERROR: archivo corrupto (nonce incompleto).")
            sys.exit(1)

        size_data = f.read(8)
        if len(size_data) != 8:
            print("ERROR: archivo corrupto (tamaño incompleto).")
            sys.exit(1)

        ciphertext_size = struct.unpack("<Q", size_data)[0]
        ciphertext = f.read(ciphertext_size)
        if len(ciphertext) != ciphertext_size:
            print("ERROR: archivo corrupto (ciphertext incompleto).")
            sys.exit(1)

    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        print("ERROR: autenticación fallida. Clave incorrecta o archivo alterado.")
        sys.exit(1)

    output_path.write_bytes(plaintext)

    print(f"[decrypt] Archivo cifrado    : {input_path}")
    print(f"[decrypt] Archivo descifrado : {output_path}")
    print(f"[decrypt] Tamaño descifrado  : {output_path.stat().st_size} bytes")


def main() -> None:
    parser = argparse.ArgumentParser(description="Descifra un backup AES-256-GCM")
    parser.add_argument("input", help="Archivo cifrado (.enc)")
    parser.add_argument("-o", "--output", help="Archivo de salida")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"ERROR: no existe el archivo: {input_path}")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        name = str(input_path)
        output_path = Path(name[:-4]) if name.endswith('.enc') else Path(name + '.dec')

    decrypt_file(input_path, output_path)


if __name__ == "__main__":
    main()