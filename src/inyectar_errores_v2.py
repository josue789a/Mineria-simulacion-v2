"""
Inyección de errores v3 -- RETO DIFÍCIL, multi-planta
========================================================
Diferencias clave respecto al reto de v1/v2 (que era 1 sola planta, 1
sola fecha de migración, 8 categorías de problemas):

  1. MIGRACIÓN ESCALONADA: cada planta cambia de sistema en una fecha
     DISTINTA (no las 3 el mismo 1-enero-2025). Hay que descubrir la
     fecha de corte de cada planta, no asumirla.
  2. 14 categorías de problemas en vez de 8 (ver RETO_LIMPIEZA_v3.md
     para el enunciado completo, sin respuestas).
  3. Errores nuevos que no existían en v1/v2: contaminación cruzada
     entre archivos de planta, cambio silencioso de unidad de medida,
     ambigüedad real de formato de fecha (no siempre resoluble con
     certeza), encoding roto, bloques de días completos faltantes
     (no aleatorios).
  4. Todo escalado ~2x por planta respecto a v1 (cada planta ya es 2x
     el tamaño del dataset original de 1 sola planta/2 años).

Genera para cada planta (PN, PC, PS):
  - fact_produccion_{planta}_legacy.csv
  - fact_produccion_{planta}_nuevo.csv
  - fact_paradas_{planta}_raw.csv
  - fact_mantenimiento_{planta}_raw.csv
  - dim_equipos.csv               (SIN ensuciar -- dato maestro, igual que siempre)
  - answer_key_errores_v3.csv     (respuestas, SOLO para autovalidación,
                                    NUNCA mirar antes de intentar resolver)

Reproducible con SEED fija.
"""

import numpy as np
import pandas as pd

SEED = 77
rng = np.random.default_rng(SEED)

prod = pd.read_csv("fact_produccion.csv", parse_dates=["fecha"])
paradas = pd.read_csv("fact_paradas.csv", parse_dates=["fecha"])
mant = pd.read_csv("fact_mantenimiento.csv", parse_dates=["fecha_apertura"])

prod["planta_id"] = prod["equipo_id"].str.split("-").str[0]
paradas["planta_id"] = paradas["equipo_id"].str.split("-").str[0]
mant["planta_id"] = mant["equipo_id"].str.split("-").str[0]

answer_key = []

# =====================================================================
# FECHAS DE MIGRACIÓN ESCALONADAS -- distintas por planta, y NINGUNA cae
# en 1-enero (a propósito, para que no se puedan asumir por "costumbre")
# =====================================================================
FECHA_MIGRACION = {
    "PS": pd.Timestamp("2024-07-15"),  # la más nueva, migra primero
    "PC": pd.Timestamp("2025-03-01"),  # intermedia
    "PN": pd.Timestamp("2026-01-10"),  # la más antigua, migra al final
}


def id_sucio(equipo_id, rng_local, permitir_espacios_ocultos=True):
    variante = rng_local.integers(0, 7 if permitir_espacios_ocultos else 5)
    if variante == 0:
        return equipo_id
    elif variante == 1:
        return equipo_id.replace("-", "")
    elif variante == 2:
        return equipo_id.lower()
    elif variante == 3:
        return f" {equipo_id}"
    elif variante == 4:
        return equipo_id + " "
    elif variante == 5:
        return equipo_id + "\t"          # tab oculto (nuevo, más difícil de ver)
    else:
        return equipo_id.replace("-", "_")  # separador distinto (nuevo)


def romper_encoding(texto):
    """Simula un problema real de encoding UTF-8 leído como Latin-1."""
    try:
        return texto.encode("utf-8").decode("latin-1")
    except Exception:
        return texto


# =====================================================================
# PROCESAR CADA PLANTA POR SEPARADO
# =====================================================================
legacy_frames = {}
nuevo_frames = {}

for planta_id, fecha_corte in FECHA_MIGRACION.items():
    df_planta = prod[prod["planta_id"] == planta_id].copy()
    n_total = len(df_planta)

    df_legacy = df_planta[df_planta["fecha"] < fecha_corte].copy()
    df_nuevo = df_planta[df_planta["fecha"] >= fecha_corte].copy()

    # -----------------------------------------------------------------
    # LEGACY: esquema viejo en español, con toda la suciedad de v1
    # -----------------------------------------------------------------
    n = len(df_legacy)
    legacy = pd.DataFrame({
        "Fecha": df_legacy["fecha"].dt.strftime("%d/%m/%Y"),
        "Cod_Equipo": [id_sucio(e, rng) for e in df_legacy["equipo_id"]],
        "Horas_Trab": df_legacy["horas_operativas"].round(1),
        "Horas_Parada": df_legacy["horas_parada"].round(1),
        "Ton_Producidas": df_legacy["toneladas_procesadas"].round(1),
        "Ton_Rechazo": df_legacy["toneladas_fuera_especificacion"].round(1),
        "Cap_Nominal_TMH": df_legacy["capacidad_nominal_tmh"],
    })
    legacy["Fecha_Carga"] = df_legacy["fecha"].values + pd.to_timedelta(1, unit="D")

    # --- Nulos (~4% Horas_Parada, ~3% Ton_Rechazo) ---
    mask_null_hp = rng.random(n) < 0.04
    legacy.loc[mask_null_hp, "Horas_Parada"] = np.nan
    mask_null_tr = rng.random(n) < 0.03
    legacy.loc[mask_null_tr, "Ton_Rechazo"] = np.nan

    # --- Toneladas negativas (error de signo), ~5-8 por planta ---
    n_neg = max(int(n * 0.0004), 5)
    idx_neg = rng.choice(legacy.index, size=n_neg, replace=False)
    for i in idx_neg:
        val = legacy.loc[i, "Ton_Producidas"]
        legacy.loc[i, "Ton_Producidas"] = -abs(val)
        answer_key.append({"planta": planta_id, "archivo": "legacy", "fila_idx": i,
                            "tipo_error": "toneladas_negativas", "columna": "Ton_Producidas",
                            "valor_original": val, "valor_inyectado": legacy.loc[i, "Ton_Producidas"]})

    # --- Capacidad x10, 1 equipo x 1 mes específico por planta ---
    equipo_cap_afectado = rng.choice(df_legacy["equipo_id"].unique())
    mes_afectado = int(rng.integers(1, 13))
    fechas_dt = pd.to_datetime(legacy["Fecha"], format="%d/%m/%Y")
    equipos_norm = legacy["Cod_Equipo"].str.strip().str.upper().str.replace(r"[\s_]", "", regex=True)
    mask_cap = (equipos_norm == equipo_cap_afectado.replace("-", "")) & (fechas_dt.dt.month == mes_afectado)
    for i in legacy[mask_cap].index:
        val = legacy.loc[i, "Cap_Nominal_TMH"]
        legacy.loc[i, "Cap_Nominal_TMH"] = val * 10
        answer_key.append({"planta": planta_id, "archivo": "legacy", "fila_idx": i,
                            "tipo_error": "capacidad_x10_typo", "columna": "Cap_Nominal_TMH",
                            "valor_original": val, "valor_inyectado": legacy.loc[i, "Cap_Nominal_TMH"]})

    # --- NUEVO: cambio silencioso de unidad (toneladas cortas en vez de
    # métricas) durante 1 mes, en un equipo distinto al de capacidad ---
    FACTOR_TON_CORTA = 1 / 0.907185  # si el sistema reportó en ton corta, el valor
                                       # legible es MAYOR que el valor métrico real
    equipos_disponibles = [e for e in df_legacy["equipo_id"].unique() if e != equipo_cap_afectado]
    equipo_unidad_afectado = rng.choice(equipos_disponibles)
    mes_unidad = int(rng.integers(1, 13))
    mask_unidad = (equipos_norm == equipo_unidad_afectado.replace("-", "")) & (fechas_dt.dt.month == mes_unidad)
    for i in legacy[mask_unidad].index:
        val = legacy.loc[i, "Ton_Producidas"]
        if val > 0:  # no aplicar sobre los ya negativos
            legacy.loc[i, "Ton_Producidas"] = round(val * FACTOR_TON_CORTA, 1)
            answer_key.append({"planta": planta_id, "archivo": "legacy", "fila_idx": i,
                                "tipo_error": "unidad_toneladas_cortas_silenciosa",
                                "columna": "Ton_Producidas",
                                "valor_original": val, "valor_inyectado": legacy.loc[i, "Ton_Producidas"]})

    # --- NUEVO: bloque de días completos faltantes (no aleatorio, es un
    # tramo contiguo de 5-9 días en un equipo -- "outage de sistema") ---
    equipo_outage = rng.choice(df_legacy["equipo_id"].unique())
    fechas_equipo = sorted(df_legacy[df_legacy["equipo_id"] == equipo_outage]["fecha"].unique())
    if len(fechas_equipo) > 20:
        dur_outage = int(rng.integers(5, 10))
        inicio_idx = int(rng.integers(10, len(fechas_equipo) - dur_outage - 10))
        fechas_a_borrar = set(fechas_equipo[inicio_idx: inicio_idx + dur_outage])
        equipos_norm_full = legacy["Cod_Equipo"].str.strip().str.upper().str.replace(r"[\s_]", "", regex=True)
        mask_outage = (equipos_norm_full == equipo_outage.replace("-", "")) & (fechas_dt.isin(fechas_a_borrar))
        for i in legacy[mask_outage].index:
            answer_key.append({"planta": planta_id, "archivo": "legacy", "fila_idx": i,
                                "tipo_error": "bloque_dias_faltantes_outage",
                                "columna": "(fila completa)", "valor_original": "presente",
                                "valor_inyectado": "eliminada"})
        legacy = legacy.drop(index=legacy[mask_outage].index)

    # --- NUEVO: ambigüedad real de formato de fecha (DD/MM vs MM/DD,
    # solo posible en días <=12, colisión genuina en un subconjunto) ---
    fechas_dt2 = pd.to_datetime(legacy["Fecha"], format="%d/%m/%Y")
    candidatas = legacy[(fechas_dt2.dt.day <= 12) & (fechas_dt2.dt.day != fechas_dt2.dt.month)]
    if len(candidatas) > 30:
        idx_ambiguas = rng.choice(candidatas.index, size=min(15, len(candidatas)), replace=False)
        for i in idx_ambiguas:
            d = fechas_dt2.loc[i]
            # se invierte día/mes en el string -- ahora es genuinamente ambiguo
            legacy.loc[i, "Fecha"] = f"{d.month:02d}/{d.day:02d}/{d.year}"
            answer_key.append({"planta": planta_id, "archivo": "legacy", "fila_idx": i,
                                "tipo_error": "fecha_ambigua_dd_mm_vs_mm_dd",
                                "columna": "Fecha", "valor_original": d.strftime("%d/%m/%Y"),
                                "valor_inyectado": legacy.loc[i, "Fecha"]})

    # --- Duplicados con corrección posterior (~3%) ---
    idx_dup_source = rng.choice(legacy.index, size=max(int(len(legacy) * 0.03), 1), replace=False)
    dup_rows = legacy.loc[idx_dup_source].copy()
    dup_rows["Ton_Producidas"] = (dup_rows["Ton_Producidas"] * rng.uniform(0.85, 0.93, len(dup_rows))).round(1)
    dup_rows["Fecha_Carga"] = pd.to_datetime(dup_rows["Fecha_Carga"]) - pd.to_timedelta(
        rng.integers(1, 4, len(dup_rows)), unit="D")

    legacy_final = pd.concat([legacy, dup_rows], ignore_index=True)
    legacy_final = legacy_final.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    legacy_final["Fecha_Carga"] = pd.to_datetime(legacy_final["Fecha_Carga"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    legacy_frames[planta_id] = legacy_final

    # -----------------------------------------------------------------
    # NUEVO: esquema limpio, PERO con grano por turno en equipos/ventana
    # DISTINTOS por planta, más nulos leves y duplicados exactos
    # -----------------------------------------------------------------
    nuevo = df_nuevo.drop(columns=["planta_id"]).copy()
    nuevo["turno"] = np.nan

    equipos_planta = sorted(df_nuevo["equipo_id"].unique())
    equipos_turno = list(rng.choice(equipos_planta, size=2, replace=False))
    fecha_min_nuevo = df_nuevo["fecha"].min()
    offset_dias = int(rng.integers(20, 90))
    ventana_ini = fecha_min_nuevo + pd.Timedelta(days=offset_dias)
    ventana_fin = ventana_ini + pd.Timedelta(days=int(rng.integers(60, 100)))

    filas_normales, filas_turno = [], []
    for _, row in nuevo.iterrows():
        en_ventana = row["equipo_id"] in equipos_turno and ventana_ini <= row["fecha"] <= ventana_fin
        if not en_ventana:
            filas_normales.append(row.to_dict())
            continue
        pesos_h = rng.dirichlet(np.ones(3))
        pesos_par = rng.dirichlet(np.ones(3))
        pesos_ton = np.clip(pesos_h + rng.normal(0, 0.02, 3), 0.01, None)
        pesos_ton = pesos_ton / pesos_ton.sum()
        pesos_rech = rng.dirichlet(np.ones(3))

        horas_turno = np.round(row["horas_operativas"] * pesos_h, 2)
        horas_turno[-1] = round(row["horas_operativas"] - horas_turno[:2].sum(), 2)
        parada_turno = np.round(row["horas_parada"] * pesos_par, 2)
        parada_turno[-1] = round(row["horas_parada"] - parada_turno[:2].sum(), 2)
        ton_turno = np.round(row["toneladas_procesadas"] * pesos_ton, 1)
        ton_turno[-1] = round(row["toneladas_procesadas"] - ton_turno[:2].sum(), 1)
        rech_turno = np.round(row["toneladas_fuera_especificacion"] * pesos_rech, 1)
        rech_turno[-1] = round(row["toneladas_fuera_especificacion"] - rech_turno[:2].sum(), 1)

        for t in range(3):
            filas_turno.append({
                "fecha": row["fecha"], "equipo_id": row["equipo_id"], "turno": t + 1,
                "horas_operativas": horas_turno[t], "horas_parada": parada_turno[t],
                "toneladas_procesadas": ton_turno[t], "toneladas_fuera_especificacion": rech_turno[t],
                "capacidad_nominal_tmh": row["capacidad_nominal_tmh"],
            })

    nuevo_final = pd.DataFrame(filas_normales + filas_turno)

    # --- NUEVO: contaminación cruzada -- unas filas de OTRA planta
    # aparecen mezcladas en este archivo (error de export del sistema) ---
    otras_plantas = [p for p in FECHA_MIGRACION if p != planta_id]
    planta_origen_contaminacion = rng.choice(otras_plantas)
    df_contaminante = prod[
        (prod["planta_id"] == planta_origen_contaminacion) &
        (prod["fecha"] >= nuevo_final["fecha"].min()) &
        (prod["fecha"] <= nuevo_final["fecha"].max())
    ].sample(n=min(8, len(prod)), random_state=int(rng.integers(0, 100000)))
    filas_contaminantes = df_contaminante.drop(columns=["planta_id"]).copy()
    filas_contaminantes["turno"] = np.nan
    for idx_c in filas_contaminantes.index:
        answer_key.append({"planta": planta_id, "archivo": "nuevo", "fila_idx": f"contaminante_{idx_c}",
                            "tipo_error": "contaminacion_cruzada_entre_plantas",
                            "columna": "equipo_id",
                            "valor_original": f"pertenece a planta {planta_origen_contaminacion}",
                            "valor_inyectado": filas_contaminantes.loc[idx_c, "equipo_id"]})
    nuevo_final = pd.concat([nuevo_final, filas_contaminantes], ignore_index=True)

    # --- Nulos leves (~2%) ---
    mask_null = rng.random(len(nuevo_final)) < 0.02
    nuevo_final.loc[mask_null, "toneladas_fuera_especificacion"] = np.nan

    # --- Duplicados exactos (~1%) ---
    idx_dup2 = rng.choice(nuevo_final.index, size=max(int(len(nuevo_final) * 0.01), 1), replace=False)
    nuevo_final = pd.concat([nuevo_final, nuevo_final.loc[idx_dup2]], ignore_index=True)
    nuevo_final = nuevo_final.sample(frac=1.0, random_state=SEED + hash(planta_id) % 1000).reset_index(drop=True)
    nuevo_final["fecha"] = pd.to_datetime(nuevo_final["fecha"]).dt.strftime("%Y-%m-%d")
    nuevo_frames[planta_id] = nuevo_final

    print(f"Planta {planta_id}: migración {fecha_corte.date()} | legacy={len(legacy_final)} | nuevo={len(nuevo_final)} | "
          f"equipo_cap_afectado={equipo_cap_afectado} (mes {mes_afectado}) | "
          f"equipo_unidad_afectado={equipo_unidad_afectado} (mes {mes_unidad})")

# =====================================================================
# GUARDAR ARCHIVOS DE PRODUCCIÓN POR PLANTA
# =====================================================================
for planta_id in FECHA_MIGRACION:
    legacy_frames[planta_id].to_csv(f"fact_produccion_{planta_id}_legacy.csv", index=False, encoding="utf-8-sig")
    nuevo_frames[planta_id].to_csv(f"fact_produccion_{planta_id}_nuevo.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# FACT_PARADAS -- versión cruda por planta (mismo patrón de v1, escalado)
# =====================================================================
for planta_id in FECHA_MIGRACION:
    p = paradas[paradas["planta_id"] == planta_id].drop(columns=["planta_id"]).copy()
    n2 = len(p)
    p["equipo_id"] = [id_sucio(e, rng) for e in p["equipo_id"]]

    mask_fecha_alt = rng.random(n2) < 0.40
    fechas_str = p["fecha"].dt.strftime("%Y-%m-%d")
    fechas_alt = p["fecha"].dt.strftime("%d/%m/%Y")
    p["fecha"] = np.where(mask_fecha_alt, fechas_alt, fechas_str)

    def ensuciar_texto(txt, rng_local):
        v = rng_local.integers(0, 5)
        if v == 0:
            return txt
        elif v == 1:
            return txt.upper()
        elif v == 2:
            return f" {txt.lower()}"
        elif v == 3:
            return f"{txt} "
        else:
            return romper_encoding(txt)  # NUEVO: encoding roto además de casing

    p["tipo_parada"] = [ensuciar_texto(t, rng) for t in p["tipo_parada"]]

    # --- NUEVO: encoding roto en causa (~3% de filas, solo texto con tildes) ---
    mask_encoding = rng.random(n2) < 0.03
    p.loc[mask_encoding, "causa"] = p.loc[mask_encoding, "causa"].apply(
        lambda t: romper_encoding(t) if isinstance(t, str) else t
    )

    mask_null_causa = rng.random(n2) < 0.05
    p.loc[mask_null_causa, "causa"] = np.nan
    mask_null_costo = rng.random(n2) < 0.04
    p.loc[mask_null_costo, "costo_estimado_soles"] = np.nan

    mask_neg = rng.random(n2) < 0.005
    p.loc[mask_neg, "duracion_horas"] = -p.loc[mask_neg, "duracion_horas"]

    idx_dup3 = rng.choice(p.index, size=max(int(n2 * 0.02), 1), replace=False)
    p = pd.concat([p, p.loc[idx_dup3]], ignore_index=True)
    p = p.sample(frac=1.0, random_state=SEED + hash(planta_id + "p") % 1000).reset_index(drop=True)
    p.to_csv(f"fact_paradas_{planta_id}_raw.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# FACT_MANTENIMIENTO -- ensuciado leve por planta
# =====================================================================
for planta_id in FECHA_MIGRACION:
    m = mant[mant["planta_id"] == planta_id].drop(columns=["planta_id"]).copy()
    n3 = len(m)
    mask_null_rep = rng.random(n3) < 0.02
    m.loc[mask_null_rep, "repuesto_principal"] = np.nan
    idx_dup4 = rng.choice(m.index, size=max(int(n3 * 0.01), 1), replace=False)
    m = pd.concat([m, m.loc[idx_dup4]], ignore_index=True)
    m = m.sample(frac=1.0, random_state=SEED + hash(planta_id + "m") % 1000).reset_index(drop=True)
    m.to_csv(f"fact_mantenimiento_{planta_id}_raw.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# ANSWER KEY (autovalidación, NUNCA usar como guía antes de intentarlo)
# =====================================================================
answer_df = pd.DataFrame(answer_key)
answer_df.to_csv("answer_key_errores_v3.csv", index=False, encoding="utf-8-sig")

print()
print("Resumen de errores inyectados por tipo:")
print(answer_df["tipo_error"].value_counts())
print()
print("TOTAL errores documentados en answer_key:", len(answer_df))
print()
print("Fechas de migración por planta (esto SÍ hay que descubrirlo mirando los datos):")
for k, v in FECHA_MIGRACION.items():
    print(f"  {k}: {v.date()}")
