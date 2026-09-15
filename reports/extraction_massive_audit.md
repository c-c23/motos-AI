# REPORTE DE EXTRACCIÓN IA MASIVA Y SCORING HÍBRIDO (FASE 9C.2-B)

*Fecha de inicio: 2026-09-15 14:19:53*
*Base de datos: PostgreSQL (`motos_database.core`)*

---

Conversaciones reales pendientes encontradas: **601**

## 1. Cobertura Final en PostgreSQL Post-Extracción Masiva
- **Total Leads en DB:** 1507
- **Leads Reales con Conversación (`LD-%`):** 640
- **Leads Reales con Extracción IA (`LD-%`):** 640 (100% de los leads con chat)
- **Total de Conversaciones Procesadas en 9C.2:** 584
- **Errores:** 0

## 2. Desglose de Scoring en Producción
| Modelo de Scoring | Versión | Cantidad de Leads | % sobre Total |
| :--- | :--- | ---: | ---: |
| `rules` | `v1.0` | **1068** | 70.87% |
| `logistic_regression` | `v1.0` | **439** | 29.13% |

## 3. Distribución por Temperatura
| Temperatura | Total Leads | Score Promedio |
| :--- | ---: | ---: |
| **Crítico** | 11 | 77.40 pts |
| **Alto** | 320 | 61.93 pts |
| **Medio** | 451 | 37.89 pts |
| **Bajo** | 725 | 10.53 pts |

## 4. Frecuencia Global de Variables Extraídas (Leads Reales)
- **`solicita_cita`**: True: 145 | False: 0 | NULL: 439
- **`pago_inicial`**: >0: 196 | =0: 65 | NULL: 323
- **`metodo_pago`**: Crédito: 266 | Contado: 48 | NULL: 270
- **`solicita_cotizacion`**: True: 212 | False: 0 | NULL: 372

## 5. Validaciones de Integridad Finales
- **Duplicados de Scores Activos (`es_actual = TRUE`):** 0 (Esperado: 0)
- **Leads sin score activo:** 0 (Esperado: 0)
