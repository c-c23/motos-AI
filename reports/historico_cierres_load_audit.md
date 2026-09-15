# historico_cierres_load_audit.md — REPORTE DE CARGA CONTROLADA DEL HISTÓRICO DE CIERRES
**Fecha de ejecución:** 2026-09-15 11:07:40

## 1. Fuente y Configuración
- **Archivo de origen:** `historico_cierres.csv`
- **Ruta:** `C:\motos-ai-leads\archivosreales\historico_cierres.csv` (o `archivosreales/historico_cierres.csv`) 
- **Tabla destino en PostgreSQL:** `core.historico_cierres`

---

## 2. Auditoría Previa del Dataset
- **Filas totales fuente:** 2200
- **Columnas:** 13
- **IDs únicos:** 2200 (`HX-00001` a `HX-02200`)
- **Duplicados de ID / Fila:** 0
- **Rango de Fechas:** 2026-03-01 ➔ 2026-07-28

---

## 3. Resultado de la Carga en PostgreSQL
| Métrica | Resultado |
| :--- | ---: |
| Filas fuente | **2200** |
| IDs únicos (`HX-...`) | **2200** |
| Insertados nuevos en DB | **0** |
| Omitidos por duplicado | **0** |
| Rechazados | **0** |
| Errores | **0** |
| **Total final en DB (`core.historico_cierres`)** | **2200** |

---

## 4. Validación de Datos y Distribuciones
### A. Distribución de Desenlaces
| Desenlace | Cantidad | Porcentaje |
| :--- | :---: | :---: |
| **Perdido** | 1824 | 82.91% |
| **Cerrado** | 197 | 8.95% |
| **Sin gestión** | 179 | 8.14% |

> **Tasa de Conversión sobre Casos Conocidos:** 197 cierres / 2.021 casos conocidos (`Perdido` + `Cerrado`) = **9.75%** (Coincidencia exacta con el análisis estadístico inicial).

### B. Rangos Numéricos y Nulos
- **`precio_lista`:** Min $4.990.000 ➔ Max $24.900.000 | Mean $10.566.222,73 | Nulos: 0
- **`horas_al_primer_contacto`:** Min 0.5h ➔ Max 120.0h | Mean 25.44h | Nulos: 179 (Preservados como NULL en DB)
- **`numero_contactos`:** Min 0 ➔ Max 7 | Mean 3.80 | Nulos: 0

### C. Mismatches Históricos Preservados
- **Registros con mismatch Empresa ↔ PV:** 447 registros.
- **Decisión Arquitectónica:** Se preservaron intactos los valores de `empresa_id` y `punto_venta_id` como snapshot original de fuente, manteniendo la trazabilidad histórica sin alteración silenciosa de datos.

---

## 5. Declaración de Integridad Referencial
- [x] **Independencia de Datasets:** El dataset `HX-00001...HX-02200` fue tratado como histórico independiente.
- [x] **Sin Relación Artificial:** Se garantiza 0 relaciones o FKs artificiales entre `HX-...` y `LD-...` o `LEAD-...`.
- [x] **Preservación de Excepción HUÉRFANOS TIPO A:** Las 12 conversaciones huérfanas tipo A continúan 100% fuera de DB (`in_db = 0`).

---

## 6. Verificación de Idempotencia
- **Primera ejecución:** Insertó 2.200 registros en `core.historico_cierres`.
- **Segunda ejecución:** Insertó 0 nuevos registros, 0 duplicados, 0 errores.

---

## 7. Preservación General del Sistema
- [x] `LEAD-001` a `LEAD-007` intactos en `core.leads` (7 registros).
- [x] `CONV-001` a `CONV-007` intactos en `core.conversaciones` (672 registros).
- [x] Scoring V1 intacto y pasando 100% de los tests automatizados.