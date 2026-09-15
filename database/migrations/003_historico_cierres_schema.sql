-- database/migrations/003_historico_cierres_schema.sql
-- Crea la tabla core.historico_cierres para la persistencia del dataset histórico de cierres (HX-00001 a HX-02200).

CREATE TABLE IF NOT EXISTS core.historico_cierres (
    historico_lead_id         VARCHAR(50) PRIMARY KEY,
    registrado_en            TIMESTAMP NOT NULL,
    canal                    VARCHAR(50) NOT NULL,
    empresa_id               VARCHAR(50) REFERENCES core.empresas(empresa_id),
    punto_venta_id           VARCHAR(50) REFERENCES core.puntos_venta(punto_venta_id),
    modelo_cotizado          VARCHAR(100) NOT NULL,
    precio_lista             NUMERIC(12, 2) NOT NULL,
    horas_al_primer_contacto NUMERIC(6, 2) NULL,
    numero_contactos         INTEGER NOT NULL,
    manifesto_cuota_inicial  VARCHAR(20) NOT NULL,
    forma_pago_declarada     VARCHAR(50) NOT NULL,
    pidio_cita               VARCHAR(10) NOT NULL,
    desenlace                VARCHAR(50) NOT NULL,
    creado_en                TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Índices de consulta frecuente para análisis histórico
CREATE INDEX IF NOT EXISTS idx_historico_cierres_pv ON core.historico_cierres(punto_venta_id);
CREATE INDEX IF NOT EXISTS idx_historico_cierres_empresa ON core.historico_cierres(empresa_id);
CREATE INDEX IF NOT EXISTS idx_historico_cierres_desenlace ON core.historico_cierres(desenlace);
CREATE INDEX IF NOT EXISTS idx_historico_cierres_registrado ON core.historico_cierres(registrado_en);
