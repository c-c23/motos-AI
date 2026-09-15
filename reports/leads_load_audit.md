# leads_load_audit.md — REPORTE DE CARGA CONTROLADA DE LEADS REALES
**Fecha de ejecución:** 2026-09-15 10:34:01

## 1. Resumen General de Carga
| Métrica | Valor |
| :--- | :---: |
| Filas originales en `leads.csv` | **1503** |
| IDs de lead únicos | **1501** |
| Duplicados exactos deduplicados | **2** |
| Leads cargados / insertados nuevos en DB | **0** |
| Leads actualizados | **1194** |
| Leads sin cambios | **0** |
| Leads rechazados / pendientes por inconsistencia | **307** |
| Total `core.leads` en DB (Sintéticos + Reales) | **1201** |

---

## 2. Auditoría Detallada de Duplicados en `leads.csv` (2 IDs duplicados)
> **Regla aplicada:** Los 2 IDs duplicados (`LD-00011` y `LD-00251`) corresponden a **filas 100% idénticas** en todas sus columnas (mismo cliente, teléfono, email, fechas, canal, campaña y estado). Se conservó exactamente 1 fila por ID sin pérdida de información.

### Lead ID: `LD-00011`
- **Ocurrencias:** 2 filas
- **Diagnóstico de Identidad:** 100% Idéntico en todas las columnas
- **Acción tomada:** Conservada 1 sola fila representativa para inserción.

### Lead ID: `LD-00251`
- **Ocurrencias:** 2 filas
- **Diagnóstico de Identidad:** 100% Idéntico en todas las columnas
- **Acción tomada:** Conservada 1 sola fila representativa para inserción.


---

## 3. Normalización y Transformaciones Aplicadas
### A. Canales Originarios
- `WhatsApp`, `WHATSAPP`, `whatsapp` ➔ **WhatsApp**
- `Meta Ads`, `META ADS`, `meta ads` ➔ **Meta Ads**
- `Formulario Web`, `FORMULARIO WEB`, `formulario web` ➔ **Formulario Web**

### B. Estados de Gestión
- `Contactado`, `contactado` ➔ **Contactado**
- `Sin gestión`, `sin gestion`, `SIN GESTION` ➔ **Sin gestión**
- `No contesta`, `no contesta` ➔ **No contesta**
- `Cotización enviada` ➔ **Cotización enviada**
- `En proceso` ➔ **En proceso**
- `Descartado` ➔ **Descartado**

### C. Mapeo de Modelo de Interés a SKU (`core.motocicletas`)
- **Modelos mapeados determinísticamente a SKU:** 652 leads
- **Modelos conservados como texto original (SKU = NULL):** 769 leads (se preservó el texto sin forzar asignaciones ambiguas)

---

## 4. Detalle de Leads Rechazados / Pendientes (307 leads)
> **Inconsistencias FK y Fechas Inválidas:** Se rechazaron **306 leads** debido a que su `empresa_id` en `leads.csv` (`EMP-01`) no coincide con la `empresa_id` oficial de su `punto_venta_id` en `core.puntos_venta` (`EMP-02` o `EMP-03`). Adicionalmente se rechazó **1 lead** (`LD-01501`) por tener una fecha de registro calendáricamente imposible (`2026-08-33 10:00:00`).

| # | lead_id | empresa_id (CSV) | punto_venta_id | Motivo de Rechazo / Estado Pendiente |
| :---: | :--- | :---: | :---: | :--- |
| 1 | `LD-00012` | `EMP-01` | `PV-005` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-03) |
| 2 | `LD-00019` | `EMP-01` | `PV-004` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 3 | `LD-00022` | `EMP-01` | `PV-004` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 4 | `LD-00023` | `EMP-01` | `PV-003` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 5 | `LD-00024` | `EMP-01` | `PV-003` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 6 | `LD-00030` | `EMP-01` | `PV-003` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 7 | `LD-00031` | `EMP-01` | `PV-004` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 8 | `LD-00034` | `EMP-01` | `PV-004` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 9 | `LD-00040` | `EMP-01` | `PV-005` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-03) |
| 10 | `LD-00052` | `EMP-01` | `PV-004` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 11 | `LD-00054` | `EMP-01` | `PV-004` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 12 | `LD-00055` | `EMP-01` | `PV-003` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 13 | `LD-00061` | `EMP-01` | `PV-004` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 14 | `LD-00065` | `EMP-01` | `PV-003` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |
| 15 | `LD-00069` | `EMP-01` | `PV-004` | Inconsistencia FK: empresa en CSV (EMP-01) no coincide con empresa oficial del PV (EMP-02) |

*(Se omiten 292 filas adicionales por brevedad en el reporte)*


---

## 5. Validaciones de Seguridad e Integridad Referencial
- [x] **Protección de Leads Sintéticos:** Los 7 leads sintéticos (`LEAD-001` a `LEAD-007`) se mantuvieron 100% intactos.
- [x] **Transaccionalidad:** Carga dentro de bloque `with conn` con `commit` al finalizar.
- [x] **Idempotencia:** Inserción y actualización segura vía `ON CONFLICT (lead_id) DO UPDATE`.
- [x] **Sin destructividad:** Cero sentencias `DROP`, `TRUNCATE` o `DELETE`.
- [x] **Desacoplamiento:** No se insertaron conversaciones, mensajes ni histórico de cierres prematuramente.