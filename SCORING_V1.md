# SCORING DE PRIORIDAD OPERACIONAL HÍBRIDO V1 — MOTOS AI LEADS

## 1. Objetivo

El objetivo del **Motor de Scoring Híbrido V1** es proporcionar un **sistema explicable, idempotente y calibrado de prioridad comercial** para guiar a los asesores comerciales sobre a qué lead de venta de motocicletas atender primero.

El sistema califica cada lead en una escala de **0 a 100**, asignando una categoría de **Temperatura** (`Crítico`, `Alto`, `Medio`, `Bajo`), determinando automáticamente la arquitectura adecuada (**Regresión Logística V1** o **Rules V1 Fallback**) y generando un desglose transparente de las razones en formato JSON.

---

## 2. Evidencia de la Arquitectura Híbrida

Tras la investigación independiente realizada en la Fase 9B.2 sobre los **2.200 registros históricos** (`historico_cierres.csv`), se determinó:

1. **Regresión Logística V1 (Modelo Principal):**
   - ROC-AUC: **0.6111** – **0.6292**
   - PR-AUC: **0.1386** – **0.1522**
   - Lift@10%: **1.56x** (Aumenta la tasa de conversión del 9.75% al 15.3%–16.4% en el Top 10% priorizado)
   - La transformación `log1p(horas_al_primer_contacto)` representa de forma continua y suave la degradación de urgencia sin rupturas por saltos discrecionales.

2. **Rules V1 (Modelo Fallback):**
   - ROC-AUC: **0.6140**
   - PR-AUC: **0.1343**
   - Lift@10%: **1.57x**
   - Sirve como respaldo determinista perfecto cuando no existen suficientes extracciones conversacionales.

---

## 3. Regla de Selección Dinámica del Modelo

El motor implementa la siguiente lógica de decisión atómica:

```text
               ¿Existen extracciones de conversación?
               (solicita_cita, pago_inicial, metodo_pago)
                                │
                      ┌─────────┴─────────┐
                     SÍ                   NO
                      │                   │
                      ▼                   ▼
           Logistic Regression V1      Rules V1 Fallback
         (modelo_scoring='logistic_regression')  (modelo_scoring='rules')
         (version_scoring='v1.0')               (version_scoring='v1.0')
```

---

## 4. Cálculo Dinámico de Horas de Espera

Para leads en gestión que aún no han sido contactados, el tiempo transcurrido NO se toma de forma fija ni sesgada, sino que se calcula en tiempo real como:

$$\text{horas\_espera} = \frac{\text{Fecha/Hora Actual} - \text{registrado\_en}}{3600}$$

Una vez que el lead recibe su primer contacto (`primer_contacto_en IS NOT NULL`), se calcula la duración exacta del intervalo histórico observado.

---

## 5. Especificaciones del Modelo Principal (Logistic Regression V1)

### Features utilizadas:
- `log_horas`: $\log(1 + \text{horas\_espera})$ (Coeficiente: `-0.2550`)
- `pidio_cita`: `1` si solicitó cita else `0` (Coeficiente: `+0.3068`)
- `manifesto_cuota_inicial`: `1` si manifestó cuota inicial else `0` (Coeficiente: `+0.4263`)
- `pago_credito`: `1` si declaró intención de pago a crédito else `0` (Coeficiente: `-0.3749`)
- `intercept`: `+0.4981`

### Cálculo del Score:
$$z = \text{intercept} + \sum \text{coef}_i \cdot X_i$$
$$p = \frac{1}{1 + e^{-z}}$$
$$\text{puntaje\_prioridad} = \min(100.0, \max(0.0, \text{round}(p \times 100, 2)))$$

---

## 6. Especificaciones del Modelo Fallback (Rules V1)

```text
score_tiempo = puntaje_tiempo_base * 0.70
score_cita   = indicador_pidio_cita * 100 * 0.15
score_cuota  = indicador_cuota_inicial * 100 * 0.15

puntaje_prioridad = min(100, max(0, score_tiempo + score_cita + score_cuota))
```

### Buckets de `puntaje_tiempo_base`:
- `< 1h` ➔ `100`
- `1 - 4h` ➔ `80`
- `4 - 12h` ➔ `60`
- `12 - 24h` ➔ `50`
- `24 - 48h` ➔ `30`
- `> 48h` ➔ `10`

---

## 7. Categorías de Temperatura

| Rango de Puntaje | Categoría | Icono / Estado |
| :--- | :--- | :--- |
| `0 – 24.99` | **Bajo** | 🔵 Frío / Bajo |
| `25 – 49.99` | **Medio** | 🟡 Tibio / Medio |
| `50 – 74.99` | **Alto** | 🟠 Alto |
| `75 – 100` | **Crítico** | 🔴 Crítico |

---

## 8. Explicabilidad y Razones (JSONB)

Cada score guardado en `core.puntajes_leads` incluye una estructura explicable en la columna `razones`.
Ejemplo (Logistic Regression V1):
```json
{
  "modelo": "logistic_regression",
  "version": "v1.0",
  "tiempo": {
    "horas": 0.5,
    "log_horas": 0.4055,
    "z_score": 1.2312
  },
  "pidio_cita": "SI",
  "manifesto_cuota_inicial": "SI",
  "forma_pago_declarada": "contado",
  "factores_clave": [
    "Atención prioritaria (<1h sin contacto)",
    "Solicitud de cita detectada en conversación",
    "Manifestó cuota inicial",
    "Intención de pago de contado"
  ],
  "probabilidad_raw": 0.7741,
  "puntaje_prioridad": 77.41,
  "temperatura": "Crítico"
}
```

---

## 9. Persistencia e Idempotencia en PostgreSQL

El scoring se guarda en la tabla `core.puntajes_leads` asegurando mediante transacciones atómicas la regla de integridad:
- **Exactamente 1 registro activo con `es_actual = TRUE` por cada `lead_id`.**
- El modelo utilizado se almacena en `modelo_scoring` (`logistic_regression` o `rules`) y `version_scoring` (`v1.0`).

---

## 10. Archivos y Mantenimiento del Sistema

- **Dataset de Entrenamiento:** `archivosreales/historico_cierres.csv` (`HX-...`)
- **Script de Entrenamiento:** `scripts/train_logistic_regression.py`
- **Artefacto Serializado:** `models/logistic_regression_v1.joblib`
- **Servicio de Inferencia:** `services/scoring_service.py`
- **Persistencia SQL:** `queries/scoring_queries.py`
- **Scoring Masivo Idempotente:** `scripts/score_real_leads.py`
- **Suite de Pruebas:** `tests/test_scoring.py`
