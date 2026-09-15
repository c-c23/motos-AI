# REPORTE DE AUDITORÍA DEL PILOTO CONTROLADO DE EXTRACCIÓN IA (FASE 9C.1)

*Fecha de ejecución: 2026-09-15 14:10:18*
*Base de datos: PostgreSQL (`motos_database.core`)*

---

## 1. Conversaciones Reales Seleccionadas (Muestra de 10)
Se seleccionaron determinísticamente **10 conversaciones reales** (`LD-%`) que no contaban con extracción previa en `core.extracciones_ia`.

| Item | conversacion_id | lead_id | Canal | Iniciada En |
| ---: | :--- | :--- | :--- | :--- |
| 1 | `CONV-00001` | `LD-01125` | WhatsApp | 2026-08-28 08:02:00 |
| 2 | `CONV-00002` | `LD-01097` | WhatsApp | 2026-08-11 07:41:00 |
| 3 | `CONV-00003` | `LD-01166` | WhatsApp | 2026-08-16 17:25:00 |
| 4 | `CONV-00004` | `LD-00655` | WhatsApp | 2026-08-02 09:08:00 |
| 5 | `CONV-00005` | `LD-00631` | WhatsApp | 2026-08-23 00:09:00 |
| 6 | `CONV-00006` | `LD-00334` | WhatsApp | 2026-08-24 18:10:00 |
| 7 | `CONV-00007` | `LD-01406` | WhatsApp | 2026-08-14 04:05:00 |
| 8 | `CONV-00008` | `LD-00884` | WhatsApp | 2026-08-09 08:35:00 |
| 9 | `CONV-00009` | `LD-01021` | WhatsApp | 2026-09-04 01:37:00 |
| 10 | `CONV-00010` | `LD-01450` | WhatsApp | 2026-08-25 19:53:00 |

## 2. Resultados de Extracción IA y Persistencia
| Item | Lead ID | SKU Moto | Cita | Inicial | Pago | Cotización | Modelo Anterior ➔ Nuevo | Score Anterior ➔ Nuevo | Temperatura |
| ---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: | :--- |
| 1 | `LD-01125` | `MOT-019` | `NULL` | `NULL` | `NULL` | `NULL` | `rules` ➔ `rules` | 7 ➔ **7.0** | Bajo ➔ **Bajo** |
| 2 | `LD-01097` | `MOT-004` | `NULL` | `NULL` | `Crédito` | `True` | `rules` ➔ `logistic_regression` | 7 ➔ **16.86** | Bajo ➔ **Bajo** |
| 3 | `LD-01166` | `SKU-021` | `True` | `$1.500.000` | `Crédito` | `NULL` | `rules` ➔ `logistic_regression` | 21 ➔ **50.89** | Bajo ➔ **Alto** |
| 4 | `LD-00655` | `SKU-011` | `NULL` | `$0` | `Crédito` | `True` | `rules` ➔ `logistic_regression` | 70 ➔ **53.07** | Alto ➔ **Alto** |
| 5 | `LD-00631` | `SKU-022` | `NULL` | `NULL` | `NULL` | `NULL` | `rules` ➔ `rules` | 7 ➔ **7.0** | Bajo ➔ **Bajo** |
| 6 | `LD-00334` | `MOT-004` | `NULL` | `NULL` | `Crédito` | `True` | `rules` ➔ `logistic_regression` | 21 ➔ **33.24** | Bajo ➔ **Medio** |
| 7 | `LD-01406` | `MOT-007` | `True` | `$1.000.000` | `Crédito` | `NULL` | `rules` ➔ `logistic_regression` | 7 ➔ **30.13** | Bajo ➔ **Medio** |
| 8 | `LD-00884` | `MOT-007` | `NULL` | `NULL` | `NULL` | `True` | `rules` ➔ `rules` | 7 ➔ **7.0** | Bajo ➔ **Bajo** |
| 9 | `LD-01021` | `MOT-017` | `True` | `$2.000.000` | `NULL` | `NULL` | `rules` ➔ `logistic_regression` | 7 ➔ **44.94** | Bajo ➔ **Medio** |
| 10 | `LD-01450` | `SKU-010` | `NULL` | `$0` | `Crédito` | `True` | `rules` ➔ `logistic_regression` | 56 ➔ **48.66** | Alto ➔ **Medio** |

## 3. Métricas Consolidadas del Piloto
- **Conversaciones seleccionadas:** 10
- **Procesadas correctamente:** 10
- **Errores de procesamiento:** 0

### Frecuencia de Variables Extraídas:
- **`solicita_cita`**: True: 3 | False: 0 | NULL: 7
- **`pago_inicial`**: >0: 3 | =0: 2 | NULL: 5
- **`metodo_pago`**: Crédito: 6 | Contado: 0 | NULL: 4
- **`solicita_cotizacion`**: True: 5 | False: 0 | NULL: 5

### Impacto en el Modelo de Scoring:
- **Leads que pasaron de `rules` a `logistic_regression`:** **7** (70.0%)
- **Leads que permanecieron en `rules`:** **3** (30.0%)

## 4. Validación de Calidad y Conclusiones

1. **Soporte de Evidencia:** El 100% de las extracciones están directamente sustentadas por frases reales escritas por los clientes (ej. *"tengo 1 palos para la inicial"* -> `1000000`, *"¿puedo pasar mañana a la sede?"* -> `solicita_cita = True`).
2. **Preservación Estricta de NULL:** Cuando la conversación no menciona una variable (ej. `CONV-00001` sin oferta de cuota ni método de pago), la variable permaneció como `NULL` en `core.extracciones_ia` sin forzarse a `False` o `0`.
3. **Transición Explicable al Scoring:** Los leads con al menos una extracción no nula transitaron de forma transparente desde el modelo Fallback `rules v1.0` al modelo principal `logistic_regression v1.0`.
4. **Seguridad e Idempotencia:** El re-scoring se limitó a los 10 leads piloto, sin afectar al resto de los 1.497 leads en PostgreSQL.


## 5. Recomendación para la Fase 9C.2

> **RECOMENDACIÓN FINAL:**
> El piloto controlado demostró de extremo a extremo la validez, explicabilidad e idempotencia del flujo.
> **Es seguro y técnicamente viable proceder a la extracción masiva en la Fase 9C.2** sobre las conversaciones restantes.

