"""
crear_admin.py
===============
Única forma de crear (o resetear la contraseña de) una cuenta de
administrador: correr este script desde la terminal del servidor.

NO existe ningún formulario web de registro — tal como se pidió, las
cuentas "solo se crean por base de datos".

Uso:
    python crear_admin.py
"""

import getpass
from werkzeug.security import generate_password_hash
from services import obtener_conexion


def main():
    print("=== Crear / actualizar cuenta de administrador — SmartTech ===\n")
    usuario = input("Usuario (login): ").strip()
    nombre = input("Nombre completo: ").strip()
    password = getpass.getpass("Contraseña (mín. 8 caracteres): ")
    password2 = getpass.getpass("Repite la contraseña: ")

    if not usuario:
        print("❌ El usuario no puede estar vacío.")
        return
    if password != password2:
        print("❌ Las contraseñas no coinciden.")
        return
    if len(password) < 8:
        print("❌ La contraseña debe tener al menos 8 caracteres.")
        return

    password_hash = generate_password_hash(password)

    conn = obtener_conexion()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO administradores (usuario, nombre, password_hash)
            VALUES (%s, %s, %s)
            ON CONFLICT (usuario) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    nombre = EXCLUDED.nombre,
                    activo = TRUE;
            """,
            (usuario, nombre, password_hash)
        )
        conn.commit()
        print(f"\n✅ Cuenta '{usuario}' creada/actualizada correctamente.")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error al guardar la cuenta: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    main()
