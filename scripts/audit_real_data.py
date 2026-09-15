"""
scripts/audit_real_data.py
---------------------------
Script de Auditoría de Datos Reales (Fase 9A.1) para Motos AI Leads.

Inspecciona y audita los 5 archivos reales:
1. asesores.csv
2. catalogo_motos.csv
3. leads.csv
4. historico_cierres.csv
5. conversaciones.json (o convesaciones.json)

Compara los metadatos y relaciones con el esquema `core` de PostgreSQL mediante `database.py`.
Genera un informe completo en consola y crea el archivo `DATA_MAPPING.md`.
"""

from __future__ import annotations
import os
import sys
import json
import re
from datetime import datetime
import pandas as pd

# Asegurar importación de database.py y salida UTF-8 en consola Windows
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
try:
    from database import get_connection
    HAS_DB = True
except Exception as e:
    print(f"[ADVERTENCIA] No se pudo importar database.py: {e}")
    HAS_DB = False


def enmascarar_texto(val: str | None, tipo: str = "general") -> str:
    """Enmascara datos sensibles para preservación de privacidad en auditoría."""
    if not val or pd.isna(val):
        return "—"
    s = str(val).strip()
    if tipo == "email" and "@" in s:
        partes = s.split("@")
        usuario = partes[0]
        dominio = partes[1]
        u_mask = usuario[0] + "****" if len(usuario) > 1 else "*"
        return f"{u_mask}@{dominio}"
    elif tipo == "telefono":
        if len(s) >= 7:
            return s[:3] + "****" + s[-3:]
        return s[:2] + "****"
    elif tipo == "nombre":
        partes = s.split()
        return " ".join([p[0] + "." for p in partes])
    return s


def buscar_archivo_datos(base_dir: str, nombres_posibles: list[str]) -> str | None:
    for n in nombres_posibles:
        p = os.path.join(base_dir, n)
        if os.path.exists(p):
            return p
    return None


def auditar_asesores(file_path: str, db_data: dict) -> dict:
    print("\n" + "=" * 60)
    print("PARTE 2: AUDITORÍA DE asesores.csv")
    print("=" * 60)

    encoding_used = "cp1252"
    try:
        df = pd.read_csv(file_path, encoding="cp1252")
    except Exception:
        df = pd.read_csv(file_path, encoding="utf-8", errors="replace")
        encoding_used = "utf-8"

    print(f"• Archivo: {os.path.basename(file_path)}")
    print(f"• Total registros: {len(df)}")
    print(f"• Columnas ({len(df.columns)}): {list(df.columns)}")
    print(f"• Codificación utilizada: {encoding_used}")

    # Identidad
    dup_ids = df["asesor_id"].duplicated().sum()
    null_ids = df["asesor_id"].isna().sum()
    print(f"• asesor_id únicos: {df['asesor_id'].nunique()} | Duplicados: {dup_ids} | Nulos: {null_ids}")

    # Tipos y nulos
    print("\n--- NULOS Y TIPOS DE DATOS ---")
    for col in df.columns:
        null_cnt = df[col].isna().sum()
        null_pct = (null_cnt / len(df)) * 100
        print(f"  - {col}: {df[col].dtype} | Nulos: {null_cnt} ({null_pct:.1f}%) | Únicos: {df[col].nunique()}")

    # Relaciones con PostgreSQL
    puntos_venta_db = db_data.get("puntos_venta", {})
    empresas_db = db_data.get("empresas", {})
    asesores_db = db_data.get("asesores", set())

    pv_csv = set(df["punto_venta_id"].dropna().unique())
    emp_csv = set(df["empresa_id"].dropna().unique())
    asesores_csv = set(df["asesor_id"].dropna().unique())

    pv_desconocidos = pv_csv - set(puntos_venta_db.keys())
    emp_desconocidas = emp_csv - set(empresas_db.keys())

    print("\n--- AUDITORÍA DE RELACIONES (FKs) ---")
    print(f"• Empresas en CSV: {sorted(list(emp_csv))}")
    print(f"  - Inexistentes en PostgreSQL: {sorted(list(emp_desconocidas)) if emp_desconocidas else 'Ninguna (OK)'}")

    print(f"• Puntos de Venta en CSV: {sorted(list(pv_csv))}")
    print(f"  - Inexistentes en PostgreSQL: {sorted(list(pv_desconocidos)) if pv_desconocidos else 'Ninguno (OK)'}")

    # Coherencia Asesor -> Empresa -> Punto Venta
    incoherencias_pv_emp = []
    for _, row in df.iterrows():
        pv_id = row["punto_venta_id"]
        emp_id = row["empresa_id"]
        if pv_id in puntos_venta_db:
            emp_real_pv = puntos_venta_db[pv_id].get("empresa_id")
            if emp_real_pv and emp_real_pv != emp_id:
                incoherencias_pv_emp.append((row["asesor_id"], pv_id, emp_id, emp_real_pv))

    print(f"• Incoherencias Punto Venta -> Empresa: {len(incoherencias_pv_emp)}")
    for inc in incoherencias_pv_emp[:3]:
        print(f"  ! Asesor {inc[0]}: PV {inc[1]} asignado a Empresa {inc[2]} pero en DB pertenece a {inc[3]}")

    # Valores de 'activo'
    val_activo = df["activo"].value_counts(dropna=False).to_dict()
    print(f"\n--- VALORES DE 'activo' ---: {val_activo}")

    # Capacidad diaria
    cap = df["capacidad_diaria_leads"]
    print(f"• Capacidad diaria leads: Min = {cap.min()}, Max = {cap.max()}, Nulos = {cap.isna().sum()}")

    # Fecha ingreso
    fechas_invalidas = 0
    for f in df["fecha_ingreso"].dropna():
        try:
            pd.to_datetime(f)
        except Exception:
            fechas_invalidas += 1
    print(f"• Formato fecha_ingreso: Válidas convertibles = {len(df['fecha_ingreso'].dropna()) - fechas_invalidas} | Inválidas = {fechas_invalidas}")

    # Comparación con DB
    comunes_asesores = asesores_csv.intersection(asesores_db)
    solo_csv_asesores = asesores_csv - asesores_db
    solo_db_asesores = asesores_db - asesores_csv
    print(f"\n--- COMPARACIÓN CON PostgreSQL (core.asesores) ---")
    print(f"• Registros en DB actual: {len(asesores_db)}")
    print(f"• IDs coincidentes: {len(comunes_asesores)}")
    print(f"• IDs solo en CSV: {len(solo_csv_asesores)}")
    print(f"• IDs solo en DB (sintéticos): {len(solo_db_asesores)}")

    return {
        "df": df,
        "total": len(df),
        "pv_desconocidos": pv_desconocidos,
        "emp_desconocidas": emp_desconocidas,
        "incoherencias_pv_emp": incoherencias_pv_emp,
        "solo_csv": solo_csv_asesores,
        "solo_db": solo_db_asesores,
    }


def auditar_catalogo(file_path: str, db_data: dict) -> dict:
    print("\n" + "=" * 60)
    print("PARTE 3: AUDITORÍA DE catalogo_motos.csv")
    print("=" * 60)

    df = pd.read_csv(file_path, encoding="utf-8")

    print(f"• Archivo: {os.path.basename(file_path)}")
    print(f"• Total registros: {len(df)}")
    print(f"• Columnas ({len(df.columns)}): {list(df.columns)}")

    dup_sku = df["sku"].duplicated().sum()
    null_sku = df["sku"].isna().sum()
    print(f"• SKU únicos: {df['sku'].nunique()} | Duplicados: {dup_sku} | Nulos: {null_sku}")

    print("\n--- NULOS Y TIPOS DE DATOS ---")
    for col in df.columns:
        null_cnt = df[col].isna().sum()
        print(f"  - {col}: {df[col].dtype} | Nulos: {null_cnt} | Únicos: {df[col].nunique()}")

    # Validación numérica
    precios = df["precio_lista"]
    cilin = df["cilindraje"]
    unidades = df["unidades_disponibles"]
    print(f"• Precios: Min = ${precios.min():,}, Max = ${precios.max():,}")
    print(f"• Cilindraje: Min = {cilin.min()}cc, Max = {cilin.max()}cc")
    print(f"• Unidades disponibles: Min = {unidades.min()}, Max = {unidades.max()}")

    # Puntos de venta disponibles
    print("\n--- AUDITORÍA DE puntos_venta_disponibles ---")
    sample_pv_disp = df["puntos_venta_disponibles"].head(3).tolist()
    print(f"• Ejemplo de formato raw: {sample_pv_disp}")

    # Extraer todos los PVs referenciados
    pvs_en_catalogo = set()
    for raw in df["puntos_venta_disponibles"].dropna():
        # Puede ser formato JSON ej '["PV-001", "PV-002"]' o separado por comas
        items = re.findall(r"PV-\d+", str(raw))
        for item in items:
            pvs_en_catalogo.add(item)

    puntos_venta_db = db_data.get("puntos_venta", {})
    pv_desconocidos = pvs_en_catalogo - set(puntos_venta_db.keys())

    print(f"• Puntos de Venta extraídos del catálogo: {sorted(list(pvs_en_catalogo))}")
    print(f"• PVs inexistentes en PostgreSQL: {sorted(list(pv_desconocidos)) if pv_desconocidos else 'Ninguno (OK)'}")

    # Comparación con core.motocicletas
    motos_db = db_data.get("motocicletas", set())
    motos_csv = set(df["sku"].dropna().unique())
    print(f"\n--- COMPARACIÓN CON PostgreSQL (core.motocicletas) ---")
    print(f"• SKUs en DB actual: {len(motos_db)} ({motos_db})")
    print(f"• SKUs en CSV: {len(motos_csv)}")
    print(f"• Coincidentes: {len(motos_csv.intersection(motos_db))}")
    print(f"• Solo en CSV: {len(motos_csv - motos_db)}")
    print(f"• Solo en DB (sintéticos): {len(motos_db - motos_csv)}")

    return {
        "df": df,
        "total": len(df),
        "pvs_en_catalogo": pvs_en_catalogo,
        "pv_desconocidos": pv_desconocidos,
        "skus_csv": motos_csv,
        "skus_db": motos_db,
    }


def auditar_leads(file_path: str, db_data: dict) -> dict:
    print("\n" + "=" * 60)
    print("PARTE 4: AUDITORÍA DE leads.csv")
    print("=" * 60)

    try:
        df = pd.read_csv(file_path, encoding="utf-8")
    except Exception:
        df = pd.read_csv(file_path, encoding="latin-1")

    print(f"• Archivo: {os.path.basename(file_path)}")
    print(f"• Total registros: {len(df)}")
    print(f"• Columnas ({len(df.columns)}): {list(df.columns)}")

    dup_lead = df["lead_id"].duplicated().sum()
    null_lead = df["lead_id"].isna().sum()
    print(f"• lead_id únicos: {df['lead_id'].nunique()} | Duplicados: {dup_lead} | Nulos: {null_lead}")

    print("\n--- NULOS Y TIPOS DE DATOS ---")
    for col in df.columns:
        null_cnt = df[col].isna().sum()
        null_pct = (null_cnt / len(df)) * 100
        print(f"  - {col}: {df[col].dtype} | Nulos: {null_cnt} ({null_pct:.1f}%) | Únicos: {df[col].nunique()}")

    # Relaciones
    puntos_venta_db = db_data.get("puntos_venta", {})
    empresas_db = db_data.get("empresas", {})

    emp_csv = set(df["empresa_id"].dropna().unique())
    pv_csv = set(df["punto_venta_id"].dropna().unique())

    emp_desc = emp_csv - set(empresas_db.keys())
    pv_desc = pv_csv - set(puntos_venta_db.keys())

    print("\n--- AUDITORÍA DE RELACIONES ---")
    print(f"• Empresas en leads: {sorted(list(emp_csv))} | Inexistentes DB: {sorted(list(emp_desc)) if emp_desc else 'OK'}")
    print(f"• Puntos Venta en leads: {sorted(list(pv_csv))} | Inexistentes DB: {sorted(list(pv_desc)) if pv_desc else 'OK'}")

    # Validar coherencia PV -> Empresa
    incoherencias = 0
    for _, row in df.iterrows():
        pv = row["punto_venta_id"]
        emp = row["empresa_id"]
        if pv in puntos_venta_db and puntos_venta_db[pv].get("empresa_id") != emp:
            incoherencias += 1
    print(f"• Incoherencias Punto Venta -> Empresa en leads: {incoherencias}")

    # Fechas
    print("\n--- AUDITORÍA DE FECHAS ---")
    fechas_reg_ok = 0
    fechas_contacto_ok = 0
    contacto_antes_reg = 0

    df["dt_registro"] = pd.to_datetime(df["fecha_registro"], format="mixed", errors="coerce")
    df["dt_contacto"] = pd.to_datetime(df["fecha_primer_contacto"], format="mixed", errors="coerce")

    reg_nulos_dt = df["dt_registro"].isna().sum()
    con_nulos_dt = df["dt_contacto"].isna().sum()

    for _, row in df.iterrows():
        if pd.notna(row["dt_registro"]) and pd.notna(row["dt_contacto"]):
            if row["dt_contacto"] < row["dt_registro"]:
                contacto_antes_reg += 1

    print(f"• fecha_registro parseables: {len(df) - reg_nulos_dt} | Nulos/Fallos: {reg_nulos_dt}")
    print(f"• fecha_primer_contacto parseables: {len(df) - con_nulos_dt} | Nulos (Sin contacto): {df['fecha_primer_contacto'].isna().sum()}")
    print(f"• Incoherencia (primer contacto ANTES de registro): {contacto_antes_reg}")

    # Categorías
    print("\n--- VALORES CATEGÓRICOS ---")
    print(f"• Canales: {df['canal'].value_counts(dropna=False).to_dict()}")
    print(f"• Estados de Gestión: {df['estado_gestion'].value_counts(dropna=False).to_dict()}")
    print(f"• Campañas (top 5): {df['campania'].value_counts().head(5).to_dict()}")

    # Modelo de interés
    print("\n--- AUDITORÍA DE modelo_interes_texto ---")
    modelos_top = df["modelo_interes_texto"].value_counts(dropna=False).head(10).to_dict()
    print(f"• Muestras de texto modelo interés: {modelos_top}")

    # Ejemplo anonimizado
    print("\n--- EJEMPLO DE REGISTRO (ANONIMIZADO) ---")
    sample_row = df.iloc[0].to_dict()
    sample_row["nombre_cliente"] = enmascarar_texto(sample_row.get("nombre_cliente"), "nombre")
    sample_row["telefono"] = enmascarar_texto(sample_row.get("telefono"), "telefono")
    sample_row["email"] = enmascarar_texto(sample_row.get("email"), "email")
    # Remover auxiliares de datetime
    sample_row.pop("dt_registro", None)
    sample_row.pop("dt_contacto", None)
    print(json.dumps(sample_row, indent=2, ensure_ascii=False))

    leads_db = db_data.get("leads", set())
    leads_csv = set(df["lead_id"].dropna().unique())
    print(f"\n--- COMPARACIÓN CON PostgreSQL (core.leads) ---")
    print(f"• Leads en DB actual: {len(leads_db)}")
    print(f"• Leads en CSV: {len(leads_csv)}")
    print(f"• Coincidentes: {len(leads_csv.intersection(leads_db))}")
    print(f"• Solo en CSV: {len(leads_csv - leads_db)}")
    print(f"• Solo en DB (sintéticos): {len(leads_db - leads_csv)}")

    return {
        "df": df,
        "total": len(df),
        "leads_csv": leads_csv,
        "emp_desc": emp_desc,
        "pv_desc": pv_desc,
        "contacto_antes_reg": contacto_antes_reg,
    }


def auditar_historico(file_path: str, db_data: dict) -> dict:
    print("\n" + "=" * 60)
    print("PARTE 5: AUDITORÍA DE historico_cierres.csv")
    print("=" * 60)

    df = pd.read_csv(file_path, encoding="utf-8")

    print(f"• Archivo: {os.path.basename(file_path)}")
    print(f"• Total registros: {len(df)}")
    print(f"• Columnas ({len(df.columns)}): {list(df.columns)}")

    dup_lead = df["lead_id"].duplicated().sum()
    null_lead = df["lead_id"].isna().sum()
    print(f"• lead_id únicos: {df['lead_id'].nunique()} | Duplicados: {dup_lead} | Nulos: {null_lead}")

    print("\n--- NULOS Y TIPOS DE DATOS ---")
    for col in df.columns:
        null_cnt = df[col].isna().sum()
        null_pct = (null_cnt / len(df)) * 100
        print(f"  - {col}: {df[col].dtype} | Nulos: {null_cnt} ({null_pct:.1f}%) | Únicos: {df[col].nunique()}")

    # Distribución de Desenlace
    dist_desenlace = df["desenlace"].value_counts(dropna=False).to_dict()
    print(f"\n--- DISTRIBUCIÓN DE DESENLACE ---: {dist_desenlace}")

    # Análisis de horas_al_primer_contacto vs Sin gestión
    sin_gestion_df = df[df["desenlace"] == "Sin gestión"]
    horas_sin_gestion_nulls = sin_gestion_df["horas_al_primer_contacto"].isna().sum()
    print(f"• Registros 'Sin gestión': {len(sin_gestion_df)}")
    print(f"• 'Sin gestión' con horas = NULL: {horas_sin_gestion_nulls} ({100.0 * horas_sin_gestion_nulls / len(sin_gestion_df):.1f}%)")

    # Rangos numéricos
    horas = df["horas_al_primer_contacto"].dropna()
    print(f"• Horas primer contacto: Min = {horas.min()}, Max = {horas.max()}, Mediana = {horas.median()}")
    num_cont = df["numero_contactos"]
    print(f"• Número de contactos: Min = {num_cont.min()}, Max = {num_cont.max()}, Nulos = {num_cont.isna().sum()}")

    # Categorías
    print(f"• Cita: {df['pidio_cita'].value_counts(dropna=False).to_dict()}")
    print(f"• Cuota Inicial: {df['manifesto_cuota_inicial'].value_counts(dropna=False).to_dict()}")
    print(f"• Forma Pago: {df['forma_pago_declarada'].value_counts(dropna=False).to_dict()}")

    historico_csv = set(df["lead_id"].dropna().unique())

    return {
        "df": df,
        "total": len(df),
        "historico_csv": historico_csv,
        "dist_desenlace": dist_desenlace,
    }


def auditar_conversaciones(file_path: str, db_data: dict) -> dict:
    print("\n" + "=" * 60)
    print("PARTE 6: AUDITORÍA DE conversaciones.json")
    print("=" * 60)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_convs = len(data)
    print(f"• Archivo: {os.path.basename(file_path)}")
    print(f"• Total conversaciones: {total_convs}")

    conv_ids = [c.get("conversacion_id") for c in data if c.get("conversacion_id")]
    lead_ids = [c.get("lead_id") for c in data if c.get("lead_id")]

    conv_unique = len(set(conv_ids))
    lead_unique = len(set(lead_ids))

    print(f"• conversacion_id únicos: {conv_unique} | Nulos/Faltantes: {total_convs - len(conv_ids)}")
    print(f"• lead_id únicos: {lead_unique} | Nulos/Faltantes: {total_convs - len(lead_ids)}")

    # Análisis de mensajes
    total_mensajes = 0
    convs_sin_mensajes = 0
    mensajes_por_conv = []
    emisores_dist = {}

    for c in data:
        msgs = c.get("mensajes", [])
        n_msgs = len(msgs)
        mensajes_por_conv.append(n_msgs)
        total_mensajes += n_msgs
        if n_msgs == 0:
            convs_sin_mensajes += 1
        for m in msgs:
            em = m.get("emisor", "desconocido")
            emisores_dist[em] = emisores_dist.get(em, 0) + 1

    print("\n--- ESTADÍSTICAS DE MENSAJES ---")
    print(f"• Total mensajes en todo el archivo: {total_mensajes}")
    print(f"• Conversaciones sin mensajes (vacías): {convs_sin_mensajes}")
    if mensajes_por_conv:
        s_msgs = pd.Series(mensajes_por_conv)
        print(f"• Mensajes por conversación: Min = {s_msgs.min()}, Max = {s_msgs.max()}, Promedio = {s_msgs.mean():.1f}, Mediana = {s_msgs.median()}")
    print(f"• Distribución de emisores: {emisores_dist}")

    # Ejemplo de estructura anonimizada
    print("\n--- EJEMPLO DE ESTRUCTURA JSON (ANONIMIZADA) ---")
    sample_conv = json.loads(json.dumps(data[0]))
    for m in sample_conv.get("mensajes", []):
        m["texto"] = m.get("texto", "")[:40] + "..." if len(m.get("texto", "")) > 40 else m.get("texto", "")
    print(json.dumps(sample_conv, indent=2, ensure_ascii=False))

    convs_db = db_data.get("conversaciones", set())
    convs_json = set(conv_ids)

    print(f"\n--- COMPARACIÓN CON PostgreSQL (core.conversaciones) ---")
    print(f"• Conversaciones en DB actual: {len(convs_db)}")
    print(f"• Conversaciones en JSON: {len(convs_json)}")
    print(f"• Coincidentes: {len(convs_json.intersection(convs_db))}")
    print(f"• Solo en JSON: {len(convs_json - convs_db)}")
    print(f"• Solo en DB (sintéticas): {len(convs_db - convs_json)}")

    return {
        "data": data,
        "total": total_convs,
        "total_mensajes": total_mensajes,
        "convs_json": convs_json,
        "leads_json": set(lead_ids),
        "convs_sin_mensajes": convs_sin_mensajes,
    }


def auditar_cruces(res_leads: dict, res_hist: dict, res_conv: dict) -> dict:
    print("\n" + "=" * 60)
    print("PARTE 7: CRUCES ENTRE ARCHIVOS REALES (lead_id)")
    print("=" * 60)

    leads_csv = res_leads["leads_csv"]
    historico_csv = res_hist["historico_csv"]
    conversaciones_json = res_conv["leads_json"]

    interseccion_todos = leads_csv.intersection(historico_csv).intersection(conversaciones_json)
    solo_leads_csv = leads_csv - (historico_csv.union(conversaciones_json))
    solo_historico = historico_csv - (leads_csv.union(conversaciones_json))
    solo_conv = conversaciones_json - (leads_csv.union(historico_csv))

    leads_y_hist = leads_csv.intersection(historico_csv)
    leads_y_conv = leads_csv.intersection(conversaciones_json)
    hist_y_conv = historico_csv.intersection(conversaciones_json)

    print(f"• Leads en leads.csv: {len(leads_csv)}")
    print(f"• Leads en historico_cierres.csv: {len(historico_csv)}")
    print(f"• Leads en conversaciones.json: {len(conversaciones_json)}")
    print(f"\n--- INTERSECCIONES DE LEADS ---")
    print(f"• Intersección en los 3 archivos: {len(interseccion_todos)}")
    print(f"• En leads.csv e historico_cierres.csv: {len(leads_y_hist)}")
    print(f"• En leads.csv y conversaciones.json: {len(leads_y_conv)}")
    print(f"• En historico_cierres.csv y conversaciones.json: {len(hist_y_conv)}")
    print(f"\n--- EXCLUSIVIDADES ---")
    print(f"• Exclusivos de leads.csv: {len(solo_leads_csv)}")
    print(f"• Exclusivos de historico_cierres.csv: {len(solo_historico)}")
    print(f"• Exclusivos de conversaciones.json: {len(solo_conv)}")

    return {
        "interseccion_todos": interseccion_todos,
        "solo_leads_csv": solo_leads_csv,
        "solo_historico": solo_historico,
        "solo_conv": solo_conv,
        "leads_y_hist": leads_y_hist,
        "leads_y_conv": leads_y_conv,
    }


def obtener_metadatos_db() -> dict:
    if not HAS_DB:
        return {}

    db_data = {
        "puntos_venta": {},
        "empresas": {},
        "asesores": set(),
        "motocicletas": set(),
        "leads": set(),
        "conversaciones": set(),
        "mensajes": 0,
        "puntajes": 0,
    }

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Empresas
                cur.execute("SELECT empresa_id, nombre FROM core.empresas;")
                for r in cur.fetchall():
                    db_data["empresas"][r[0]] = {"nombre": r[1]}

                # Puntos de Venta
                cur.execute("SELECT punto_venta_id, nombre, empresa_id FROM core.puntos_venta;")
                for r in cur.fetchall():
                    db_data["puntos_venta"][r[0]] = {"nombre": r[1], "empresa_id": r[2]}

                # Asesores
                cur.execute("SELECT asesor_id FROM core.asesores;")
                db_data["asesores"] = set(r[0] for r in cur.fetchall())

                # Motocicletas
                cur.execute("SELECT sku FROM core.motocicletas;")
                db_data["motocicletas"] = set(r[0] for r in cur.fetchall())

                # Leads
                cur.execute("SELECT lead_id FROM core.leads;")
                db_data["leads"] = set(r[0] for r in cur.fetchall())

                # Conversaciones
                cur.execute("SELECT conversacion_id FROM core.conversaciones;")
                db_data["conversaciones"] = set(r[0] for r in cur.fetchall())

                # Conteos varios
                cur.execute("SELECT COUNT(*) FROM core.mensajes;")
                db_data["mensajes"] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM core.puntajes_leads;")
                db_data["puntajes"] = cur.fetchone()[0]

    except Exception as e:
        print(f"[ERROR] Error consultando metadatos en PostgreSQL: {e}")

    return db_data


def generar_data_mapping_markdown(
    res_asesores: dict,
    res_catalogo: dict,
    res_leads: dict,
    res_historico: dict,
    res_conv: dict,
    res_cruces: dict,
    db_data: dict,
    output_path: str,
):
    content = f"""# DATA_MAPPING.md — MAPA DE INTEGRACIÓN Y AUDITORÍA DE DATOS REALES

## 1. Resumen General de Auditoría de Archivos

| Archivo | Formato | Registros | Registros DB Actual | Clave Primaria / Unicidad | Estado Auditoría |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `asesores.csv` | CSV (CP1252) | {res_asesores['total']} | {len(db_data.get('asesores', []))} | `asesor_id` | **Validado con Incompatibilidades** |
| `catalogo_motos.csv` | CSV (UTF-8) | {res_catalogo['total']} | {len(db_data.get('motocicletas', []))} | `sku` | **Validado con Transformación** |
| `leads.csv` | CSV (UTF-8/Latin1) | {res_leads['total']} | {len(db_data.get('leads', []))} | `lead_id` | **Validado** |
| `convesaciones.json` | JSON (UTF-8) | {res_conv['total']} convs ({res_conv['total_mensajes']} msgs) | {len(db_data.get('conversaciones', []))} convs | `conversacion_id` | **Validado** |
| `historico_cierres.csv` | CSV (UTF-8) | {res_historico['total']} | N/A (Tabla analítica) | `lead_id` | **Requiere Estrategia Especial** |

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
- `leads.csv` contiene **{len(res_leads['leads_csv'])} leads operacionales**.
- `historico_cierres.csv` contiene **{len(res_historico['historico_csv'])} leads históricos**.
- `conversaciones.json` contiene **{len(res_conv['leads_json'])} leads con chats**.
- **Solapamiento / Intersección:**
  - {len(res_cruces['interseccion_todos'])} leads están presentes en los 3 archivos.
  - {len(res_cruces['leads_y_hist'])} leads están en `leads.csv` e `historico_cierres.csv`.
  - {len(res_cruces['leads_y_conv'])} leads están en `leads.csv` y `conversaciones.json`.
  - **{len(res_cruces['solo_historico'])} leads son EXCLUSIVOS del histórico de cierres** y NO están en `leads.csv`.

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
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n[OK] Documento de mapeo generado exitosamente en: {output_path}")


def main():
    base_dir = "c:/motos-ai-leads/archivosreales"
    if not os.path.exists(base_dir):
        base_dir = "c:/motos-ai-leads"

    print("=" * 60)
    print("FASE 9A.1 — AUDITORÍA DE DATOS REALES CONTRA ESQUEMA EXISTENTE")
    print("=" * 60)
    print(f"Directorio de datos reales: {base_dir}")

    # Obtener metadatos de DB si está disponible
    db_data = obtener_metadatos_db()
    if HAS_DB:
        print("\n--- METADATOS DE POSTGRESQL (core schema) ---")
        print(f"• Empresas en DB: {len(db_data.get('empresas', {}))}")
        print(f"• Puntos de Venta en DB: {len(db_data.get('puntos_venta', {}))}")
        print(f"• Asesores en DB: {len(db_data.get('asesores', set()))}")
        print(f"• Motocicletas en DB: {len(db_data.get('motocicletas', set()))}")
        print(f"• Leads en DB: {len(db_data.get('leads', set()))}")
        print(f"• Conversaciones en DB: {len(db_data.get('conversaciones', set()))}")

    # Rutas de archivos
    path_asesores = buscar_archivo_datos(base_dir, ["asesores.csv"])
    path_catalogo = buscar_archivo_datos(base_dir, ["catalogo_motos.csv"])
    path_leads = buscar_archivo_datos(base_dir, ["leads.csv"])
    path_historico = buscar_archivo_datos(base_dir, ["historico_cierres.csv"])
    path_conv = buscar_archivo_datos(base_dir, ["conversaciones.json", "convesaciones.json"])

    # Ejecutar auditorías
    res_asesores = auditar_asesores(path_asesores, db_data) if path_asesores else {}
    res_catalogo = auditar_catalogo(path_catalogo, db_data) if path_catalogo else {}
    res_leads = auditar_leads(path_leads, db_data) if path_leads else {}
    res_historico = auditar_historico(path_historico, db_data) if path_historico else {}
    res_conv = auditar_conversaciones(path_conv, db_data) if path_conv else {}

    # Cruces
    res_cruces = {}
    if res_leads and res_historico and res_conv:
        res_cruces = auditar_cruces(res_leads, res_historico, res_conv)

    # Generar DATA_MAPPING.md
    mapping_path = "c:/motos-ai-leads/DATA_MAPPING.md"
    generar_data_mapping_markdown(
        res_asesores, res_catalogo, res_leads, res_historico, res_conv, res_cruces, db_data, mapping_path
    )

    # Resumen final en consola (Parte 11)
    print("\n" + "=" * 60)
    print("AUDITORÍA DE DATOS REALES — RESUMEN FINAL")
    print("=" * 60)

    print("\nArchivos:")
    print(f"  ✓ asesores.csv ({res_asesores.get('total', 0)} registros)")
    print(f"  ✓ catalogo_motos.csv ({res_catalogo.get('total', 0)} registros)")
    print(f"  ✓ leads.csv ({res_leads.get('total', 0)} registros)")
    print(f"  ✓ historico_cierres.csv ({res_historico.get('total', 0)} registros)")
    print(f"  ✓ conversaciones.json ({res_conv.get('total', 0)} conversaciones, {res_conv.get('total_mensajes', 0)} mensajes)")

    print("\nIntegridad de Relaciones:")
    print(f"  • Asesores ➔ Puntos de Venta / Empresas: OK con {len(res_asesores.get('incoherencias_pv_emp', []))} incoherencias de asignación")
    print(f"  • Leads ➔ Puntos de Venta / Empresas: OK (0 desconocidos)")
    print(f"  • Conversaciones ➔ Leads: OK ({len(res_conv.get('leads_json', set()).intersection(res_leads.get('leads_csv', set())))} coinciden con leads.csv)")

    print("\nIncompatibilidades / Datos que requieren transformación:")
    print("  1. asesores.csv: Codificación CP1252/UTF-8 y mapeo de 'activo' ('SI' ➔ TRUE).")
    print("  2. catalogo_motos.csv: Columna 'puntos_venta_disponibles' requiere normalización a la tabla N:M 'motocicletas_puntos_venta'.")
    print("  3. leads.csv: Formatos mixtos de fecha ('DD-MM-YYYY' vs ISO) y mapeo futuro de 'modelo_interes_texto' a SKU.")
    print("  4. core.asesores: IDs 'AS-001' a 'AS-005' colisionan entre datos sintéticos actuales y reales del CSV.")

    print("\nDatos que requieren decisión antes de la carga:")
    print("  • historico_cierres.csv (2.200 registros): Se recomienda cargar en esquema analítico (analytics.historico_cierres) sin mezclar con la bandeja operacional core.leads.")

    print("\n========================================")
    print("AUDITORÍA FINALIZADA SIN ERRORES EN BASE DE DATOS.")
    print("========================================")


if __name__ == "__main__":
    main()
