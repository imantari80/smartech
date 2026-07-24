"""
chat_logger.py
================
Registro de interacciones del chatbot SmartTech, para fines estadísticos.

Cada vez que un usuario envía un mensaje a /api/chat se guarda una fila en
la tabla `chat_log` (ver migracion_estadisticas.sql) con la fecha/hora, el
paso del flujo, y su perfil/formato/presupuesto si ya los definió.

Con esto se puede responder preguntas como:
- ¿Cuántas consultas (mensajes) recibió el chatbot hoy / esta semana / este mes?
- ¿Cuántas conversaciones (sesiones) distintas hubo en un rango de fechas?
- ¿Qué perfil de usuario o formato de equipo es el más consultado?

Principio de diseño: el logging es "best effort". Si falla por cualquier
motivo (BD caída, etc.), NUNCA debe interrumpir ni degradar la respuesta
real del chatbot al usuario.
"""

import uuid
import logging

logger = logging.getLogger(__name__)


def obtener_sesion_id(session_obj):
    """Devuelve el identificador de sesión persistente del usuario (una
    conversación completa), creándolo la primera vez que escribe."""
    if not session_obj.get('sesion_id'):
        session_obj['sesion_id'] = uuid.uuid4().hex
    return session_obj['sesion_id']


def registrar_evento(conn, cursor, sesion_id, paso, mensaje_usuario,
                      perfil=None, formato=None, presupuesto=None,
                      evento='mensaje'):
    """
    Inserta una fila en chat_log y hace commit (el resto del flujo del chat
    solo hace SELECTs, así que el commit de esta función es independiente).

    No lanza excepciones hacia afuera: un error al registrar estadísticas
    jamás debe romper la respuesta del chatbot.
    """
    if cursor is None or conn is None:
        return

    try:
        cursor.execute(
            """
            INSERT INTO chat_log
                (sesion_id, paso, mensaje_usuario, perfil, formato, presupuesto, evento)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """,
            (
                sesion_id,
                paso,
                (mensaje_usuario or '')[:500],
                perfil,
                formato,
                presupuesto,
                evento,
            )
        )
        conn.commit()
    except Exception:
        logger.exception("No se pudo registrar el evento de estadísticas del chat")
        try:
            conn.rollback()
        except Exception:
            pass
