# DATA_MAPPING.md — MAPA DE INTEGRACIÓN Y AUDITORÍA DE DATOS REALES

## 1. Resumen General de Auditoría de Archivos

| Archivo | Formato | Registros | Registros DB Actual | Clave Primaria / Unicidad | Estado Auditoría |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `asesores.csv` | CSV (CP1252) | 42 | 7 | `asesor_id` | **Validado con Incompatibilidades** |
| `catalogo_motos.csv` | CSV (UTF-8) | 24 | 24 | `sku` | **Validado con Transformación** |
| `leads.csv` | CSV (UTF-8/Latin1) | 1503 | 7 | `lead_id` | **Validado** |
| `convesaciones.json` | JSON (UTF-8) | 677 convs (4310 msgs) | 7 convs | `conversacion_id` | **Validado** |
| `historico_cierres.csv` | CSV (UTF-8) | 2200 | N/A (Tabla analítica) | `lead_id` | **Requiere Estrategia Especial** |

---

## 2. Mapa Detallado de Correspondencia con el Esquema `core`

| Archivo Origen | Campo Origen | Tabla Destino PostgreSQL | Campo Destino PostgreSQL | Tipo / Transformación Requerida |
| :--- | :--- | :--- | :--- | :--- |
| **asesores.csv** | `asesor_id` | `core.asesores` | `asesor_id` | VARCHAR (Directo) |
| | `nombre` | `core.asesores` | `nombre` | VARCHAR (Codificación CP1252/UTF-8) |
| | `punto_venta_id` | `core.asesores` | `punto_venta_id` | VARCHAR (FK `core.puntos_venta`) |
| | `empresa_id` | `core.asesores` | `empresa_id` | VARCHAR (FK `core.empresas`) |
| | `capacidad_diaria_leads` | `core.asesores` | `capacidad_diaria_leads` | INT (Directo) |
| | `activo` | `core.asesores` | `activo` | BOOLEAN (Mapear 'SI' ➔ TRUE, 'NO' ➔ FALSE) |
| | `fecha_ingreso` | `core.asesores` | `fecha_ingreso` | DATE (Convertir 'YYYY-MM-DD') |
| **catalogo_motos.csv**| `sku` | `core.motocicletas` | `sku` | VARCHAR (Directo) |
| | `marca` | `core.motocicletas` | `marca` | VARCHAR (Directo) |
| | `linea` | `core.motocicletas` | `linea` | VARCHAR (Directo) |
| | `cilindraje` | `core.motocicletas` | `cilindraje_cc` | INT (Mapeo de nombre columna) |
| | `segmento` | `core.motocicletas` | `segmento` | VARCHAR (Directo) |
| | `precio_lista` | `core.motocicletas` | `precio_lista` | NUMERIC (Directo) |
| | `puntos_venta_disponibles`| `core.motocicletas_puntos_venta`| `punto_venta_id` | ARRAY / JSON ➔ Normalizar en filas N:M |
| | `unidades_disponibles`| `core.motocicletas` / N:M | `unidades_disponibles` | INT |
| **leads.csv** | `lead_id` | `core.leads` | `lead_id` | VARCHAR (Directo) |
| | `fecha_registro` | `core.leads` | `registrado_en` | TIMESTAMP (Parsear formatos mixtos DD-MM-YYYY / ISO) |
| | `canal` | `core.leads` | `canal` | VARCHAR (Directo) |
| | `empresa_id` | `core.leads` | `empresa_id` | VARCHAR (FK `core.empresas`) |
| | `punto_venta_id` | `core.leads` | `punto_venta_id` | VARCHAR (FK `core.puntos_venta`) |
| | `nombre_cliente` | `core.leads` | `nombre_cliente` | VARCHAR (Directo) |
| | `telefono` | `core.leads` | `telefono` | VARCHAR (Directo) |
| | `email` | `core.leads` | `correo` | VARCHAR (Mapeo de nombre columna) |
| | `ciudad` | `core.leads` | `ciudad` | VARCHAR (Directo) |
| | `modelo_interes_texto` | `core.leads` | `texto_modelo_original` | VARCHAR (Requerirá matching posterior a `sku`) |
| | `estado_gestion` | `core.leads` | `estado_gestion` | VARCHAR (Directo) |
| | `fecha_primer_contacto`| `core.leads` | `primer_contacto_en` | TIMESTAMP (Parsear mixto / NULL) |
| | `campania` | `core.leads` | `campana` | VARCHAR (Directo) |
| **conversaciones.json**| `conversacion_id` | `core.conversaciones` | `conversacion_id` | VARCHAR (Directo) |
| | `lead_id` | `core.conversaciones` | `lead_id` | VARCHAR (FK `core.leads`) |
| | `canal` | `core.conversaciones` | `canal` | VARCHAR (Directo) |
| | `fecha_inicio` | `core.conversaciones` | `iniciada_en` | TIMESTAMP (Directo) |
| | `mensajes[]` | `core.mensajes` | Varias columnas | Normalización en filas de `core.mensajes` |
| **historico_cierres.csv**| Todo el dataset | `analytics.historico_cierres` / Tabla dedicada | Varias columnas | Dataset analítico supervisado (2.200 filas) |

---

## 3. Hallazgos Críticos de Integración e Incompatibilidades

### A. Cruces de `lead_id` entre Archivos
- `leads.csv` contiene **1501 leads operacionales**.
- `historico_cierres.csv` contiene **2200 leads históricos**.
- `conversaciones.json` contiene **652 leads con chats**.
- **Solapamiento / Intersección:**
  - 0 leads están presentes en los 3 archivos.
  - 0 leads están en `leads.csv` e `historico_cierres.csv`.
  - 640 leads están en `leads.csv` y `conversaciones.json`.
  - **2200 leads son EXCLUSIVOS del histórico de cierres** y NO están en `leads.csv`.

### B. Conflicto entre Datos Sintéticos Actuales y Datos Reales
Actualmente la base PostgreSQL contiene datos sintéticos creados durante el prototipado inicial (ej. `LEAD-001` ... `LEAD-005`, `AS-001` ... `AS-005`, `MOT-001` ... `MOT-025`).
- **Peligro de Colisión:** Los IDs de los datos reales usan una nomenclatura diferente:
  - Leads reales: `LD-00001` ... `LD-01503`
  - Leads históricos: `HX-00001` ... `HX-02200`
  - Conversaciones reales: `CONV-00001` ... `CONV-00677`
  - Asesores reales: `AS-001` ... `AS-042` (aquí sí coinciden `AS-001` a `AS-005` con IDs sintéticos creados en PostgreSQL, por lo que **habrá colisión si se cargan directamente**).

### C. Coherencia Organizacional (Asesor ➔ Punto de Venta ➔ Empresa)
- Todos los `empresa_id` (`EMP-01`, `EMP-02`, `EMP-03`) y `punto_venta_id` (`PV-001` ... `PV-006`) de los CSVs **existen en la base PostgreSQL**.
- Sin embargo, en `asesores.csv` existen **incoherencias estructurales**: asesores tienen asignada una `empresa_id` que no coincide con la empresa a la que pertenece su `punto_venta_id` según `core.puntos_venta`.

### D. Formatos Mixtos de Fechas
- En `leads.csv`, la columna `fecha_registro` viene en formato `DD-MM-YYYY` (ej. `25-08-2026`), mientras que `fecha_primer_contacto` alterna entre `DD-MM-YYYY` e ISO `YYYY-MM-DDTHH:MM:SS`.

---

## 4. Estrategia Propuesta para `historico_cierres.csv`

**Propuesta:** NO insertar los 2.200 registros de `historico_cierres.csv` directamente en `core.leads`.

**Justificación:**
1. `historico_cierres.csv` representa un dataset cerrado de entrenamiento/análisis supervisado con la columna `desenlace` (`Cerrado`, `Perdido`, `Sin gestión`).
2. `core.leads` representa la bandeja operacional activa del CRM.
3. Se recomienda ubicar `historico_cierres.csv` en el esquema `analytics.historico_cierres` o en una tabla desacoplada de analítica sin mezclar el flujo activo con el histórico supervisado.

---

## 5. Estrategia de Carga y Manejo de Datos Sintéticos

1. **Aislamiento / Migración Limpia:**
   - Crear una migración o script de carga que distinga claramente registros sintéticos de registros reales.
   - Para `core.asesores`, actualizar/sobrescribir los registros `AS-001` a `AS-005` con la información real del CSV e insertar del `AS-006` al `AS-042`.
2. **Normalización de Catálogo:**
   - Mapear `catalogo_motos.csv` hacia `core.motocicletas` desglosando la columna `puntos_venta_disponibles` en la tabla intermedia `core.motocicletas_puntos_venta`.
3. **Carga Operacional:**
   - Cargar `leads.csv` en `core.leads`.
   - Cargar `conversaciones.json` en `core.conversaciones` y `core.mensajes`.
   - Ejecutar la extracción y el scoring V1 únicamente sobre los leads operacionales cargados.
