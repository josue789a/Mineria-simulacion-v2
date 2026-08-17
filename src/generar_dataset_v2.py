"""
Generador multi-planta / multi-año (v3)
==========================================
Extiende el modelo original a 3 plantas concentradoras y 4 años
(2024-01-01 a 2027-12-31), manteniendo la misma lógica de negocio del
generador v1 (MTBF/MTTR simulado por clase de confiabilidad, mismo flujo
de proceso Chancado->Molienda->Flotación->Espesado->Filtrado), pero con
parámetros DISTINTOS por planta para que la comparación entre plantas
sea real y no una copia.

Plantas:
  PN - Planta Norte  (costa, equipos más antiguos, capacidad 1.0x)
  PC - Planta Centro (sierra, mayor exposición a lluvias, capacidad 0.8x)
  PS - Planta Sur    (sierra alta, equipos más nuevos, capacidad 1.2x)

Genera (sin errores inyectados -- ese ejercicio ya se hizo en v1/v2 y no
se repite aquí, el objetivo de v3 es escala, no limpieza):
  - dim_plantas.csv
  - dim_equipos.csv       (equipo_id con prefijo de planta: PN-EQ-01, ...)
  - fact_produccion.csv   (base, SIN tendencia/estacionalidad -- eso lo
                            aplica aplicar_realismo_v3.py después)
  - fact_paradas.csv
  - fact_mantenimiento.csv

Reproducible con SEED fija.
"""

import numpy as np
import pandas as pd
from datetime import date

SEED = 100
rng = np.random.default_rng(SEED)

# -------------------------------------------------------------------
# 1) DIM_PLANTAS
# -------------------------------------------------------------------
dim_plantas = pd.DataFrame([
    {"planta_id": "PN", "nombre_planta": "Planta Norte", "region": "Costa",
     "tipo_clima": "Costa (seco, riesgo El Niño)", "factor_capacidad": 1.0,
     "anio_inicio_operacion": 2015},
    {"planta_id": "PC", "nombre_planta": "Planta Centro", "region": "Sierra Centro",
     "tipo_clima": "Sierra (lluvias fuertes ene-mar)", "factor_capacidad": 0.8,
     "anio_inicio_operacion": 2012},
    {"planta_id": "PS", "nombre_planta": "Planta Sur", "region": "Sierra Sur",
     "tipo_clima": "Sierra alta (lluvias moderadas)", "factor_capacidad": 1.2,
     "anio_inicio_operacion": 2019},
])
dim_plantas.to_csv("dim_plantas.csv", index=False, encoding="utf-8-sig")

# -------------------------------------------------------------------
# 2) DIM_EQUIPOS (mismo catálogo base de 10 equipos, replicado x planta
#    con capacidad ajustada por factor_capacidad y confiabilidad
#    ligeramente distinta por planta -- PN más antigua = peor
#    confiabilidad promedio, PS más nueva = mejor)
# -------------------------------------------------------------------
equipos_base = [
    ("EQ-01", "Chancadora Primaria",   "Chancado",  "Chancadora", 520, "media"),
    ("EQ-02", "Chancadora Secundaria", "Chancado",  "Chancadora", 430, "media"),
    ("EQ-03", "Chancadora Terciaria",  "Chancado",  "Chancadora", 380, "alta"),
    ("EQ-04", "Molino SAG",            "Molienda",  "Molino",     460, "baja"),
    ("EQ-05", "Molino de Bolas 1",     "Molienda",  "Molino",     300, "baja"),
    ("EQ-06", "Molino de Bolas 2",     "Molienda",  "Molino",     300, "media"),
    ("EQ-07", "Celda de Flotación",    "Flotación", "Flotacion",  350, "alta"),
    ("EQ-08", "Espesador de Relave",   "Espesado",  "Espesador",  400, "media"),
    ("EQ-09", "Filtro Prensa",         "Filtrado",  "Filtro",     260, "alta"),
    ("EQ-10", "Faja Transportadora 3", "Chancado",  "Faja",       500, "media"),
]

# Ajuste de confiabilidad por planta: PN (antigua) degrada 1 nivel en 3 de
# 10 equipos; PS (nueva) mejora 1 nivel en 3 de 10 equipos; PC se queda
# en la confiabilidad base.
DEGRADAR_EN_PN = {"EQ-04", "EQ-05", "EQ-10"}
MEJORAR_EN_PS = {"EQ-04", "EQ-05", "EQ-10"}
ORDEN_CONFIABILIDAD = ["baja", "media", "alta"]

def ajustar_confiabilidad(clase, delta):
    i = ORDEN_CONFIABILIDAD.index(clase)
    i = min(max(i + delta, 0), 2)
    return ORDEN_CONFIABILIDAD[i]

filas_equipos = []
anio_base_instalacion = {"EQ-01": 2016, "EQ-02": 2016, "EQ-03": 2019, "EQ-04": 2014,
                          "EQ-05": 2014, "EQ-06": 2018, "EQ-07": 2017, "EQ-08": 2015,
                          "EQ-09": 2020, "EQ-10": 2016}

for _, planta in dim_plantas.iterrows():
    planta_id = planta["planta_id"]
    factor_cap = planta["factor_capacidad"]
    for eq_num, nombre, area, tipo, cap_base, clase_base in equipos_base:
        clase = clase_base
        if planta_id == "PN" and eq_num in DEGRADAR_EN_PN:
            clase = ajustar_confiabilidad(clase_base, -1)
        elif planta_id == "PS" and eq_num in MEJORAR_EN_PS:
            clase = ajustar_confiabilidad(clase_base, +1)

        # año de instalación: PN más antigua (-3 años), PS más nueva (+3 años) vs base
        anio_ajuste = {"PN": -3, "PC": 0, "PS": 3}[planta_id]

        filas_equipos.append({
            "equipo_id": f"{planta_id}-{eq_num}",
            "planta_id": planta_id,
            "nombre_equipo": nombre,
            "area": area,
            "tipo_equipo": tipo,
            "capacidad_nominal_tmh": round(cap_base * factor_cap, 1),
            "anio_instalacion": anio_base_instalacion[eq_num] + anio_ajuste,
            "clase_confiabilidad": clase,
        })

dim_equipos = pd.DataFrame(filas_equipos)
dim_equipos.to_csv("dim_equipos.csv", index=False, encoding="utf-8-sig")

# -------------------------------------------------------------------
# 3) Generación de fact_produccion / fact_paradas / fact_mantenimiento
#    (misma lógica de generar_dataset.py v1, ahora recorriendo 3 plantas
#    x 4 años)
# -------------------------------------------------------------------
mtbf_objetivo = {"alta": 280, "media": 170, "baja": 105}
mttr_objetivo = {"alta": 5.0, "media": 8.0, "baja": 12.0}

fecha_inicio = date(2024, 1, 1)
fecha_fin = date(2027, 12, 31)
fechas = pd.date_range(fecha_inicio, fecha_fin, freq="D")
HORAS_DIA = 24.0

produccion_rows = []
paradas_rows = []
mantenimiento_rows = []
parada_id_counter = 1
orden_id_counter = 1

for _, eq in dim_equipos.iterrows():
    equipo_id = eq["equipo_id"]
    clase = eq["clase_confiabilidad"]
    cap_nominal = eq["capacidad_nominal_tmh"]
    mtbf_h = mtbf_objetivo[clase]
    mttr_h = mttr_objetivo[clase]

    horas_hasta_prox_falla = rng.exponential(mtbf_h)
    horas_acumuladas_operativas = 0.0
    prox_preventivo = rng.integers(14, 24)
    dias_desde_ultimo_preventivo = 0

    for fecha in fechas:
        horas_parada_dia = 0.0
        eventos_hoy = []
        dias_desde_ultimo_preventivo += 1

        if dias_desde_ultimo_preventivo >= prox_preventivo:
            dur = round(rng.uniform(4, 9), 1)
            horas_parada_dia += dur
            eventos_hoy.append(("Preventiva", dur, "Mantenimiento programado (plan anual)"))
            dias_desde_ultimo_preventivo = 0
            prox_preventivo = rng.integers(14, 24)

        if rng.random() < 0.06:
            dur = round(rng.uniform(0.5, 3.0), 1)
            causa = rng.choice([
                "Falta de mineral en cancha", "Corte de energía externo",
                "Condiciones climáticas adversas",
                "Espera de insumos (reactivos/bolas de molienda)",
            ])
            horas_parada_dia += dur
            eventos_hoy.append(("Operativa", dur, causa))

        horas_disponibles_hoy = max(HORAS_DIA - horas_parada_dia, 0)
        horas_acumuladas_operativas += horas_disponibles_hoy
        if horas_acumuladas_operativas >= horas_hasta_prox_falla:
            dur = round(max(rng.exponential(mttr_h), 0.5), 1)
            dur = min(dur, 20.0)
            causa = rng.choice([
                "Falla mecánica - desgaste de componente", "Falla eléctrica - motor/tablero",
                "Rotura de faja/correa", "Atoro de mineral / obstrucción", "Falla de lubricación",
            ])
            horas_parada_dia = min(horas_parada_dia + dur, HORAS_DIA)
            eventos_hoy.append(("Correctiva", dur, causa))
            horas_acumuladas_operativas = 0.0
            horas_hasta_prox_falla = rng.exponential(mtbf_h)

        horas_parada_dia = min(horas_parada_dia, HORAS_DIA)
        horas_operativas_dia = HORAS_DIA - horas_parada_dia

        eficiencia = np.clip(rng.normal(0.90, 0.05), 0.55, 0.99)
        toneladas_procesadas = round(horas_operativas_dia * cap_nominal * eficiencia, 1)
        pct_fuera_espec = np.clip(rng.normal(0.02, 0.008), 0.0, 0.15)
        toneladas_fuera_espec = round(toneladas_procesadas * pct_fuera_espec, 1)

        produccion_rows.append({
            "fecha": fecha.date(), "equipo_id": equipo_id,
            "horas_operativas": round(horas_operativas_dia, 1),
            "horas_parada": round(horas_parada_dia, 1),
            "toneladas_procesadas": toneladas_procesadas,
            "toneladas_fuera_especificacion": toneladas_fuera_espec,
            "capacidad_nominal_tmh": cap_nominal,
        })

        for tipo_parada, dur, causa in eventos_hoy:
            pid = f"PAR-{parada_id_counter:06d}"
            parada_id_counter += 1
            hora_inicio = rng.integers(0, max(int(24 - dur), 1))
            paradas_rows.append({
                "parada_id": pid, "equipo_id": equipo_id, "fecha": fecha.date(),
                "hora_inicio_aprox": f"{hora_inicio:02d}:00", "duracion_horas": dur,
                "tipo_parada": tipo_parada, "causa": causa,
                "costo_estimado_soles": round(dur * rng.uniform(800, 2200), 0)
                    if tipo_parada != "Operativa" else round(dur * rng.uniform(200, 600), 0),
            })
            if tipo_parada in ("Correctiva", "Preventiva"):
                oid = f"OT-{orden_id_counter:06d}"
                orden_id_counter += 1
                mantenimiento_rows.append({
                    "orden_id": oid, "parada_id": pid, "equipo_id": equipo_id,
                    "fecha_apertura": fecha.date(), "tipo_orden": tipo_parada,
                    "horas_hombre": round(dur * rng.uniform(0.8, 1.6), 1),
                    "num_tecnicos": int(rng.integers(1, 4)),
                    "repuesto_principal": rng.choice([
                        "Rodamiento", "Faja/correa", "Sello mecánico", "Motor eléctrico",
                        "Revestimiento (liner)", "Sensor/instrumento", "Ninguno (solo mano de obra)"
                    ]),
                    "costo_repuestos_soles": round(rng.uniform(0, 8000), 0)
                        if tipo_parada == "Correctiva" else round(rng.uniform(0, 2500), 0),
                })

fact_produccion = pd.DataFrame(produccion_rows)
fact_paradas = pd.DataFrame(paradas_rows)
fact_mantenimiento = pd.DataFrame(mantenimiento_rows)

fact_produccion.to_csv("fact_produccion.csv", index=False, encoding="utf-8-sig")
fact_paradas.to_csv("fact_paradas.csv", index=False, encoding="utf-8-sig")
fact_mantenimiento.to_csv("fact_mantenimiento.csv", index=False, encoding="utf-8-sig")

print("dim_plantas:", dim_plantas.shape)
print("dim_equipos:", dim_equipos.shape)
print("fact_produccion:", fact_produccion.shape)
print("fact_paradas:", fact_paradas.shape)
print("fact_mantenimiento:", fact_mantenimiento.shape)
