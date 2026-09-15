-- database/migrations/002_scoring_v1_schema.sql
-- Actualiza el tipo de dato y restricciones de puntaje_prioridad a NUMERIC (0-100) para el Scoring V1.

DROP VIEW IF EXISTS core.vw_leads_gestion CASCADE;

ALTER TABLE core.puntajes_leads ALTER COLUMN puntaje_prioridad TYPE NUMERIC;

-- Actualizar restricción check_priority_score para la escala 0 - 100
ALTER TABLE core.puntajes_leads DROP CONSTRAINT IF EXISTS chk_priority_score;
ALTER TABLE core.puntajes_leads ADD CONSTRAINT chk_priority_score CHECK (
    puntaje_prioridad IS NULL OR (puntaje_prioridad >= 0 AND puntaje_prioridad <= 100)
);

-- Sincronizar secuencia de puntaje_id
SELECT setval(
    pg_get_serial_sequence('core.puntajes_leads', 'puntaje_id'),
    COALESCE((SELECT MAX(puntaje_id) FROM core.puntajes_leads), 1)
);

CREATE VIEW core.vw_leads_gestion AS
SELECT 
    l.lead_id,
    l.nombre_cliente,
    l.telefono,
    l.correo,
    l.ciudad,
    l.canal,
    l.campana,
    l.empresa_id,
    emp.nombre AS empresa,
    l.punto_venta_id,
    pv.nombre AS punto_venta,
    l.sku_motocicleta,
    m.marca,
    m.linea,
    m.cilindraje_cc,
    m.segmento,
    m.precio_lista,
    e.pago_inicial,
    e.metodo_pago,
    e.intencion_declarada,
    e.objecion_principal,
    e.solicita_cotizacion,
    e.solicita_cita,
    p.probabilidad_comercial,
    p.puntaje_urgencia,
    p.puntaje_prioridad,
    p.temperatura,
    a.asesor_id,
    asr.nombre AS asesor,
    l.estado_gestion,
    l.primer_contacto_en,
    l.registrado_en,
    l.actualizado_en
FROM core.leads l
LEFT JOIN core.empresas emp ON l.empresa_id = emp.empresa_id
LEFT JOIN core.puntos_venta pv ON l.punto_venta_id = pv.punto_venta_id
LEFT JOIN core.motocicletas m ON l.sku_motocicleta = m.sku
LEFT JOIN core.extracciones_ia e ON l.lead_id = e.lead_id
LEFT JOIN core.puntajes_leads p ON l.lead_id = p.lead_id AND p.es_actual = true
LEFT JOIN core.asignaciones a ON l.lead_id = a.lead_id AND a.es_actual = true
LEFT JOIN core.asesores asr ON a.asesor_id = asr.asesor_id;
