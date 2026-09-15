# advisors_reconciliation_9d0_audit.md — AUDITORÍA Y RECONCILIACIÓN DE ASESORES FALTANTES
**Fecha de ejecución:** 2026-09-15 15:02:40  
**Fase del Proyecto:** FASE 9D.0 — Auditoría Técnica Exclusiva (READ-ONLY)  
**Base de Datos:** PostgreSQL 18.6 (`motos_database`), Esquema `core`  

---

## 1. Resumen Ejecutivo

| Métrica | Valor | Observación |
| :--- | :---: | :--- |
| **Asesores en CSV real** | **42** | Registros en `archivosreales/asesores.csv` |
| **Asesores únicos en CSV** | **42** | Sin IDs duplicados en el archivo origen |
| **Asesores actuales en BD** | **34** | Registros activos en `core.asesores` |
| **Asesores faltantes auditados** | **8** | `AS-009` al `AS-016` |
| **Inconsistencias detectadas** | **8** | Discrepancia entre `empresa_id` del CSV y la empresa del punto de venta |
| **Casos cargables sin corrección** | **0** | 0 registros cumplen la FK compuesta `(empresa_id, punto_venta_id)` |
| **Casos pendientes de reconciliación** | **8** | Requieren validación de regla de negocio o confirmación de fuente |
| **Modificaciones a PostgreSQL** | **0 (NO)** | Auditoría 100% de solo lectura (`READ-ONLY`) |

---

## 2. Fuente CSV

- **Archivo auditado:** `archivosreales/asesores.csv`
- **Número total de filas:** 42
- **IDs únicos:** 42
- **Codificación utilizada/detectada:** `utf-8` (permite decodificación correcta de tildes y caracteres como ñ)
- **Columnas detectadas:** `asesor_id, nombre, punto_venta_id, empresa_id, capacidad_diaria_leads, activo, fecha_ingreso`

### Registro crudo de los 8 asesores faltantes en el CSV:

| asesor_id | nombre | punto_venta_id | empresa_id | capacidad_diaria_leads | activo | fecha_ingreso |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `AS-009` | Liliana Muñoz Zapata | `PV-003` | `EMP-01` | 18 | SI | 2025-06-28 |
| `AS-010` | Paula Andrea Londoño Cardona | `PV-003` | `EMP-01` | 18 | SI | 2024-04-27 |
| `AS-011` | Sebastián Valencia Cardona | `PV-003` | `EMP-01` | 12 | SI | 2025-11-28 |
| `AS-012` | Julián Osorio Mosquera | `PV-003` | `EMP-01` | 18 | SI | 2025-10-18 |
| `AS-013` | Liliana Londoño Bedoya | `PV-004` | `EMP-01` | 12 | SI | 2024-04-22 |
| `AS-014` | Luz Marina Cardona Mosquera | `PV-004` | `EMP-01` | 20 | SI | 2024-10-26 |
| `AS-015` | Katherine Vargas Jiménez | `PV-005` | `EMP-01` | 25 | SI | 2026-04-27 |
| `AS-016` | Leidy Johana Castaño Jiménez | `PV-005` | `EMP-01` | 15 | SI | 2026-03-28 |

---

## 3. Auditoría Individual (AS-009 a AS-016)

Detalle técnico individual de cada uno de los 8 asesores pendientes:

### Asesor `AS-009` — Liliana Muñoz Zapata
- **Datos CSV:** `empresa_id='EMP-01'`, `punto_venta_id='PV-003'`, `capacidad=18`, `activo=SI`, `fecha_ingreso=2025-06-28`
- **Datos BD (`core.asesores`):** NO EXISTE (0 registros encontrados)
- **Empresa declarada (CSV):** `EMP-01` (Motos Andinas)
- **Punto de venta declarado (CSV):** `PV-003` (MotoRisaralda Dosquebradas - Dosquebradas)
- **Empresa oficial del PV en BD (`core.puntos_venta`):** `EMP-02` (MotoRisaralda)
- **Validación de Relación:** `INCONSISTENCIA_EMPRESA_PV` (`EMP-01` != `EMP-02`)
- **Dependencias en BD:** `core.asignaciones`: 0 | `core.eventos_gestion`: 0
- **Conclusión:** No puede cargarse tal como viene en el CSV debido a la restricción de clave foránea compuesta `fk_adviser_sales_point` (`FOREIGN KEY (empresa_id, punto_venta_id) REFERENCES core.puntos_venta(empresa_id, punto_venta_id)`). Estado: `PENDIENTE_RECONCILIACION`.

### Asesor `AS-010` — Paula Andrea Londoño Cardona
- **Datos CSV:** `empresa_id='EMP-01'`, `punto_venta_id='PV-003'`, `capacidad=18`, `activo=SI`, `fecha_ingreso=2024-04-27`
- **Datos BD (`core.asesores`):** NO EXISTE (0 registros encontrados)
- **Empresa declarada (CSV):** `EMP-01` (Motos Andinas)
- **Punto de venta declarado (CSV):** `PV-003` (MotoRisaralda Dosquebradas - Dosquebradas)
- **Empresa oficial del PV en BD (`core.puntos_venta`):** `EMP-02` (MotoRisaralda)
- **Validación de Relación:** `INCONSISTENCIA_EMPRESA_PV` (`EMP-01` != `EMP-02`)
- **Dependencias en BD:** `core.asignaciones`: 0 | `core.eventos_gestion`: 0
- **Conclusión:** No puede cargarse tal como viene en el CSV debido a la restricción de clave foránea compuesta `fk_adviser_sales_point` (`FOREIGN KEY (empresa_id, punto_venta_id) REFERENCES core.puntos_venta(empresa_id, punto_venta_id)`). Estado: `PENDIENTE_RECONCILIACION`.

### Asesor `AS-011` — Sebastián Valencia Cardona
- **Datos CSV:** `empresa_id='EMP-01'`, `punto_venta_id='PV-003'`, `capacidad=12`, `activo=SI`, `fecha_ingreso=2025-11-28`
- **Datos BD (`core.asesores`):** NO EXISTE (0 registros encontrados)
- **Empresa declarada (CSV):** `EMP-01` (Motos Andinas)
- **Punto de venta declarado (CSV):** `PV-003` (MotoRisaralda Dosquebradas - Dosquebradas)
- **Empresa oficial del PV en BD (`core.puntos_venta`):** `EMP-02` (MotoRisaralda)
- **Validación de Relación:** `INCONSISTENCIA_EMPRESA_PV` (`EMP-01` != `EMP-02`)
- **Dependencias en BD:** `core.asignaciones`: 0 | `core.eventos_gestion`: 0
- **Conclusión:** No puede cargarse tal como viene en el CSV debido a la restricción de clave foránea compuesta `fk_adviser_sales_point` (`FOREIGN KEY (empresa_id, punto_venta_id) REFERENCES core.puntos_venta(empresa_id, punto_venta_id)`). Estado: `PENDIENTE_RECONCILIACION`.

### Asesor `AS-012` — Julián Osorio Mosquera
- **Datos CSV:** `empresa_id='EMP-01'`, `punto_venta_id='PV-003'`, `capacidad=18`, `activo=SI`, `fecha_ingreso=2025-10-18`
- **Datos BD (`core.asesores`):** NO EXISTE (0 registros encontrados)
- **Empresa declarada (CSV):** `EMP-01` (Motos Andinas)
- **Punto de venta declarado (CSV):** `PV-003` (MotoRisaralda Dosquebradas - Dosquebradas)
- **Empresa oficial del PV en BD (`core.puntos_venta`):** `EMP-02` (MotoRisaralda)
- **Validación de Relación:** `INCONSISTENCIA_EMPRESA_PV` (`EMP-01` != `EMP-02`)
- **Dependencias en BD:** `core.asignaciones`: 0 | `core.eventos_gestion`: 0
- **Conclusión:** No puede cargarse tal como viene en el CSV debido a la restricción de clave foránea compuesta `fk_adviser_sales_point` (`FOREIGN KEY (empresa_id, punto_venta_id) REFERENCES core.puntos_venta(empresa_id, punto_venta_id)`). Estado: `PENDIENTE_RECONCILIACION`.

### Asesor `AS-013` — Liliana Londoño Bedoya
- **Datos CSV:** `empresa_id='EMP-01'`, `punto_venta_id='PV-004'`, `capacidad=12`, `activo=SI`, `fecha_ingreso=2024-04-22`
- **Datos BD (`core.asesores`):** NO EXISTE (0 registros encontrados)
- **Empresa declarada (CSV):** `EMP-01` (Motos Andinas)
- **Punto de venta declarado (CSV):** `PV-004` (MotoRisaralda Manizales - Manizales)
- **Empresa oficial del PV en BD (`core.puntos_venta`):** `EMP-02` (MotoRisaralda)
- **Validación de Relación:** `INCONSISTENCIA_EMPRESA_PV` (`EMP-01` != `EMP-02`)
- **Dependencias en BD:** `core.asignaciones`: 0 | `core.eventos_gestion`: 0
- **Conclusión:** No puede cargarse tal como viene en el CSV debido a la restricción de clave foránea compuesta `fk_adviser_sales_point` (`FOREIGN KEY (empresa_id, punto_venta_id) REFERENCES core.puntos_venta(empresa_id, punto_venta_id)`). Estado: `PENDIENTE_RECONCILIACION`.

### Asesor `AS-014` — Luz Marina Cardona Mosquera
- **Datos CSV:** `empresa_id='EMP-01'`, `punto_venta_id='PV-004'`, `capacidad=20`, `activo=SI`, `fecha_ingreso=2024-10-26`
- **Datos BD (`core.asesores`):** NO EXISTE (0 registros encontrados)
- **Empresa declarada (CSV):** `EMP-01` (Motos Andinas)
- **Punto de venta declarado (CSV):** `PV-004` (MotoRisaralda Manizales - Manizales)
- **Empresa oficial del PV en BD (`core.puntos_venta`):** `EMP-02` (MotoRisaralda)
- **Validación de Relación:** `INCONSISTENCIA_EMPRESA_PV` (`EMP-01` != `EMP-02`)
- **Dependencias en BD:** `core.asignaciones`: 0 | `core.eventos_gestion`: 0
- **Conclusión:** No puede cargarse tal como viene en el CSV debido a la restricción de clave foránea compuesta `fk_adviser_sales_point` (`FOREIGN KEY (empresa_id, punto_venta_id) REFERENCES core.puntos_venta(empresa_id, punto_venta_id)`). Estado: `PENDIENTE_RECONCILIACION`.

### Asesor `AS-015` — Katherine Vargas Jiménez
- **Datos CSV:** `empresa_id='EMP-01'`, `punto_venta_id='PV-005'`, `capacidad=25`, `activo=SI`, `fecha_ingreso=2026-04-27`
- **Datos BD (`core.asesores`):** NO EXISTE (0 registros encontrados)
- **Empresa declarada (CSV):** `EMP-01` (Motos Andinas)
- **Punto de venta declarado (CSV):** `PV-005` (Motos del Eje Pereira - Pereira)
- **Empresa oficial del PV en BD (`core.puntos_venta`):** `EMP-03` (Motos del Eje)
- **Validación de Relación:** `INCONSISTENCIA_EMPRESA_PV` (`EMP-01` != `EMP-03`)
- **Dependencias en BD:** `core.asignaciones`: 0 | `core.eventos_gestion`: 0
- **Conclusión:** No puede cargarse tal como viene en el CSV debido a la restricción de clave foránea compuesta `fk_adviser_sales_point` (`FOREIGN KEY (empresa_id, punto_venta_id) REFERENCES core.puntos_venta(empresa_id, punto_venta_id)`). Estado: `PENDIENTE_RECONCILIACION`.

### Asesor `AS-016` — Leidy Johana Castaño Jiménez
- **Datos CSV:** `empresa_id='EMP-01'`, `punto_venta_id='PV-005'`, `capacidad=15`, `activo=SI`, `fecha_ingreso=2026-03-28`
- **Datos BD (`core.asesores`):** NO EXISTE (0 registros encontrados)
- **Empresa declarada (CSV):** `EMP-01` (Motos Andinas)
- **Punto de venta declarado (CSV):** `PV-005` (Motos del Eje Pereira - Pereira)
- **Empresa oficial del PV en BD (`core.puntos_venta`):** `EMP-03` (Motos del Eje)
- **Validación de Relación:** `INCONSISTENCIA_EMPRESA_PV` (`EMP-01` != `EMP-03`)
- **Dependencias en BD:** `core.asignaciones`: 0 | `core.eventos_gestion`: 0
- **Conclusión:** No puede cargarse tal como viene en el CSV debido a la restricción de clave foránea compuesta `fk_adviser_sales_point` (`FOREIGN KEY (empresa_id, punto_venta_id) REFERENCES core.puntos_venta(empresa_id, punto_venta_id)`). Estado: `PENDIENTE_RECONCILIACION`.

---

## 4. Matriz Consolidada de Reconciliación

| asesor_id | nombre | empresa_csv | pv_csv | empresa_pv_oficial | existe_empresa | existe_pv | estado | acción_recomendada |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| `AS-009` | Liliana Muñoz Zapata | `EMP-01` | `PV-003` | `EMP-02` | SI | SI | `INCONSISTENCIA_EMPRESA_PV` | `PENDIENTE_RECONCILIACION` |
| `AS-010` | Paula Andrea Londoño Cardona | `EMP-01` | `PV-003` | `EMP-02` | SI | SI | `INCONSISTENCIA_EMPRESA_PV` | `PENDIENTE_RECONCILIACION` |
| `AS-011` | Sebastián Valencia Cardona | `EMP-01` | `PV-003` | `EMP-02` | SI | SI | `INCONSISTENCIA_EMPRESA_PV` | `PENDIENTE_RECONCILIACION` |
| `AS-012` | Julián Osorio Mosquera | `EMP-01` | `PV-003` | `EMP-02` | SI | SI | `INCONSISTENCIA_EMPRESA_PV` | `PENDIENTE_RECONCILIACION` |
| `AS-013` | Liliana Londoño Bedoya | `EMP-01` | `PV-004` | `EMP-02` | SI | SI | `INCONSISTENCIA_EMPRESA_PV` | `PENDIENTE_RECONCILIACION` |
| `AS-014` | Luz Marina Cardona Mosquera | `EMP-01` | `PV-004` | `EMP-02` | SI | SI | `INCONSISTENCIA_EMPRESA_PV` | `PENDIENTE_RECONCILIACION` |
| `AS-015` | Katherine Vargas Jiménez | `EMP-01` | `PV-005` | `EMP-03` | SI | SI | `INCONSISTENCIA_EMPRESA_PV` | `PENDIENTE_RECONCILIACION` |
| `AS-016` | Leidy Johana Castaño Jiménez | `EMP-01` | `PV-005` | `EMP-03` | SI | SI | `INCONSISTENCIA_EMPRESA_PV` | `PENDIENTE_RECONCILIACION` |

---

## 5. Inconsistencias Encontradas

### Desglose por Tipología:
- **`INCONSISTENCIA_EMPRESA_PV`:** 8 asesores (100% de los 8 auditados).
- **`PV_NO_EXISTE`:** 0 asesores.
- **`EMPRESA_NO_EXISTE`:** 0 asesores.
- **`OTRO`:** 0 asesores.

### Análisis Técnico de la Restricción en PostgreSQL:
La tabla `core.asesores` posee la siguiente restricción de integridad referencial:
```sql
CONSTRAINT fk_adviser_sales_point FOREIGN KEY (empresa_id, punto_venta_id)
    REFERENCES core.puntos_venta (empresa_id, punto_venta_id);
```
Dado que en `core.puntos_venta`:
- `PV-003` (Dosquebradas) pertenece a `EMP-02` (MotoRisaralda).
- `PV-004` (Manizales) pertenece a `EMP-02` (MotoRisaralda).
- `PV-005` (Pereira) pertenece a `EMP-03` (Motos del Eje).

Cualquier intento de insertar directamente un registro con `empresa_id='EMP-01'` asociado a `PV-003`, `PV-004` o `PV-005` es **rechazado por el motor de PostgreSQL** por violación de clave foránea.

---

## 6. Comparación Contextual y Patrones Estructurales

Al examinar la distribución completa de asesores en el CSV y en la base de datos por punto de venta, se observan los siguientes hallazgos objetivos:

| Punto Venta | Nombre | Ciudad | Empresa Oficial | Asesores en CSV | Asesores en DB | Estado en DB | IDs en CSV |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `PV-001` | Motos Andinas Pereira | Pereira | `EMP-01` | 4 | 4 | NORMAL | AS-001, AS-002, AS-003, AS-004 |
| `PV-002` | Motos Andinas Armenia | Armenia | `EMP-01` | 4 | 4 | NORMAL | AS-005, AS-006, AS-007, AS-008 |
| `PV-003` | MotoRisaralda Dosquebradas | Dosquebradas | `EMP-02` | 4 | 0 | **VACÍO (0 ASESORES)** | AS-009, AS-010, AS-011, AS-012 |
| `PV-004` | MotoRisaralda Manizales | Manizales | `EMP-02` | 2 | 0 | **VACÍO (0 ASESORES)** | AS-013, AS-014 |
| `PV-005` | Motos del Eje Pereira | Pereira | `EMP-03` | 2 | 0 | **VACÍO (0 ASESORES)** | AS-015, AS-016 |
| `PV-006` | MotoRisaralda Barranquilla | Barranquilla | `EMP-02` | 2 | 2 | NORMAL | AS-017, AS-018 |
| `PV-007` | MotoRisaralda Soledad | Soledad | `EMP-02` | 2 | 2 | NORMAL | AS-019, AS-020 |
| `PV-008` | MotoRisaralda Cartagena | Cartagena | `EMP-02` | 3 | 3 | NORMAL | AS-021, AS-022, AS-023 |
| `PV-009` | MotoRisaralda Santa Marta | Santa Marta | `EMP-02` | 3 | 3 | NORMAL | AS-024, AS-025, AS-026 |
| `PV-010` | MotoRisaralda Montería | Montería | `EMP-02` | 2 | 2 | NORMAL | AS-027, AS-028 |
| `PV-011` | Motos del Eje Bogotá Norte | Bogotá | `EMP-03` | 4 | 4 | NORMAL | AS-029, AS-030, AS-031, AS-032 |
| `PV-012` | Motos del Eje Bogotá Sur | Bogotá | `EMP-03` | 4 | 4 | NORMAL | AS-033, AS-034, AS-035, AS-036 |
| `PV-013` | Motos del Eje Bogotá Centro | Bogotá | `EMP-03` | 2 | 2 | NORMAL | AS-037, AS-038 |
| `PV-014` | Motos del Eje Bogotá Occidente | Bogotá | `EMP-03` | 2 | 2 | NORMAL | AS-039, AS-040 |
| `PV-015` | Motos del Eje Soacha | Soacha | `EMP-03` | 2 | 2 | NORMAL | AS-041, AS-042 |

### Observaciones de Patrón:
1. **Puntos de Venta Huérfanos de Personal en DB:** Todos los puntos de venta de la red tienen entre 2 y 4 asesores cargados en PostgreSQL, **excepto exactamente `PV-003`, `PV-004` y `PV-005`**, los cuales tienen 0 asesores en `core.asesores`.
2. **Correlación con el Caso de Leads de Fase 9A.5:** Durante la Fase 9A.5 (Reconciliación de Leads), se identificaron exactamente **306 leads** en `archivosreales/leads.csv` que venían etiquetados con `empresa_id='EMP-01'`, pero pertenecían a `PV-003`, `PV-004` o `PV-005`. En dicha fase se determinó como regla comercial que el `punto_venta_id` determinaba la empresa propietaria oficial.
3. **Secuencia de IDs:** La numeración de `asesor_id` en `asesores.csv` es estrictamente secuencial y agrupa por punto de venta:
   - `AS-001` a `AS-004`: `PV-001` (`EMP-01`)
   - `AS-005` a `AS-008`: `PV-002` (`EMP-01`)
   - `AS-009` a `AS-012`: `PV-003` (Declarado `EMP-01`, Oficial `EMP-02`)
   - `AS-013` a `AS-014`: `PV-004` (Declarado `EMP-01`, Oficial `EMP-02`)
   - `AS-015` a `AS-016`: `PV-005` (Declarado `EMP-01`, Oficial `EMP-03`)
   - `AS-017` a `AS-028`: `PV-006` a `PV-010` (`EMP-02`)
   - `AS-029` a `AS-042`: `PV-011` a `PV-015` (`EMP-03`)

---

## 7. Recomendación para Fase 9D.1

### Estado de Cargabilidad:
- **Cargables sin modificación:** `0 asesores`.
- **Requieren validación / Reconciliación:** `8 asesores` (`AS-009` al `AS-016`).

### Opciones de Decisión Técnica para la Fase 9D.1:

1. **Opción A (Reconciliación por Punto de Venta — Homóloga a Fase 9A.5):**
   - Asumir que el `punto_venta_id` es el dato operativo fidedigno y corregir el `empresa_id` para que coincida con la empresa propietaria del punto de venta:
     - `AS-009` .. `AS-012`: asignar `empresa_id='EMP-02'` (`PV-003`).
     - `AS-013` .. `AS-014`: asignar `empresa_id='EMP-02'` (`PV-004`).
     - `AS-015` .. `AS-016`: asignar `empresa_id='EMP-03'` (`PV-005`).
   - *Ventaja:* Restaura el equipo comercial de los tres puntos de venta desiertos (`PV-003`, `PV-004`, `PV-005`), respetando la FK `fk_adviser_sales_point` y manteniendo total consistencia con los 306 leads reconciliados en 9A.5.

2. **Opción B (Reconciliación por Empresa — Mantener EMP-01):**
   - Asumir que el `empresa_id='EMP-01'` es correcto y que el `punto_venta_id` fue mal registrado.
   - *Dificultad:* No existe evidencia objetiva en el archivo de a qué punto de venta de `EMP-01` (`PV-001` o `PV-002`) pertenecerían estos 8 asesores, lo que saturaría la capacidad de `PV-001` y `PV-002` y dejaría `PV-003`, `PV-004` y `PV-005` sin asesores.

3. **Opción C (Permanencia Pendiente):**
   - Mantener los 8 registros fuera de PostgreSQL hasta obtener confirmación explícita del área de negocio / recursos humanos de la empresa matriz.

> [!IMPORTANT]
> Conforme a las reglas de la Fase 9D.0, **no se ha tomado ninguna acción de carga ni corrección**. Los 8 asesores quedan formalmente documentados como `PENDIENTE_RECONCILIACION` a la espera de la instrucción de negocio para Fase 9D.1.

---

## 8. Verificación de Integridad de la Auditoría

- [x] **Auditoría individual realizada:** 8 de 8 asesores auditados minuciosamente.
- [x] **Comparación CSV vs BD ejecutada:** Se verificó la no existencia previa de los 8 en `core.asesores`.
- [x] **Validación Empresa ↔ Punto de Venta:** 100% de inconsistencias identificadas y clasificadas.
- [x] **Revisión de dependencias:** 0 registros en `core.asignaciones` y `core.eventos_gestion`.
- [x] **Cero modificaciones a PostgreSQL:** Sin operaciones DML (`INSERT`, `UPDATE`, `DELETE`) ni DDL ejecutadas en la base de datos.
- [x] **Tests y sistema intactos:** No se alteró ninguna vista, scoring ni flujo operativo.
