# REPORTE DE AUDITORÍA DEL BATCH PILOTO AMPLIADO DE 50 CONVERSACIONES (FASE 9C.2-A)

*Fecha de ejecución: 2026-09-15 14:18:55*
*Base de datos: PostgreSQL (`motos_database.core`)*

---

## 1. Muestra Seleccionada (50 Conversaciones Reales)
Se seleccionaron **50 conversaciones reales** (`LD-%`) sin extracción previa.


## 2. Métricas del Batch de 50 Leads
- **Conversaciones procesadas:** 50
- **Errores:** 0

### Frecuencia de Variables Extraídas:
- **`solicita_cita`**: True: 14 | False: 0 | NULL: 36
- **`pago_inicial`**: >0: 18 | =0: 11 | NULL: 21
- **`metodo_pago`**: Crédito: 23 | Contado: 2 | NULL: 25
- **`solicita_cotizacion`**: True: 13 | False: 0 | NULL: 37

### Impacto en Scoring:
- **Transitaron a Logistic Regression V1 (`logistic_regression`):** **35** (70.0%)
- **Permanecieron en Fallback Rules V1 (`rules`):** **15** (30.0%)

## 3. Muestra de Resultados del Batch (Primeros 15)
| Item | Lead ID | Cita | Cuota Inicial | Método Pago | Modelo | Score Anterior ➔ Nuevo | Temperatura |
| ---: | :--- | :---: | :---: | :---: | :--- | :---: | :--- |
| 1 | `LD-01389` | `NULL` | `NULL` | `Crédito` | `logistic_regression` | 35 ➔ **37.03** | **Medio** |
| 2 | `LD-01325` | `NULL` | `$0` | `Crédito` | `logistic_regression` | 56 ➔ **46.08** | **Medio** |
| 3 | `LD-00279` | `NULL` | `NULL` | `NULL` | `rules` | 42 ➔ **42.0** | **Medio** |
| 4 | `LD-00993` | `NULL` | `$0` | `Crédito` | `logistic_regression` | 21 ➔ **33.24** | **Medio** |
| 5 | `LD-01308` | `NULL` | `NULL` | `NULL` | `rules` | 7 ➔ **7.0** | **Bajo** |
| 6 | `LD-01019` | `True` | `$1.000.000` | `NULL` | `logistic_regression` | 7 ➔ **49.78** | **Medio** |
| 7 | `LD-00027` | `True` | `$3.000.000` | `Crédito` | `logistic_regression` | 7 ➔ **46.61** | **Medio** |
| 8 | `LD-00273` | `NULL` | `NULL` | `Crédito` | `logistic_regression` | 42 ➔ **42.87** | **Medio** |
| 9 | `LD-01113` | `NULL` | `NULL` | `NULL` | `rules` | 21 ➔ **21.0** | **Bajo** |
| 10 | `LD-00584` | `NULL` | `$6.000.000` | `Contado` | `logistic_regression` | 7 ➔ **46.53** | **Medio** |
| 11 | `LD-01241` | `NULL` | `NULL` | `NULL` | `rules` | 42 ➔ **42.0** | **Medio** |
| 12 | `LD-00570` | `True` | `$0` | `Crédito` | `logistic_regression` | 42 ➔ **50.49** | **Alto** |
| 13 | `LD-01043` | `NULL` | `NULL` | `NULL` | `rules` | 7 ➔ **7.0** | **Bajo** |
| 14 | `LD-00674` | `True` | `$1.000.000` | `NULL` | `logistic_regression` | 21 ➔ **57.56** | **Alto** |
| 15 | `LD-00958` | `NULL` | `NULL` | `NULL` | `rules` | 7 ➔ **7.0** | **Bajo** |

## 4. Diagnóstico de Calidad para 9C.2-B
El batch piloto ampliado procesó 50 conversaciones reales con **0% de error**. El **70.0% de los leads** transitaron al modelo de Regresión Logística V1 de forma justificada.

> **CONCLUSIÓN 9C.2-A:** El batch de 50 es 100% satisfactorio. Es seguro avanzar inmediatamente con el paso **9C.2-B (extracción masiva de las ~580 conversaciones restantes por lotes)**.
