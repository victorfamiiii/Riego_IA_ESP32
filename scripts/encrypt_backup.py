#!/usr/bin/env python3
"""
encrypt_backup.py — cifra un backup con AES-256-GCM.

Uso:
    export BACKUP_ENCRYPTION_KEY="hex_de_64_caracteres"
    python3 encrypt_backup.py /ruta/al/backup.zip

Salida por defecto:
    /ruta/al/backup.zip.enc
"""

import argparse
import os
import struct
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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
        print("Genera una con: python3 -c \"import secrets; print(secrets.token_hex(32))\"")
        sys.exit(1)
    try:
        return bytes.fromhex(hex_key)
    except ValueError:
        print("ERROR: BACKUP_ENCRYPTION_KEY no es hexadecimal válido.")
        sys.exit(1)


def encrypt_file(input_path: Path, output_path: Path) -> None:
    key = get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)

    data = input_path.read_bytes()
    ciphertext = aesgcm.encrypt(nonce, data, None)

    with open(output_path, "wb") as f:
        f.write(MAGIC)
        f.write(VERSION)
        f.write(nonce)
        f.write(struct.pack("<Q", len(ciphertext)))
        f.write(ciphertext)

    print(f"[encrypt] Archivo original : {input_path}")
    print(f"[encrypt] Archivo cifrado  : {output_path}")
    print(f"[encrypt] Tamaño original  : {input_path.stat().st_size} bytes")
    print(f"[encrypt] Tamaño cifrado   : {output_path.stat().st_size} bytes")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cifra un backup con AES-256-GCM")
    parser.add_argument("input", help="Archivo de entrada (.zip o .tar.gz)")
    parser.add_argument("-o", "--output", help="Archivo de salida (.enc)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"ERROR: no existe el archivo: {input_path}")
        sys.exit(1)

    output_path = Path(args.output) if args.output else Path(str(input_path) + ".enc")
    encrypt_file(input_path, output_path)


if __name__ == "__main__":
    main()