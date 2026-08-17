"""
Capa de realismo multi-planta (v3)
=====================================
Igual lógica que aplicar_realismo.py de v2 (tendencia + estacionalidad +
ruido con memoria), pero con estacionalidad DISTINTA por planta según su
región climática -- esa es la diferenciación real que justifica el
modelo multi-planta, no solo un volumen mayor de filas.

  PN (Costa)       -> impacto de lluvia bajo, algo de riesgo El Niño en feb-mar
  PC (Sierra Centro)-> impacto de lluvia fuerte ene-mar (la más afectada)
  PS (Sierra Sur)   -> impacto de lluvia moderado, jul-ago mantenimiento más marcado
                        (altura -> logística de repuestos más lenta)

Tendencia anual también difiere por planta: PS (más nueva) mejora más
rápido, PN (más antigua) mejora más lento.
"""

import numpy as np
import pandas as pd

SEED = 121
rng = np.random.default_rng(SEED)

df = pd.read_csv("fact_produccion.csv", parse_dates=["fecha"])
df = df.sort_values(["equipo_id", "fecha"]).reset_index(drop=True)
df["planta_id"] = df["equipo_id"].str.split("-").str[0]

TENDENCIA_MENSUAL = {"PN": 0.002, "PC": 0.004, "PS": 0.007}  # mejora mensual acumulada, desde 2025

ESTACIONALIDAD = {
    "PN": {1: -0.02, 2: -0.06, 3: -0.03, 7: -0.03, 8: -0.03},  # costa: riesgo El Niño feb-mar
    "PC": {1: -0.10, 2: -0.12, 3: -0.07, 7: -0.04, 8: -0.05},  # sierra centro: lluvia fuerte
    "PS": {1: -0.06, 2: -0.07, 3: -0.04, 7: -0.06, 8: -0.07},  # sierra sur: mant. jul-ago marcado
}

RUIDO_MEMORIA_PHI = 0.7
RUIDO_MEMORIA_SIGMA = 0.03
FRACCION_ESTACIONALIDAD_A_PARADA = 0.5


def factor_tendencia(fecha, planta_id):
    if fecha.year < 2025:
        return 0.0
    meses_desde_ene25 = (fecha.year - 2025) * 12 + (fecha.month - 1)
    return TENDENCIA_MENSUAL[planta_id] * meses_desde_ene25


def factor_estacionalidad(fecha, planta_id):
    return ESTACIONALIDAD[planta_id].get(fecha.month, 0.0)


df["_tendencia"] = df.apply(lambda r: factor_tendencia(r["fecha"], r["planta_id"]), axis=1)
df["_estacionalidad"] = df.apply(lambda r: factor_estacionalidad(r["fecha"], r["planta_id"]), axis=1)

df["_ruido"] = 0.0
for equipo_id, grupo in df.groupby("equipo_id"):
    idx = grupo.index
    n = len(idx)
    ruido = np.zeros(n)
    shock = rng.normal(0, RUIDO_MEMORIA_SIGMA, n)
    for t in range(1, n):
        ruido[t] = RUIDO_MEMORIA_PHI * ruido[t - 1] + shock[t]
    ruido = np.clip(ruido, -0.15, 0.15)
    df.loc[idx, "_ruido"] = ruido

df["_factor_final"] = (1 + df["_tendencia"]) * (1 + df["_estacionalidad"]) * (1 + df["_ruido"])
df["toneladas_procesadas"] = (df["toneladas_procesadas"] * df["_factor_final"]).round(1).clip(lower=0)

mask_estacion_negativa = df["_estacionalidad"] < 0
exceso_horas = (-df["_estacionalidad"] * FRACCION_ESTACIONALIDAD_A_PARADA * 24)
df.loc[mask_estacion_negativa, "horas_parada"] = (
    df.loc[mask_estacion_negativa, "horas_parada"] + exceso_horas.loc[mask_estacion_negativa]
).clip(upper=24)
df["horas_operativas"] = (24 - df["horas_parada"]).clip(lower=0)

tope = df["horas_operativas"] * df["capacidad_nominal_tmh"] * 1.10
df["toneladas_procesadas"] = np.where(
    tope.notna() & (df["toneladas_procesadas"] > tope), tope, df["toneladas_procesadas"]
)

pct_fuera_espec_original = (
    df["toneladas_fuera_especificacion"] / df["toneladas_procesadas"].replace(0, np.nan)
).fillna(0)
df["toneladas_fuera_especificacion"] = (df["toneladas_procesadas"] * pct_fuera_espec_original).round(1)

df_final = df.drop(columns=["_tendencia", "_estacionalidad", "_ruido", "_factor_final", "planta_id"])
df_final["horas_operativas"] = df_final["horas_operativas"].round(1)
df_final["horas_parada"] = df_final["horas_parada"].round(1)
df_final["fecha"] = df_final["fecha"].dt.strftime("%Y-%m-%d")
df_final.to_csv("fact_produccion_realista.csv", index=False, encoding="utf-8-sig")

# Validación: comparar totales anuales por planta -- deben diferir entre sí
chk = pd.read_csv("fact_produccion_realista.csv", parse_dates=["fecha"])
chk["planta_id"] = chk["equipo_id"].str.split("-").str[0]
resumen = chk.groupby(["planta_id", chk["fecha"].dt.year])["toneladas_procesadas"].sum().unstack(0)
print("Total toneladas por planta y año:")
print(resumen.round(0))
print()
print("Shape:", df_final.shape, "| Nulos:", df_final.isna().sum().sum())
