-- ============================================================
-- MIGRACIÓN: cuentas de administrador del panel /mi-cuenta
-- Ejecutar UNA sola vez sobre smartech_db
-- Las cuentas NO se crean desde la web: usa crear_admin.py después
-- de correr esta migración.
-- ============================================================

CREATE TABLE IF NOT EXISTS administradores (
    id              SERIAL PRIMARY KEY,
    usuario         VARCHAR(50)  UNIQUE NOT NULL,
    nombre          VARCHAR(100),
    password_hash   VARCHAR(255) NOT NULL,   -- generado con werkzeug.security, nunca texto plano
    activo          BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion  TIMESTAMP    NOT NULL DEFAULT NOW(),
    ultimo_acceso   TIMESTAMP
);
