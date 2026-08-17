"""
Capa metalúrgico-financiera multi-planta (v3)
=================================================
Mismo diseño conceptual de v2, extendido a 3 plantas x 4 años. Diferencia
clave de diseño: los PRECIOS DE MERCADO (Cu, Zn, Ag, tipo de cambio) son
GLOBALES -- el mismo día, las 3 plantas venden al mismo precio de
referencia (así funciona un mercado de commodities real). Lo que SÍ
difiere por planta es la ley de mineral, la recuperación metalúrgica y
los volúmenes -- eso es lo que cada planta controla operativamente.

Genera:
  - dim_mineral.csv              (global, sin cambios de v2)
  - fact_precios_mercado.csv     (NUEVO: precios + tipo de cambio, 1 fila
                                   por fecha, compartido por las 3 plantas)
  - fact_produccion_mineral.csv  (grano: fecha x planta)
  - fact_ventas.csv              (grano: fecha x planta, usa fact_precios_mercado)
  - dim_categoria_gasto.csv      (global, sin cambios de v2)
  - fact_gastos.csv              (grano: fecha x planta x categoría)
  - dim_metas_mensuales.csv      (grano: anio_mes x planta)
"""

import numpy as np
import pandas as pd

SEED = 133
rng = np.random.default_rng(SEED)

prod = pd.read_csv("fact_produccion_realista.csv", parse_dates=["fecha"])
prod["planta_id"] = prod["equipo_id"].str.split("-").str[0]

fechas = pd.date_range("2024-01-01", "2027-12-31", freq="D")
n_dias = len(fechas)
plantas = ["PN", "PC", "PS"]


def random_walk_acotado(n, valor_inicial, sigma, lo, hi, rng_local):
    serie = np.zeros(n)
    serie[0] = valor_inicial
    for t in range(1, n):
        serie[t] = np.clip(serie[t - 1] + rng_local.normal(0, sigma), lo, hi)
    return serie


# =====================================================================
# 1) DIM_MINERAL (sin cambios respecto a v2)
# =====================================================================
dim_mineral = pd.DataFrame([
    {"mineral_id": "CU", "nombre": "Cobre", "unidad_ley": "%", "unidad_precio": "USD/lb"},
    {"mineral_id": "ZN", "nombre": "Zinc",  "unidad_ley": "%", "unidad_precio": "USD/lb"},
    {"mineral_id": "AG", "nombre": "Plata", "unidad_ley": "g/t", "unidad_precio": "USD/oz"},
])
dim_mineral.to_csv("dim_mineral.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# 2) FACT_PRECIOS_MERCADO (nuevo -- global, 1 fila por fecha, no por planta)
# =====================================================================
fact_precios = pd.DataFrame({"fecha": fechas})
fact_precios["precio_cu_usd_lb"] = random_walk_acotado(n_dias, 4.1, 0.02, 3.5, 4.8, rng).round(3)
fact_precios["precio_zn_usd_lb"] = random_walk_acotado(n_dias, 1.2, 0.008, 1.0, 1.4, rng).round(3)
fact_precios["precio_ag_usd_oz"] = random_walk_acotado(n_dias, 26.0, 0.15, 22.0, 30.0, rng).round(3)
fact_precios["tipo_cambio_pen_usd"] = random_walk_acotado(n_dias, 3.75, 0.003, 3.65, 3.85, rng).round(4)
fact_precios["fecha_str"] = fact_precios["fecha"].dt.strftime("%Y-%m-%d")
fact_precios_out = fact_precios.drop(columns=["fecha"]).rename(columns={"fecha_str": "fecha"})
fact_precios_out = fact_precios_out[["fecha", "precio_cu_usd_lb", "precio_zn_usd_lb",
                                       "precio_ag_usd_oz", "tipo_cambio_pen_usd"]]
fact_precios_out.to_csv("fact_precios_mercado.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# 3) FACT_PRODUCCION_MINERAL (grano: fecha x planta) -- ley y recuperación
#    PROPIAS de cada planta (parámetros distintos por región/geología)
# =====================================================================
# Rangos de ley base distintos por planta (geología distinta por región)
LEY_CU_BASE = {"PN": 0.65, "PC": 0.80, "PS": 0.90}   # PS tiene mejor geología
LEY_ZN_BASE = {"PN": 1.5, "PC": 2.0, "PS": 1.8}
LEY_AG_BASE = {"PN": 22.0, "PC": 30.0, "PS": 32.0}
LEY_CONC_CU_BASE = {"PN": 28.0, "PC": 29.0, "PS": 30.0}

mineral_rows = []
for planta_id in plantas:
    ley_cu = random_walk_acotado(n_dias, LEY_CU_BASE[planta_id], 0.004, 0.40, 1.20, rng)
    ley_zn = random_walk_acotado(n_dias, LEY_ZN_BASE[planta_id], 0.01, 1.0, 3.0, rng)
    ley_ag = random_walk_acotado(n_dias, LEY_AG_BASE[planta_id], 0.15, 12.0, 48.0, rng)
    ley_conc_cu = random_walk_acotado(n_dias, LEY_CONC_CU_BASE[planta_id], 0.03, 25.0, 33.0, rng)

    # Toneladas de planta = producción del EQ-07 de ESA planta (celda de flotación)
    eq07_id = f"{planta_id}-EQ-07"
    ton_planta = prod[prod["equipo_id"] == eq07_id].set_index("fecha")["toneladas_procesadas"]
    ton_planta = ton_planta.reindex(fechas).ffill()

    paradas_eq07 = prod[prod["equipo_id"] == eq07_id].copy()
    paradas_eq07["anio_mes"] = paradas_eq07["fecha"].dt.to_period("M")
    horas_parada_eq07_mes = paradas_eq07.groupby("anio_mes")["horas_parada"].sum()

    df_p = pd.DataFrame({"fecha": fechas, "planta_id": planta_id})
    df_p["anio_mes"] = df_p["fecha"].dt.to_period("M")
    df_p["ley_cabeza_cu_pct"] = ley_cu.round(3)
    df_p["ley_cabeza_zn_pct"] = ley_zn.round(3)
    df_p["ley_cabeza_ag_gt"] = ley_ag.round(2)
    df_p["ley_concentrado_cu_pct"] = ley_conc_cu.round(2)
    df_p["toneladas_procesadas_planta"] = ton_planta.values.round(1)
    df_p["horas_parada_eq07_mes"] = df_p["anio_mes"].map(horas_parada_eq07_mes)
    df_p["recuperacion_pct"] = (
        93.0 - 0.15 * df_p["horas_parada_eq07_mes"]
    ).clip(lower=80.0, upper=93.0).round(2)

    for metal, col_ley in [("cu", "ley_cabeza_cu_pct"), ("zn", "ley_cabeza_zn_pct")]:
        df_p[f"fino_contenido_{metal}_ton"] = (
            df_p["toneladas_procesadas_planta"] * df_p[col_ley] / 100
        ).round(2)
        df_p[f"fino_recuperado_{metal}_ton"] = (
            df_p[f"fino_contenido_{metal}_ton"] * df_p["recuperacion_pct"] / 100
        ).round(2)

    df_p["fino_contenido_ag_kg"] = (
        df_p["toneladas_procesadas_planta"] * df_p["ley_cabeza_ag_gt"] / 1000
    ).round(2)
    df_p["fino_recuperado_ag_kg"] = (
        df_p["fino_contenido_ag_kg"] * df_p["recuperacion_pct"] / 100
    ).round(2)
    df_p["toneladas_concentrado_cu"] = (
        df_p["fino_recuperado_cu_ton"] / (df_p["ley_concentrado_cu_pct"] / 100)
    ).round(2)

    mineral_rows.append(df_p.drop(columns=["anio_mes", "horas_parada_eq07_mes"]))

fact_mineral = pd.concat(mineral_rows, ignore_index=True)
fact_mineral["fecha"] = fact_mineral["fecha"].dt.strftime("%Y-%m-%d")
fact_mineral.to_csv("fact_produccion_mineral.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# 4) FACT_VENTAS (grano: fecha x planta), usa fact_precios_mercado (compartido)
# =====================================================================
fm = pd.read_csv("fact_produccion_mineral.csv", parse_dates=["fecha"])
precios = pd.read_csv("fact_precios_mercado.csv", parse_dates=["fecha"])

fm = fm.merge(precios, on="fecha", how="left")

LB_POR_TON = 2204.62
OZ_POR_KG = 32.1507

fm["ingreso_cu_usd"] = (fm["fino_recuperado_cu_ton"] * LB_POR_TON * fm["precio_cu_usd_lb"]).round(0)
fm["ingreso_zn_usd"] = (fm["fino_recuperado_zn_ton"] * LB_POR_TON * fm["precio_zn_usd_lb"]).round(0)
fm["ingreso_ag_usd"] = (fm["fino_recuperado_ag_kg"] * OZ_POR_KG * fm["precio_ag_usd_oz"]).round(0)
fm["ingreso_total_usd"] = fm["ingreso_cu_usd"] + fm["ingreso_zn_usd"] + fm["ingreso_ag_usd"]
fm["ingreso_total_pen"] = (fm["ingreso_total_usd"] * fm["tipo_cambio_pen_usd"]).round(0)

fact_ventas = fm[["fecha", "planta_id", "ingreso_cu_usd", "ingreso_zn_usd", "ingreso_ag_usd",
                   "ingreso_total_usd", "ingreso_total_pen"]].copy()
fact_ventas["fecha"] = fact_ventas["fecha"].dt.strftime("%Y-%m-%d")
fact_ventas.to_csv("fact_ventas.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# 5) DIM_CATEGORIA_GASTO + FACT_GASTOS (grano: fecha x planta x categoria)
# =====================================================================
dim_gasto = pd.DataFrame([
    {"categoria_id": "ENE", "nombre": "Energía"},
    {"categoria_id": "MOB", "nombre": "Mano de obra"},
    {"categoria_id": "INS", "nombre": "Insumos y reactivos"},
    {"categoria_id": "OTR", "nombre": "Otros gastos operativos"},
])
dim_gasto.to_csv("dim_categoria_gasto.csv", index=False, encoding="utf-8-sig")

gastos_rows = []
MANO_OBRA_BASE = {"PN": 8500, "PC": 7200, "PS": 9800}  # tamaño de planta distinto
for planta_id in plantas:
    horas_op_planta = (
        prod[prod["planta_id"] == planta_id].groupby("fecha")["horas_operativas"].sum()
        .reindex(fechas).ffill()
    )
    ton_planta_serie = fm[fm["planta_id"] == planta_id].set_index("fecha")["toneladas_procesadas_planta"]
    ton_planta_serie = ton_planta_serie.reindex(fechas).ffill()

    for i, fecha in enumerate(fechas):
        gasto_energia = horas_op_planta.iloc[i] * rng.uniform(180, 220)
        gasto_mano_obra = MANO_OBRA_BASE[planta_id] + rng.normal(0, 150)
        gasto_insumos = ton_planta_serie.iloc[i] * rng.uniform(3.5, 5.0)
        gasto_otros = rng.uniform(1500, 3500)

        for cat_id, monto in [("ENE", gasto_energia), ("MOB", gasto_mano_obra),
                               ("INS", gasto_insumos), ("OTR", gasto_otros)]:
            gastos_rows.append({
                "fecha": fecha.strftime("%Y-%m-%d"), "planta_id": planta_id,
                "categoria_id": cat_id, "monto_soles": round(max(monto, 0), 0),
            })

fact_gastos = pd.DataFrame(gastos_rows)
fact_gastos.to_csv("fact_gastos.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# 6) DIM_METAS_MENSUALES (grano: anio_mes x planta)
# =====================================================================
metas_rows = []
for planta_id in plantas:
    ton_serie = fm[fm["planta_id"] == planta_id].set_index("fecha")["toneladas_procesadas_planta"]
    ton_serie = ton_serie.reindex(fechas).ffill()
    ton_mensual = ton_serie.resample("ME").sum()
    meta = ton_mensual.rolling(window=6, min_periods=1).mean() * 1.02
    meta = meta.shift(1)
    meta.iloc[0] = ton_mensual.iloc[0] * 1.02
    metas_rows.append(pd.DataFrame({
        "anio_mes": ton_mensual.index.strftime("%Y-%m"), "planta_id": planta_id,
        "meta_toneladas_planta": meta.round(1).values,
        "real_toneladas_planta": ton_mensual.round(1).values,
    }))

dim_metas = pd.concat(metas_rows, ignore_index=True)
dim_metas.to_csv("dim_metas_mensuales.csv", index=False, encoding="utf-8-sig")

# =====================================================================
# Resumen
# =====================================================================
print("dim_mineral:", dim_mineral.shape)
print("fact_precios_mercado:", fact_precios_out.shape)
print("fact_produccion_mineral:", fact_mineral.shape)
print("fact_ventas:", fact_ventas.shape)
print("dim_categoria_gasto:", dim_gasto.shape)
print("fact_gastos:", fact_gastos.shape)
print("dim_metas_mensuales:", dim_metas.shape)
print()
print("Nulos por tabla:")
for f in ["fact_precios_mercado.csv","fact_produccion_mineral.csv","fact_ventas.csv","fact_gastos.csv","dim_metas_mensuales.csv"]:
    d = pd.read_csv(f)
    print(f"  {f}: {d.isna().sum().sum()}")
