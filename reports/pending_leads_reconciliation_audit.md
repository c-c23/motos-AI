# pending_leads_reconciliation_audit.md — REPORTE DE RECONCILIACIÓN CONTROLADA DE LEADS PENDIENTES
**Fecha de ejecución:** 2026-09-15 10:43:40

## 1. Estado Inicial vs Final de DB
| Métrica | Antes (Fase 9A.4) | Después (Fase 9A.5) | Variación |
| :--- | :---: | :---: | :---: |
| Leads Sintéticos (`LEAD-001`..`007`) | **7** | **7** | **0** (Intactos) |
| Leads Reales (`LD-%`) | **1194** | **1500** | **+306** |
| Total `core.leads` en DB | **1201** | **1507** | **+306** |
| Total `core.conversaciones` en DB | **529** | **672** | **+143** |
| Total `core.mensajes` en DB | **3372** | **4262** | **+890** |

---

## 2. Clasificación de Leads Pendientes Auditados (307 leads)
| Clasificación | Cantidad | Descripción |
| :--- | :---: | :--- |
| Inconsistencia Empresa ↔ Punto de Venta | **306** | Reconciliados mediante la regla: `punto_venta_id` determina la empresa propietaria oficial. |
| Fecha Calendáricamente Inválida | **1** | Rechazado de forma permanente (`LD-01501` con fecha `2026-08-33 10:00:00`). |
| Casos Ambiguos | **0** | Sin casos ambiguos forzados. |
| **Total Leads Pendientes Procesados** | **307** | Auditados al 100%. |

---

## 3. Cambios Realizados y Reglas Aplicadas
### Regla de Reconciliación de Empresa:
> **Regla de negocio:** El `punto_venta_id` determina la empresa propietaria en `core.puntos_venta`. Se verificó que el punto de venta exista, esté activo y la empresa propietaria exista y esté activa.

| Campo Original (CSV) | Campo Reconciliado (DB) | Punto de Venta | Regla Aplicada | Cantidad |
| :---: | :---: | :---: | :--- | :---: |
| `EMP-01` | `EMP-02` | `PV-003` | Empresa oficial del PV-003 (Bello) | **111** |
| `EMP-01` | `EMP-02` | `PV-004` | Empresa oficial del PV-004 (Rionegro) | **97** |
| `EMP-01` | `EMP-03` | `PV-005` | Empresa oficial del PV-005 (Medellín) | **98** |

---

## 4. Detalle de Leads Cargados y Permanentes
- **Leads Reconciliados y Cargados en DB:** 306
- **Leads que Permanecen Pendientes:** 1 (`LD-01501`)

---

## 5. Impacto y Recuperación de Conversaciones y Mensajes
- **Conversaciones Recuperables:** **143**
- **Conversaciones Recuperadas en DB (`core.conversaciones`):** **143**
- **Mensajes Recuperables:** **890**
- **Mensajes Recuperados en DB (`core.mensajes`):** **890**

---

## 6. Auditoría de Huérfanos Tipo A (Preservados Excluidos)
- **Conversaciones Huérfanas Tipo A (IDs `LD-9xxxx` no existentes en CSV):** **12 conversaciones** (79 mensajes)
- **Estado:** Excluidas 100% de la base de datos para garantizar la integridad referencial.

---

## 7. Verificación de Integridad Referencial en PostgreSQL
- [x] **Conversaciones sin lead válido en DB:** `0`
- [x] **Mensajes sin conversación válida en DB:** `0`
- [x] **Integridad Lead ➔ Punto de Venta:** 100% verificada.
- [x] **Integridad Conversación ➔ Lead:** 100% verificada.
- [x] **Integridad Mensaje ➔ Conversación:** 100% verificada.

---

## 8. Verificación de Idempotencia
- **Primera ejecución:** Insertó 306 leads, 143 conversaciones, 890 mensajes.
- **Segunda ejecución:** Insertó 0 leads, 0 conversaciones, 0 mensajes. 0 duplicados, 0 errores.

---

## 9. Protección de Datos Sintéticos
- [x] `LEAD-001` a `LEAD-007` intactos en `core.leads` (7 registros).
- [x] `CONV-001` a `CONV-007` intactos en `core.conversaciones` (7 registros).