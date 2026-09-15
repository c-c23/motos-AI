# dimension_load_audit.md — REPORTE DE CARGA CONTROLADA DE DIMENSIONES
**Fecha de ejecución:** 2026-09-15 10:28:43

## 1. Resumen de Conteos de Tablas (Antes vs Después)
| Dimensión | Antes | Después | Insertados | Actualizados | Sin Cambios | Rechazados / Pendientes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `core.empresas` | 3 | 3 | 0 | 0 | 3 | 0 |
| `core.puntos_venta` | 15 | 15 | 0 | 0 | 10 | 0 |
| `core.motocicletas` | 48 | 48 | 0 | 0 | 24 | 0 |
| `core.motocicletas_puntos_venta` | 236 | 236 | 0 | 0 | 179 | 0 |
| `core.asesores` | 34 | 34 | 0 | 34 | 0 | 8 |

---

## 2. Comparativa de Asesores Sintéticos Existentes vs Datos Reales (Colisión AS-001 a AS-005)
| ID Asesor | Nombre en DB | Nombre en CSV Real | PV DB | PV CSV | Empresa DB | Empresa CSV | Estado Comparación |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `AS-001` | Ã‰dinson Mosquera PÃ©rez | Édinson Mosquera Pérez | `PV-001` | `PV-001` | `EMP-01` | `EMP-01` | **DIFERENTE** |
| `AS-002` | AndrÃ©s Felipe Bedoya Salazar | Andrés Felipe Bedoya Salazar | `PV-001` | `PV-001` | `EMP-01` | `EMP-01` | **DIFERENTE** |
| `AS-003` | SebastiÃ¡n Mosquera RodrÃ­guez | Sebastián Mosquera Rodríguez | `PV-001` | `PV-001` | `EMP-01` | `EMP-01` | **DIFERENTE** |
| `AS-004` | SebastiÃ¡n Cardona LondoÃ±o | Sebastián Cardona Londoño | `PV-001` | `PV-001` | `EMP-01` | `EMP-01` | **DIFERENTE** |
| `AS-005` | Luisa Ospina Vargas | Luisa Ospina Vargas | `PV-002` | `PV-002` | `EMP-01` | `EMP-01` | **IGUAL** |
| `AS-006` | DuvÃ¡n RamÃ­rez LondoÃ±o | Duván Ramírez Londoño | `PV-002` | `PV-002` | `EMP-01` | `EMP-01` | **DIFERENTE** |
| `AS-007` | Leidy Johana Herrera CastaÃ±o | Leidy Johana Herrera Castaño | `PV-002` | `PV-002` | `EMP-01` | `EMP-01` | **DIFERENTE** |
| `AS-008` | Cristian Franco Zapata | Cristian Franco Zapata | `PV-002` | `PV-002` | `EMP-01` | `EMP-01` | **IGUAL** |
| `AS-017` | JuliÃ¡n Zapata RamÃ­rez | Julián Zapata Ramírez | `PV-006` | `PV-006` | `EMP-02` | `EMP-02` | **DIFERENTE** |
| `AS-018` | Erika MuÃ±oz Vargas | Erika Muñoz Vargas | `PV-006` | `PV-006` | `EMP-02` | `EMP-02` | **DIFERENTE** |
| `AS-019` | Alexander Vargas Restrepo | Alexander Vargas Restrepo | `PV-007` | `PV-007` | `EMP-02` | `EMP-02` | **IGUAL** |
| `AS-020` | Yesenia Salazar MuÃ±oz | Yesenia Salazar Muñoz | `PV-007` | `PV-007` | `EMP-02` | `EMP-02` | **DIFERENTE** |
| `AS-021` | Nelson Correa Correa | Nelson Correa Correa | `PV-008` | `PV-008` | `EMP-02` | `EMP-02` | **IGUAL** |
| `AS-022` | Jhon Jairo Vargas Quintero | Jhon Jairo Vargas Quintero | `PV-008` | `PV-008` | `EMP-02` | `EMP-02` | **IGUAL** |
| `AS-023` | Nelson Vargas Giraldo | Nelson Vargas Giraldo | `PV-008` | `PV-008` | `EMP-02` | `EMP-02` | **IGUAL** |
| `AS-024` | Sandra Milena Betancur Giraldo | Sandra Milena Betancur Giraldo | `PV-009` | `PV-009` | `EMP-02` | `EMP-02` | **IGUAL** |
| `AS-025` | Wilmar Quintero Vargas | Wilmar Quintero Vargas | `PV-009` | `PV-009` | `EMP-02` | `EMP-02` | **IGUAL** |
| `AS-026` | Kevin Cardona Herrera | Kevin Cardona Herrera | `PV-009` | `PV-009` | `EMP-02` | `EMP-02` | **IGUAL** |
| `AS-027` | Claudia Patricia Salazar Torres | Claudia Patricia Salazar Torres | `PV-010` | `PV-010` | `EMP-02` | `EMP-02` | **IGUAL** |
| `AS-028` | Yuliana Arias PÃ©rez | Yuliana Arias Pérez | `PV-010` | `PV-010` | `EMP-02` | `EMP-02` | **DIFERENTE** |
| `AS-029` | Leidy Johana PÃ©rez Torres | Leidy Johana Pérez Torres | `PV-011` | `PV-011` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-030` | MarÃ­a Fernanda Restrepo GÃ³mez | María Fernanda Restrepo Gómez | `PV-011` | `PV-011` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-031` | Paula Andrea CastaÃ±o Correa | Paula Andrea Castaño Correa | `PV-011` | `PV-011` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-032` | Sandra Milena Salazar Franco | Sandra Milena Salazar Franco | `PV-011` | `PV-011` | `EMP-03` | `EMP-03` | **IGUAL** |
| `AS-033` | Natalia RodrÃ­guez Arias | Natalia Rodríguez Arias | `PV-012` | `PV-012` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-034` | Yuliana MuÃ±oz MarÃ­n | Yuliana Muñoz Marín | `PV-012` | `PV-012` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-035` | Cristian GÃ³mez Zapata | Cristian Gómez Zapata | `PV-012` | `PV-012` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-036` | JuliÃ¡n Arias Osorio | Julián Arias Osorio | `PV-012` | `PV-012` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-037` | Luisa MuÃ±oz Escobar | Luisa Muñoz Escobar | `PV-013` | `PV-013` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-038` | Luz Marina HernÃ¡ndez Restrepo | Luz Marina Hernández Restrepo | `PV-013` | `PV-013` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-039` | Ã‰dinson Ospina Arias | Édinson Ospina Arias | `PV-014` | `PV-014` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-040` | Marcela HernÃ¡ndez RodrÃ­guez | Marcela Hernández Rodríguez | `PV-014` | `PV-014` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-041` | EstefanÃ­a Escobar Mosquera | Estefanía Escobar Mosquera | `PV-015` | `PV-015` | `EMP-03` | `EMP-03` | **DIFERENTE** |
| `AS-042` | Adriana Escobar Giraldo | Adriana Escobar Giraldo | `PV-015` | `PV-015` | `EMP-03` | `EMP-03` | **IGUAL** |

---

## 3. Detalle de los 8 Asesores Rechazados / Pendientes por Inconsistencia de Asignación
> **Importante:** Estos 8 registros de `asesores.csv` fueron identificados y **excluidos del proceso de carga** para preservar la integridad de datos, debido a que su `empresa_id` en el CSV no coincide con la empresa oficial a la que pertenece el `punto_venta_id` en `core.puntos_venta`.

| # | asesor_id | Nombre Asesor | empresa_id (CSV) | punto_venta_id | empresa_id (Punto de Venta) | Motivo de Rechazo / Aborto |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- |
| 1 | `AS-009` | Liliana Muñoz Zapata | `EMP-01` | `PV-003` | `EMP-02` | Inconsistencia de asignación: empresa del CSV no coincide con la empresa oficial del Punto de Venta |
| 2 | `AS-010` | Paula Andrea Londoño Cardona | `EMP-01` | `PV-003` | `EMP-02` | Inconsistencia de asignación: empresa del CSV no coincide con la empresa oficial del Punto de Venta |
| 3 | `AS-011` | Sebastián Valencia Cardona | `EMP-01` | `PV-003` | `EMP-02` | Inconsistencia de asignación: empresa del CSV no coincide con la empresa oficial del Punto de Venta |
| 4 | `AS-012` | Julián Osorio Mosquera | `EMP-01` | `PV-003` | `EMP-02` | Inconsistencia de asignación: empresa del CSV no coincide con la empresa oficial del Punto de Venta |
| 5 | `AS-013` | Liliana Londoño Bedoya | `EMP-01` | `PV-004` | `EMP-02` | Inconsistencia de asignación: empresa del CSV no coincide con la empresa oficial del Punto de Venta |
| 6 | `AS-014` | Luz Marina Cardona Mosquera | `EMP-01` | `PV-004` | `EMP-02` | Inconsistencia de asignación: empresa del CSV no coincide con la empresa oficial del Punto de Venta |
| 7 | `AS-015` | Katherine Vargas Jiménez | `EMP-01` | `PV-005` | `EMP-03` | Inconsistencia de asignación: empresa del CSV no coincide con la empresa oficial del Punto de Venta |
| 8 | `AS-016` | Leidy Johana Castaño Jiménez | `EMP-01` | `PV-005` | `EMP-03` | Inconsistencia de asignación: empresa del CSV no coincide con la empresa oficial del Punto de Venta |

---

## 4. Validaciones de Seguridad e Integridad Referencial
- [x] **Transaccionalidad:** Carga ejecutada en un único bloque `with conn` con `commit` al finalizar.
- [x] **Idempotencia:** Ejecución repetible sin duplicación de registros.
- [x] **Sin destructividad:** No se ejecutaron sentencias `DROP`, `TRUNCATE` ni `DELETE`.
- [x] **Integridad de Scoring y UI:** Scoring V1 y Streamlit permanecen 100% funcionales.
- [x] **Protección de Leads/Conversaciones:** Los leads y conversaciones sintéticos y reales no fueron modificados.