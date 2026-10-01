# src/produccion.py
# Transformaciones de las tablas de producción (legacy + nuevo) por planta.
# Portadas del notebook Exploracion1.ipynb (PC como planta de referencia).
# Diagnóstico interactivo y exploración siguen en src/eda.py / notebook.

import numpy as np
import pandas as pd

from src.eda import (
    corregir_negativos_con_validacion,
    resolver_duplicados,
    validar_columna_temporal,
)

# =========================================================
# 0) PARAMETROS
# Lo que se descubre a mano por planta vive aquí, NO dentro de las funciones.
PARAMS_DEFAULT = {
    'fecha_ini': '2024-01-01',       # inicio del proyecto
    'fecha_fin': '2027-12-31',       # fin del proyecto
    'huecos_esperados': None,        # int: nº de días faltantes documentados (Cat 13). None = solo reportar
    'corregir_capacidad': True,      # Cat 10: x10 en Cap_Nominal_TMH vs maestro
    'deltas_validos': (-2, -1, 0, 1),  # Fecha_Carga - Fecha aceptables (Cat 12)
    'corregir_unidad': True,         # Cat 10: toneladas cortas -> métricas (detección por techo de eficiencia)
    'propagar_nulos': True,          # colapso de turnos: un NaN en un turno deja NaN el día (luego se imputa)
}

# Ejemplo:
# PARAMS_PLANTAS = {
#     'PC': {'huecos_esperados': 3},
#     'PS': {},
#     'PN': {},
# }
# =========================================================


# =========================================================
# 1) LEGACY: FUNCIONES DE TRANSFORMACION
def normalizar_equipo_id(serie):
    """PC_EQ01 / pc-eq-1 / ' PC-EQ-01 ' -> PC-EQ-01"""
    return (serie.str.strip()
                 .str.upper()
                 .str.replace('_', '-', regex=False)
                 .str.replace(r"^([A-Z]{2})(EQ)", r'\1-\2', regex=True)
                 .str.replace(r'EQ(\d)', r'EQ-\1', regex=True))


def outliers_iqr(df, columna, groupby_col=None):
    """Filas outlier por IQR (1.5x), opcionalmente dentro de cada grupo. Diagnóstico."""
    def _flags(s):
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        return (s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)
    if groupby_col:
        mask = df.groupby(groupby_col)[columna].transform(_flags)
    else:
        mask = _flags(df[columna])
    return df[mask]


def verificar_capacidad_vs_maestro(df, columna_cap, columna_equipo, columna_fecha,
                                   df_maestro, col_maestro_id, col_maestro_valor,
                                   nombre_tabla=""):
    """
    Detecta filas donde columna_cap se desvía de su valor habitual por equipo (IQR)
    y corrige usando el maestro como fuente de verdad, solo para los equipos afectados.
    """
    outliers_cap = outliers_iqr(df, columna=columna_cap, groupby_col=columna_equipo)

    if outliers_cap.empty:
        print(f"[{nombre_tabla}] '{columna_cap}' es constante en todos los equipos -- nada que corregir")
        return df, pd.DataFrame()

    equipos_afectados = outliers_cap[columna_equipo].unique()
    print(f"[{nombre_tabla}] Equipos con outliers en '{columna_cap}': {list(equipos_afectados)}")

    df_corregido = df.copy()
    reporte = []

    for equipo in equipos_afectados:
        anomalas_equipo = outliers_cap[outliers_cap[columna_equipo] == equipo]

        fechas_dt = pd.to_datetime(df.loc[df[columna_equipo] == equipo, columna_fecha], dayfirst=True)
        distrib_mensual = df.loc[df[columna_equipo] == equipo].groupby(
            fechas_dt.dt.month)[columna_cap].value_counts()

        match_maestro = df_maestro.loc[df_maestro[col_maestro_id] == equipo, col_maestro_valor]
        if match_maestro.empty:
            print(f"  AVISO {equipo}: no encontrado en el maestro -- se deja intacto")
            continue
        valor_correcto = match_maestro.iloc[0]

        valores_anomalos = anomalas_equipo[columna_cap].unique()
        print(f"  {equipo}: {len(anomalas_equipo)} filas con {list(valores_anomalos)} "
              f"| maestro dice {valor_correcto} | distribución mensual:\n{distrib_mensual}")

        mask = (df_corregido[columna_equipo] == equipo) & (df_corregido[columna_cap] != valor_correcto)
        n_corregidas = mask.sum()
        df_corregido.loc[mask, columna_cap] = valor_correcto

        reporte.append({
            'equipo': equipo,
            'valor_correcto': valor_correcto,
            'valores_encontrados': list(valores_anomalos),
            'filas_corregidas': n_corregidas,
        })

    return df_corregido, pd.DataFrame(reporte)


def imputar_por_tasa_equipo(df, col_objetivo, col_base, col_equipo, decimales=1, nombre_tabla=""):
    """
    Imputa nulos de col_objetivo con (mediana de col_objetivo/col_base del propio equipo) * col_base.
    Sirve para Ton_Rechazo (legacy) y toneladas_fuera_especificacion (nuevo).
    """
    df = df.copy()
    tasa_equipo = (
        df.dropna(subset=[col_objetivo])
          .assign(tasa=lambda d: d[col_objetivo] / d[col_base])
          .groupby(col_equipo)['tasa'].median()
    )

    mask_nulo = df[col_objetivo].isna()
    n_a_imputar = int(mask_nulo.sum())

    df.loc[mask_nulo, col_objetivo] = (
        df.loc[mask_nulo, col_equipo].map(tasa_equipo) * df.loc[mask_nulo, col_base]
    ).round(decimales)

    restantes = int(df[col_objetivo].isna().sum())
    print(f"[{nombre_tabla}] '{col_objetivo}': imputados {n_a_imputar} | nulos restantes {restantes}")
    return df


def imputar_horas_parada(df, col_trab='Horas_Trab', col_parada='Horas_Parada',
                         horas_dia=24, nombre_tabla=""):
    """Horas_Parada nula = horas_dia - Horas_Trab (relación exacta verificada en PC)."""
    df = df.copy()
    n_excede = int(((df[col_trab] + df[col_parada]) > horas_dia + 0.01).sum())
    if n_excede:
        print(f"[{nombre_tabla}] AVISO: {n_excede} filas con {col_trab} + {col_parada} > {horas_dia}")

    mask_nulo = df[col_parada].isna()
    df.loc[mask_nulo, col_parada] = horas_dia - df.loc[mask_nulo, col_trab]
    print(f"[{nombre_tabla}] '{col_parada}': imputados {int(mask_nulo.sum())} "
          f"| nulos restantes {int(df[col_parada].isna().sum())}")
    return df


def corregir_fechas_ambiguas(df, col_fecha='Fecha', col_carga='Fecha_Carga',
                             deltas_validos=(-2, -1, 0, 1), nombre_tabla=""):
    """
    Cat 12: fechas DD/MM vs MM/DD mal interpretadas. Requiere col_fecha y col_carga ya datetime.
    Una fila es anómala si (Fecha_Carga - Fecha) cae fuera de deltas_validos.
    Corrección: invertir día/mes (no depende de Fecha_Carga). Devuelve (df, reporte).
    """
    df = df.copy()
    delta = (df[col_carga] - df[col_fecha]).dt.days
    mask = delta.notna() & ~delta.isin(deltas_validos)
    anomalas = df.loc[mask, col_fecha]

    if anomalas.empty:
        print(f"[{nombre_tabla}] Sin fechas ambiguas fuera de {list(deltas_validos)}")
        return df, pd.DataFrame()

    invertible = anomalas.dt.day <= 12   # el día se vuelve mes: debe ser <= 12
    no_invertibles = anomalas[~invertible]
    if len(no_invertibles):
        print(f"[{nombre_tabla}] AVISO: {len(no_invertibles)} fechas anómalas NO se pueden invertir "
              f"(día > 12). Índices: {list(no_invertibles.index)}")

    a_invertir = anomalas[invertible]
    fecha_swap = a_invertir.apply(lambda f: pd.Timestamp(year=f.year, month=f.day, day=f.month))

    reporte = pd.DataFrame({
        'fecha_mal_interpretada': a_invertir,
        'fecha_via_swap': fecha_swap,
        'fecha_via_carga_menos_1': df.loc[a_invertir.index, col_carga] - pd.Timedelta(days=1),
    })
    reporte['coinciden'] = reporte['fecha_via_swap'] == reporte['fecha_via_carga_menos_1']

    df.loc[fecha_swap.index, col_fecha] = fecha_swap.values
    print(f"[{nombre_tabla}] Fechas invertidas: {len(fecha_swap)} "
          f"(coinciden con Fecha_Carga-1: {int(reporte['coinciden'].sum())})")
    return df, reporte


def resolver_duplicados_legacy(df, clave=('Fecha', 'Cod_Equipo'), col_fecha='Fecha',
                               col_carga='Fecha_Carga', delta_valido=1, nombre_tabla=""):
    """
    Duplicados por clave: se conserva la fila con Fecha_Carga - Fecha == delta_valido.
    Solo aplica si CADA grupo tiene exactamente 1 fila válida; si no, no toca nada y
    devuelve los grupos ambiguos. Devuelve (df, grupos_ambiguos).
    """
    clave = list(clave)
    es_correcta = ((df[col_carga] - df[col_fecha]).dt.days == delta_valido)
    mask_dup = df.duplicated(subset=clave, keep=False)

    if not mask_dup.any():
        print(f"[{nombre_tabla}] Sin duplicados por clave {clave}")
        return df, pd.Series(dtype=int)

    validas_por_grupo = es_correcta[mask_dup].groupby([df.loc[mask_dup, c] for c in clave]).sum()
    ambiguos = validas_por_grupo[validas_por_grupo != 1]

    if len(ambiguos) > 0:
        print(f"[{nombre_tabla}] {len(ambiguos)} grupos sin exactamente 1 fila válida -- "
              f"NO se aplica el criterio, revisar manualmente.")
        return df, ambiguos

    n_antes = len(df)
    df_limpio = df[(~mask_dup) | (mask_dup & es_correcta)]
    print(f"[{nombre_tabla}] Duplicados resueltos: {n_antes} -> {len(df_limpio)} filas")
    return df_limpio, ambiguos


def corregir_unidad_toneladas_cortas(df, col_ton='Ton_Producidas', col_horas='Horas_Trab',
                                     col_cap='Cap_Nominal_TMH', col_equipo='Cod_Equipo', col_fecha='Fecha',
                                     techo=0.99, umbral_certeza=1.0, nombre_tabla=""):
    """
    Cat 10: cambio silencioso de unidad (toneladas cortas en vez de métricas).
    Detección por techo teórico: eficiencia = ton / (horas * capacidad) nunca supera ~0.99 en el
    proceso normal. Se corrigen solo las filas con eficiencia > umbral_certeza (evidencia directa);
    el resto se documenta como limitación, no se fuerza. Debe correr DESPUES de corregir la capacidad
    (x10) y ANTES de descartar Cap_Nominal_TMH. Devuelve (df, reporte).
    """
    FACTOR_TON_CORTA = 1 / 0.907185
    df = df.copy()
    eficiencia = df[col_ton] / (df[col_horas] * df[col_cap])
    imposibles = eficiencia[eficiencia > techo]
    idx = eficiencia[eficiencia > umbral_certeza].index

    reporte = pd.DataFrame({
        col_equipo: df.loc[idx, col_equipo], col_fecha: df.loc[idx, col_fecha],
        'ton_antes': df.loc[idx, col_ton], 'eficiencia_antes': eficiencia[idx],
    })
    df.loc[idx, col_ton] = (df.loc[idx, col_ton] / FACTOR_TON_CORTA).round(1)
    reporte['ton_despues'] = df.loc[idx, col_ton]

    print(f"[{nombre_tabla}] Eficiencia > {techo}: {len(imposibles)} filas | "
          f"corregidas con certeza (> {umbral_certeza}): {len(idx)}")
    return df, reporte


def detectar_huecos(df, col_equipo='Cod_Equipo', col_fecha='Fecha'):
    """Días ausentes dentro del rango registrado de cada equipo. Solo reporta, no imputa (Cat 13)."""
    filas = []
    for equipo, grupo in df.groupby(col_equipo):
        rango = pd.date_range(grupo[col_fecha].min(), grupo[col_fecha].max())
        for f in rango.difference(grupo[col_fecha]):
            filas.append({'equipo': equipo, 'fecha_faltante': f})
    return pd.DataFrame(filas, columns=['equipo', 'fecha_faltante'])
# =========================================================


# =========================================================
# 2) NUEVO: FUNCIONES DE TRANSFORMACION
def detectar_contaminacion_cruzada(df, planta_esperada, df_maestro,
                                   col_equipo='equipo_id', col_planta='planta_id'):
    """Filas cuyo equipo_id pertenece (según el maestro) a otra planta o no existe en él (Cat 11)."""
    planta_real = df[col_equipo].map(df_maestro.drop_duplicates(col_equipo).set_index(col_equipo)[col_planta])
    contaminacion = df[planta_real != planta_esperada]
    print(f"[{planta_esperada}] Filas contaminadas (no pertenecen a esta planta): {len(contaminacion)}")
    return contaminacion


def eliminar_contaminacion_cruzada(df, planta_esperada, df_maestro,
                                   col_equipo='equipo_id', col_planta='planta_id'):
    """Quita las filas contaminadas. No depende del tipo de índice del df."""
    contaminacion = detectar_contaminacion_cruzada(df, planta_esperada, df_maestro, col_equipo, col_planta)
    return df.drop(contaminacion.index)


def _suma_estricta(s):
    """Suma que devuelve NaN si algún elemento es NaN (a diferencia de sum() normal)."""
    return s.sum(min_count=len(s))


def colapsar_grano_turno(df, columnas_flujo, columnas_fijas, nombre_planta="", propagar_nulos=True):
    """
    Colapsa filas con grano turno (turno no nulo) a grano diario: suma columnas de flujo,
    'first' en columnas fijas. Filas ya diarias no se tocan.
    propagar_nulos=True: si algún turno tiene NaN en una columna de flujo, el día colapsado
    queda NaN (y luego lo imputa imputar_por_tasa_equipo) en vez de sumar de menos en silencio.
    """
    filas_turno = df[df['turno'].notna()]
    if filas_turno.empty:
        print(f"[{nombre_planta}] No hay filas con grano turno -- nada que colapsar.")
        return df

    equipos_turno = filas_turno['equipo_id'].unique()
    ventana = filas_turno['fecha'].agg(['min', 'max'])
    print(f"[{nombre_planta}] Equipos con grano turno: {list(equipos_turno)} | "
          f"ventana: {ventana['min']} -> {ventana['max']}")

    nulos_turno = filas_turno[columnas_flujo].isna().sum()
    if nulos_turno.sum() > 0:
        print(f"[{nombre_planta}] AVISO: nulos en filas de turno antes de colapsar:\n{nulos_turno[nulos_turno > 0]}")

    fn_suma = _suma_estricta if propagar_nulos else 'sum'
    agg_dict = {c: fn_suma for c in columnas_flujo}
    agg_dict.update({c: 'first' for c in columnas_fijas})

    colapsado = filas_turno.groupby(['fecha', 'equipo_id'], as_index=False).agg(agg_dict)
    colapsado['turno'] = np.nan

    df_final = pd.concat([df[df['turno'].isna()], colapsado], ignore_index=True)
    print(f"[{nombre_planta}] Shape tras colapso: {df_final.shape} | "
          f"¿queda turno no nulo?: {df_final['turno'].notna().sum()}")
    return df_final
# =========================================================


# =========================================================
# 3) CONSOLIDACION Y CIERRE
def consolidar_legacy_nuevo(df_legacy, df_nuevo, nombre_planta=""):
    """
    Une legacy y nuevo en el esquema de 'nuevo'. Descarta Cap_Nominal_TMH / capacidad_nominal_tmh
    (viven solo en dim_equipos), Fecha_Carga y columnas auxiliares de diagnóstico.
    """
    mapeo = {
        'Fecha': 'fecha', 'Cod_Equipo': 'equipo_id',
        'Horas_Trab': 'horas_operativas', 'Horas_Parada': 'horas_parada',
        'Ton_Producidas': 'toneladas_procesadas', 'Ton_Rechazo': 'toneladas_fuera_especificacion',
    }
    legacy = df_legacy.rename(columns=mapeo)

    columnas_auxiliares = ['Cap_Nominal_TMH', 'Fecha_Carga', 'anio_mes', 'eficiencia_implicita']
    legacy = legacy.drop(columns=[c for c in columnas_auxiliares if c in legacy.columns])

    if 'turno' not in legacy.columns:
        legacy['turno'] = np.nan

    nuevo = df_nuevo.drop(columns=[c for c in ['capacidad_nominal_tmh'] if c in df_nuevo.columns])
    nuevo['fecha'] = pd.to_datetime(nuevo['fecha'])

    df_final = pd.concat([legacy, nuevo], ignore_index=True)
    print(f"[{nombre_planta}] Shape consolidado: {df_final.shape}")
    return df_final


def validar_cierre(df_final, fecha_ini, fecha_fin, equipos, col_fecha='fecha',
                   col_equipo='equipo_id', nombre_planta=""):
    """
    Compara el calendario completo (fecha x equipo) contra la tabla consolidada.
    Devuelve dict con esperadas / reales / huecos y el MultiIndex de los huecos.
    """
    esperado = pd.MultiIndex.from_product(
        [pd.date_range(fecha_ini, fecha_fin), list(equipos)], names=[col_fecha, col_equipo])
    faltan = esperado.difference(df_final.set_index([col_fecha, col_equipo]).index)
    resultado = {'esperadas': len(esperado), 'reales': len(df_final), 'huecos': len(faltan)}
    print(f"[{nombre_planta}] Cierre: esperadas {resultado['esperadas']} | "
          f"reales {resultado['reales']} | huecos {resultado['huecos']}")
    return resultado, faltan
# =========================================================


# =========================================================
# 4) ORQUESTADORES
def _log(log, paso, df, **extra):
    log.append({'paso': paso, 'filas': len(df), **extra})


def procesar_legacy(df_raw, planta, dim_equipos, params=None):
    """
    Orden (el que reproduce PC en el notebook):
    equipo -> negativos -> capacidad vs maestro -> nulos Ton_Rechazo -> nulos Horas_Parada
    -> fechas a datetime -> swap DD/MM -> duplicados -> unidad (ton cortas) -> huecos (solo reporte)
    Devuelve (df_legacy_limpio, log, huecos_df).
    """
    p = {**PARAMS_DEFAULT, **(params or {})}
    nombre = f"prodLegacy_{planta}"
    df, log = df_raw.copy(), []
    _log(log, 'carga', df)

    # 1) Equipo normalizado y validado contra el maestro
    df['Cod_Equipo'] = normalizar_equipo_id(df['Cod_Equipo'])
    equipos_planta = dim_equipos.loc[dim_equipos['planta_id'] == planta, 'equipo_id']
    desconocidos = set(df['Cod_Equipo'].unique()) - set(equipos_planta)
    if desconocidos:
        print(f"[{nombre}] AVISO: equipos que no existen en dim_equipos: {desconocidos}")
    _log(log, 'equipo_normalizado', df, desconocidos=sorted(desconocidos))

    # 2) Negativos en Ton_Producidas (dudosos quedan para revisión manual)
    df, dudosos = corregir_negativos_con_validacion(df, 'Ton_Producidas', 'Cod_Equipo', nombre_tabla=nombre)
    _log(log, 'negativos', df, dudosos=len(dudosos))

    # 3) Cap_Nominal_TMH vs maestro (Cat 10)
    if p['corregir_capacidad']:
        df, rep_cap = verificar_capacidad_vs_maestro(
            df, columna_cap='Cap_Nominal_TMH', columna_equipo='Cod_Equipo', columna_fecha='Fecha',
            df_maestro=dim_equipos, col_maestro_id='equipo_id', col_maestro_valor='capacidad_nominal_tmh',
            nombre_tabla=nombre)
        _log(log, 'capacidad', df, filas_corregidas=int(rep_cap['filas_corregidas'].sum()) if len(rep_cap) else 0)

    # 4) Nulos
    df = imputar_por_tasa_equipo(df, 'Ton_Rechazo', 'Ton_Producidas', 'Cod_Equipo', nombre_tabla=nombre)
    df = imputar_horas_parada(df, nombre_tabla=nombre)
    _log(log, 'nulos', df)

    # 5) Fechas -> datetime, luego swap DD/MM (ANTES de duplicados: el swap resuelve colisiones)
    df = validar_columna_temporal(df, 'Fecha', tipo='fecha')
    df = validar_columna_temporal(df, 'Fecha_Carga', tipo='fecha')
    df, rep_fechas = corregir_fechas_ambiguas(df, deltas_validos=p['deltas_validos'], nombre_tabla=nombre)
    _log(log, 'fechas', df, fechas_invertidas=len(rep_fechas))

    # 6) Duplicados por clave
    df, ambiguos = resolver_duplicados_legacy(df, nombre_tabla=nombre)
    _log(log, 'duplicados', df, grupos_ambiguos=len(ambiguos))

    # 7) Cambio de unidad (Cat 10): despues de capacidad y duplicados, antes de consolidar
    if p['corregir_unidad']:
        df, rep_unidad = corregir_unidad_toneladas_cortas(df, nombre_tabla=nombre)
        _log(log, 'unidad', df, filas_corregidas=len(rep_unidad))

    # 8) Huecos: solo reporte (no se imputa, Cat 13)
    huecos = detectar_huecos(df)
    _log(log, 'huecos', df, huecos=len(huecos))
    print(f"[{nombre}] Huecos detectados: {len(huecos)}")

    return df, log, huecos


def procesar_nuevo(df_raw, planta, dim_equipos, params=None):
    """
    Orden: contaminación cruzada -> colapso de turno -> nulos fuera_especificacion -> duplicados.
    Devuelve (df_nuevo_limpio, log).
    """
    p = {**PARAMS_DEFAULT, **(params or {})}
    nombre = f"prodNuevo_{planta}"
    df, log = df_raw.copy(), []
    _log(log, 'carga', df)

    df = eliminar_contaminacion_cruzada(df, planta, dim_equipos)
    _log(log, 'contaminacion', df)

    df = colapsar_grano_turno(
        df,
        columnas_flujo=['horas_operativas', 'horas_parada', 'toneladas_procesadas', 'toneladas_fuera_especificacion'],
        columnas_fijas=['capacidad_nominal_tmh'],
        nombre_planta=planta,
        propagar_nulos=p['propagar_nulos'])
    _log(log, 'colapso_turno', df)

    df = imputar_por_tasa_equipo(df, 'toneladas_fuera_especificacion', 'toneladas_procesadas',
                                 'equipo_id', nombre_tabla=nombre)
    _log(log, 'nulos', df)

    df, exactos, conflictivos = resolver_duplicados(
        df,
        subset_clave=['fecha', 'equipo_id'],
        columnas_desempate=None,
        nombre_tabla=nombre,
        columnas_grano_esperado=['horas_operativas', 'horas_parada', 'toneladas_procesadas',
                                 'toneladas_fuera_especificacion', 'capacidad_nominal_tmh'])
    _log(log, 'duplicados', df, exactos=len(exactos), conflictivos=len(conflictivos))

    return df, log


def procesar_planta(df_legacy_raw, df_nuevo_raw, planta, dim_equipos, params=None):
    """
    Legacy + nuevo + consolidación + validación de cierre.
    Devuelve (df_final, resumen) con resumen = logs de cada etapa + resultado del cierre.
    """
    p = {**PARAMS_DEFAULT, **(params or {})}

    legacy, log_l, huecos_legacy = procesar_legacy(df_legacy_raw, planta, dim_equipos, p)
    nuevo, log_n = procesar_nuevo(df_nuevo_raw, planta, dim_equipos, p)

    df_final = consolidar_legacy_nuevo(legacy, nuevo, nombre_planta=planta)

    equipos = dim_equipos.loc[dim_equipos['planta_id'] == planta, 'equipo_id']
    cierre, faltan = validar_cierre(df_final, p['fecha_ini'], p['fecha_fin'], equipos, nombre_planta=planta)

    esperados = p['huecos_esperados']
    cierre['ok'] = None if esperados is None else (cierre['huecos'] == esperados)
    if cierre['ok'] is False:
        print(f"[{planta}] CIERRE NO CUADRA: huecos {cierre['huecos']} vs esperados {esperados}")

    resumen = {'log_legacy': log_l, 'log_nuevo': log_n, 'cierre': cierre,
               'huecos_legacy': huecos_legacy, 'huecos_cierre': faltan}
    return df_final, resumen
# =========================================================
