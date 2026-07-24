"""
auth.py
=======
Autenticación del panel de administración de SmartTech.

IMPORTANTE: no existe ningún formulario de registro. Las cuentas de
administrador se crean ÚNICAMENTE por base de datos, corriendo el script
`crear_admin.py` (o insertando manualmente en la tabla `administradores`).
Este módulo solo valida credenciales contra esa tabla y protege las
rutas del dashboard.
"""

from functools import wraps
from flask import session, redirect, url_for
from werkzeug.security import check_password_hash

from services import obtener_conexion


def verificar_credenciales(usuario, password):
    """
    Verifica usuario/contraseña contra la tabla `administradores`.

    Retorna un dict {id, usuario, nombre} si son válidos y la cuenta está
    activa; retorna None en cualquier otro caso (usuario inexistente,
    contraseña incorrecta o cuenta desactivada).
    """
    if not usuario or not password:
        return None

    conn = obtener_conexion()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, usuario, nombre, password_hash, activo
            FROM administradores
            WHERE usuario = %s;
            """,
            (usuario,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        admin_id, usuario_db, nombre, password_hash, activo = row

        if not activo:
            return None
        if not check_password_hash(password_hash, password):
            return None

        # Registrar el último acceso (informativo, no afecta el login si falla)
        try:
            cursor.execute(
                "UPDATE administradores SET ultimo_acceso = NOW() WHERE id = %s;",
                (admin_id,)
            )
            conn.commit()
        except Exception:
            conn.rollback()

        return {"id": admin_id, "usuario": usuario_db, "nombre": nombre}
    finally:
        cursor.close()
        conn.close()


def login_requerido(vista):
    """Decorador para proteger rutas del dashboard/API de estadísticas.
    Si no hay sesión de administrador activa, redirige al login."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not session.get('admin_id'):
            return redirect(url_for('chat.mi_cuenta'))
        return vista(*args, **kwargs)
    return envoltura
