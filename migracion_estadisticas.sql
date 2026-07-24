-- ============================================================
-- MIGRACIÓN: registro de interacciones del chatbot (estadísticas)
-- Ejecutar UNA sola vez sobre smartech_db (la misma BD del chat)
-- ============================================================

CREATE TABLE IF NOT EXISTS chat_log (
    id               SERIAL PRIMARY KEY,
    sesion_id        VARCHAR(64)   NOT NULL,       -- identifica una conversación (una pestaña/usuario)
    fecha_hora       TIMESTAMP     NOT NULL DEFAULT NOW(),
    paso             INTEGER,                       -- paso del flujo (1..5) en el momento del mensaje
    evento           VARCHAR(40)   NOT NULL DEFAULT 'mensaje',  -- 'mensaje', 'proforma_generada', 'periferico_agregado', 'chat_finalizado'
    mensaje_usuario  VARCHAR(500),                  -- texto recibido (recortado a 500 caracteres)
    perfil           VARCHAR(60),                   -- perfil ya definido en esa sesión, si existe
    formato          VARCHAR(60),                   -- formato ya definido en esa sesión, si existe
    presupuesto      NUMERIC(10, 2)                 -- presupuesto ya definido en esa sesión, si existe
);

-- Índices para que las consultas de estadísticas por rango de fechas sean rápidas
CREATE INDEX IF NOT EXISTS idx_chat_log_fecha  ON chat_log (fecha_hora);
CREATE INDEX IF NOT EXISTS idx_chat_log_sesion ON chat_log (sesion_id);
