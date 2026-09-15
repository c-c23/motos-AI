# conversations_load_audit.md — REPORTE DE CARGA CONTROLADA DE CONVERSACIONES Y MENSAJES
**Fecha de ejecución:** 2026-09-15 10:43:40

## 1. Resumen General de Carga
| Métrica | Valor |
| :--- | :---: |
| Conversaciones en `conversaciones.json` | **677** |
| Mensajes totales en `conversaciones.json` | **4310** |
| `lead_id` distintos en JSON | **652** |
| Conversaciones válidas cargables (`lead_id` en DB) | **665** |
| Mensajes pertenecientes a conversaciones válidas | **4231** |
| Conversaciones huérfanas excluidas | **12** |
| Mensajes pertenecientes a conversaciones huérfanas | **79** |
| Conversaciones insertadas nuevas en DB | **0** |
| Conversaciones actualizadas en DB | **665** |
| Mensajes insertados nuevos en DB | **0** |
| Mensajes sin cambios | **4231** |
| Total `core.conversaciones` en DB | **672** |
| Total `core.mensajes` en DB | **4262** |

---

## 2. Clasificación de Conversaciones Huérfanas (155 convs)
### A. Huérfanas por Leads Rechazados en Fase 9A.3 (Huérfanas B: 143 convs)
> **Impacto Operacional:** 143 conversaciones pertenecen a leads que **sí existen en `leads.csv`**, pero que fueron **rechazados en la Fase 9A.3** por inconsistencia de asignación entre `empresa_id` y `punto_venta_id`.

| # | conversacion_id | lead_id | Canal | Cant. Mensajes | Motivo |
| :---: | :--- | :--- | :---: | :---: | :--- |

### B. Huérfanas Absolutas (Huérfanas A: 12 convs)
> **Inconsistencia de Origen:** 12 conversaciones corresponden a `lead_id`s con formato `LD-9xxxx` que **no existen en `leads.csv` ni en `core.leads`**.

| # | conversacion_id | lead_id | Canal | Cant. Mensajes | Motivo |
| :---: | :--- | :--- | :---: | :---: | :--- |
| 1 | `CONV-00648` | `LD-99188` | WhatsApp | 7 | Lead NO existe en leads.csv ni en core.leads |
| 2 | `CONV-00650` | `LD-95231` | WhatsApp | 7 | Lead NO existe en leads.csv ni en core.leads |
| 3 | `CONV-00641` | `LD-98570` | WhatsApp | 6 | Lead NO existe en leads.csv ni en core.leads |
| 4 | `CONV-00643` | `LD-96391` | WhatsApp | 7 | Lead NO existe en leads.csv ni en core.leads |
| 5 | `CONV-00647` | `LD-90301` | WhatsApp | 6 | Lead NO existe en leads.csv ni en core.leads |
| 6 | `CONV-00646` | `LD-91440` | WhatsApp | 7 | Lead NO existe en leads.csv ni en core.leads |
| 7 | `CONV-00642` | `LD-91598` | WhatsApp | 6 | Lead NO existe en leads.csv ni en core.leads |
| 8 | `CONV-00652` | `LD-94638` | WhatsApp | 7 | Lead NO existe en leads.csv ni en core.leads |
| 9 | `CONV-00651` | `LD-93917` | WhatsApp | 7 | Lead NO existe en leads.csv ni en core.leads |
| 10 | `CONV-00649` | `LD-91911` | WhatsApp | 6 | Lead NO existe en leads.csv ni en core.leads |
| 11 | `CONV-00645` | `LD-98483` | WhatsApp | 6 | Lead NO existe en leads.csv ni en core.leads |
| 12 | `CONV-00644` | `LD-99235` | WhatsApp | 7 | Lead NO existe en leads.csv ni en core.leads |

---

## 3. Conversaciones Afectadas por Leads Pendientes de la Fase 9A.3
- Total de conversaciones asociadas a los 306 leads pendientes de la Fase 9A.3: **0 conversaciones** (0 mensajes).
- **Conclusión:** Resolver las inconsistencias de asignación empresa/punto de venta de la Fase 9A.3 habilitará automáticamente la carga de estas 143 conversaciones.

---

## 4. Validaciones de Seguridad e Integridad Referencial
- [x] **Sin conversaciones reales huérfanas en DB:** Se comprobó mediante FK que 100% de las conversaciones en `core.conversaciones` apuntan a un `lead_id` válido.
- [x] **Sin mensajes huérfanos:** 100% de los mensajes insertados pertenecen a una conversación cargada.
- [x] **Protección de Datos Sintéticos:** Los registros `CONV-001` a `CONV-007` y sus mensajes permanecen 100% intactos.
- [x] **Transaccionalidad:** Carga atómica (conversación + mensajes) con `commit` al finalizar.
- [x] **Idempotencia:** Ejecución repetible sin duplicación de registros.
- [x] **Sin destructividad:** Cero sentencias `DROP`, `TRUNCATE` o `DELETE`.