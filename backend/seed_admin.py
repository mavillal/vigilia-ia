#!/usr/bin/env python3
"""
seed_admin.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Crea el primer usuario (rol 'gerencia') para poder autenticarse en el
backend recién desplegado. Al ser un sistema 100% local sin proveedor de
identidad externo, este es el único mecanismo de bootstrap de acceso.

Uso:
  python seed_admin.py --username admin --password "clave-segura" --rol gerencia
"""

import argparse
import sys

from database import get_connection, init_db
from security import hash_password
import crud


def parse_args():
    p = argparse.ArgumentParser(description="Crear usuario inicial del backend VIGIL-IA")
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True, help="Mínimo 8 caracteres")
    p.add_argument("--rol", default="gerencia", choices=["operador", "supervisor", "gerencia"])
    return p.parse_args()


def main():
    args = parse_args()
    if len(args.password) < 8:
        print("La contraseña debe tener al menos 8 caracteres.")
        sys.exit(1)

    init_db()
    conn = get_connection()
    try:
        existente = crud.get_usuario_by_username(conn, args.username)
        if existente:
            print(f"El usuario '{args.username}' ya existe (rol: {existente['rol']}).")
            sys.exit(1)

        usuario = crud.create_usuario(
            conn,
            username=args.username,
            password_hash=hash_password(args.password),
            rol=args.rol,
        )
        print(f"Usuario creado: {usuario['username']} (rol: {usuario['rol']})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
