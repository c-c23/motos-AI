-- database/migrations/004_assignment_persistence.sql
-- Fase 9D.3: Migración para soporte de persistencia e idempotencia de asignaciones.

-- 1. Índice único condicional: garantiza que un lead nunca tenga más de una asignación activa a la vez.
CREATE UNIQUE INDEX IF NOT EXISTS uq_asignaciones_lead_actual
    ON core.asignaciones (lead_id)
    WHERE es_actual = true;

-- 2. Índice para acelerar el cálculo de carga diaria por asesor y fecha
CREATE INDEX IF NOT EXISTS idx_asignaciones_asesor_fecha_actual
    ON core.asignaciones (asesor_id, CAST(asignado_en AS date))
    WHERE es_actual = true;
