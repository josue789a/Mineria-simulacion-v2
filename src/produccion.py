# src/produccion.py
# Transformaciones de las tablas de producción (legacy + nuevo) por planta.
# Portadas del notebook Exploracion1.ipynb (PC como planta de referencia).
# Diagnóstico interactivo y exploración siguen en src/eda.py / notebook.
# Regla: lo generico vive en eda.py (se importa); lo propio de produccion
# (imputar_por_tasa_equipo, detectar_contaminacion_cruzada, etc.) vive aqui. Sin copias en ambos.

import numpy as np
import pandas as pd

# Funciones genericas (sirven a mas de una tabla): viven en src/eda.py, NO se redefinen aqui.
from src.eda import (
    corregir_fechas_ambiguas,
    corregir_negativos_con_validacion,
    normalizar_equipo_id,
    resolver_duplicados,
    validar_columna_temporal,
    verificar_capacidad_vs_maestro,
)

# =========================================================
# 0) PARAMETROS
# Lo que se descubre a mano por planta vive aquí, NO dentro de las funciones.
PARAMS_DEFAULT = {
    'fecha_ini': '2024-01-01',       # inicio del proyecto
    'fecha_fin': '2027-12-31',       # fin del proyecto
    'huecos_esperados': None,        # int: numero de días faltantes documentados (Cat 13). None = solo reportar
    'corregir_capacidad': True,      # Cat 10: x10 en Cap_Nominal_TMH vs maestro
    'deltas_validos': (-2, -1, 0, 1),  # Fecha_Carga - Fecha aceptables (Cat 12)
    'corregir_unidad': True,         # Cat 10: toneladas cortas -> metricas. True = se aplica; False = se omite
                                     # (util para diagnosticar una planta sin tocar la unidad)
}



# =========================================================
# 1) LEGACY: FUNCIONES DE TRANSFORMACION


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

# Misma logica de arriba (techo de eficiencia 0.99, correccion solo si eficiencia > 1.0), empaquetada en funcion. Se usa desde procesar_legacy() en src/produccion.py.
def corregir_unidad_toneladas_cortas(df, col_ton='Ton_Producidas', col_horas='Horas_Trab',
                                     col_cap='Cap_Nominal_TMH', col_equipo='Cod_Equipo', col_fecha='Fecha',
                                     techo=0.99, umbral_certeza=1.0, nombre_tabla=""):
    """Cat 10: cambio silencioso de unidad (toneladas cortas en vez de metricas). Corrige solo las filas con eficiencia > umbral_certeza. Debe correr DESPUES de corregir la capacidad (x10). Devuelve (df, reporte)."""
    FACTOR_TON_CORTA = 1 / 0.907185
    df = df.copy()
    eficiencia = df[col_ton] / (df[col_horas] * df[col_cap])
    sospechosas = eficiencia[eficiencia > techo] # Toda aquella que supere el techo teorico del equipo
    idx_corregir = eficiencia[eficiencia > umbral_certeza].index # Con certeza de imposibilidad de alcnazar esa eficiencia

    reporte = pd.DataFrame({ #Se arma diccionario de reporte
        col_equipo: df.loc[idx_corregir, col_equipo], 
        col_fecha: df.loc[idx_corregir, col_fecha],
        'ton_antes': df.loc[idx_corregir, col_ton], 
        'eficiencia_antes': eficiencia[idx_corregir], # Eficiencia antes de certeza de correccion de formula de conversion
    })

    df.loc[idx_corregir, col_ton] = (df.loc[idx_corregir, col_ton] / FACTOR_TON_CORTA).round(1) # Garantiza la correcion de conversion de factor
    reporte['ton_despues'] = df.loc[idx_corregir, col_ton]

    print(f"[{nombre_tabla}] Eficiencia > {techo}: {len(sospechosas)} filas | corregidas con certeza (> {umbral_certeza}): {len(idx_corregir)}")
    return df, reporte




def resolver_duplicados_legacy(df, grano=('Fecha', 'Cod_Equipo'), col_fecha='Fecha',
                               col_carga='Fecha_Carga', delta_valido=1, nombre_tabla=""):
    """
    Duplicados por grano: se conserva la fila con Fecha_Carga - Fecha == delta_valido.
    Solo aplica si CADA grupo tiene exactamente 1 fila válida; si no, no toca nada y
    devuelve los grupos ambiguos. Devuelve (df, grupos_ambiguos).
    """
    grano = list(grano)
    delta_correcto = ((df[col_carga] - df[col_fecha]).dt.days == delta_valido)  # True si el delta de la fila es el esperado
    mask_dup = df.duplicated(subset=grano, keep=False)  # True en TODAS las filas de un grupo repetido (original y copia)

    if not mask_dup.any():
        print(f"[{nombre_tabla}] Sin duplicados por grano {grano}")
        return df, pd.Series(dtype=int)

    # Se recorta delta_correcto a las filas duplicadas y se suma por grano:
    # 1 = exactamente una fila con delta válido ( VALIDO )
    validas_por_grupo = delta_correcto[mask_dup].groupby(
        [df.loc[mask_dup, col] for col in grano]).sum()     # Se ubica en base al (mask_dup con datos validos , con las columnas del grano), procede a sumar el delta correcto de cada fila duplicada( n valores con diferentes delta por cada duplicado)
    ambiguos = validas_por_grupo[validas_por_grupo != 1]    # un delta difernte a 1 como 0 o 2 = ambiguo


    if len(ambiguos) > 0:
        print(f"[{nombre_tabla}] {len(ambiguos)} grupos sin exactamente 1 fila válida -- "
              f"NO se aplica el criterio, revisar manualmente.")
        return df, ambiguos

    n_antes = len(df)
    df_limpio = df[(~mask_dup) | (mask_dup & delta_correcto)]  # no duplicadas + duplicadas con delta válido
    print(f"[{nombre_tabla}] Duplicados resueltos: {n_antes} -> {len(df_limpio)} filas")
    return df_limpio, ambiguos


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
    return s.sum(min_count=len(s)) #solo devuelve la suma si hay al menos n valores no nulos; si no, devuelve NaN


def colapsar_grano_turno(df, columnas_flujo_partible, columnas_fijas, nombre_planta="", propagar_nulos=True):
    """
    Colapsa filas con grano turno (turno no nulo) a grano diario: suma columnas de flujo,
    'first' en columnas fijas. Filas ya diarias no se tocan.
    propagar_nulos=True: si algún turno tiene NaN en una columna de flujo, el día colapsado
    queda NaN (y luego lo imputa imputar_por_tasa_equipo) en vez de sumar de menos en silencio.
    """
    filas_turno = df[df['turno'].notna()] # Solo filas partidas por turno
    if filas_turno.empty: # Empty marca TRUE si es vacio (filas turno)
        print(f"[{nombre_planta}] No hay filas con grano turno -- nada que colapsar.")
        return df

    equipos_turno = filas_turno['equipo_id'].unique()
    ventana = filas_turno['fecha'].agg(['min', 'max']) #recordar .agg recibia los metodos de agregacion como texto: first,count,std,mean, median,etc
    print(f"[{nombre_planta}] Equipos con grano turno: {list(equipos_turno)} | "f"ventana: {ventana['min']} -> {ventana['max']}"
          )

    nulos_turno = filas_turno[columnas_flujo_partible].isna().sum()
    if nulos_turno.sum() > 0:
        print(f"[{nombre_planta}] AVISO: nulos en filas de turno antes de colapsar:\n{nulos_turno[nulos_turno > 0]}")

    fn_suma = _suma_estricta if propagar_nulos else 'sum'

    agg_dict = {col: fn_suma for col in columnas_flujo_partible} #OJO COMPRESION DE DICCIONARIO de suma estricta si esta definido propagar_nulos, para cada elemento de  'columnas_flujo_partible' (toma keys) y fn_suma toma values
    agg_dict.update({col: 'first' for col in columnas_fijas}) #Las columas fijas  no se reparten su flujo por turno, se repite denuevo para cada turno, por eso nos quedamos solo con 'first', first toma values para la 'columnas_fija'
                                                          #Ejemplo agg_dict = {'horas_operativas': 'sum', 'capacidad_nominal_tmh': 'first'}

    colapsado = filas_turno.groupby(['fecha', 'equipo_id'], as_index=False).agg(agg_dict) #No TOMES las columnas de agrupacion como indice -- aplica funciones de agregacion en base al diccionario 'agg_dict'
    colapsado['turno'] = np.nan

    df_colapsado = pd.concat([df[df['turno'].isna()], 
                                        colapsado], 
                                        ignore_index=True)
    print(f"[{nombre_planta}] Shape tras colapso: {df_colapsado.shape} | "
          f"¿queda turno no nulo?: {df_colapsado['turno'].notna().sum()}")
    return df_colapsado
# =========================================================


# =========================================================
# 3) ORQUESTADORES
def _log(log, paso, df, **extra):
    log.append({'paso': paso, 'filas': len(df), **extra}) #Extra puede entregar mas de uno si entregamos en la llamada


def procesar_legacy(df_raw, planta, dim_equipos, params=None):
    """
    Orden (el que reproduce PC en el notebook):
    equipo -> negativos -> capacidad vs maestro -> nulos Ton_Rechazo -> nulos Horas_Parada
    -> fechas a datetime -> swap DD/MM -> duplicados -> unidad (ton cortas) -> huecos (solo reporte)
    Devuelve (df_legacy_limpio, log, huecos_df).
    """
    p = {**PARAMS_DEFAULT, **(params or {})}
    nombre = f"prodLegacy_{planta}"
    df, log = df_raw.copy(), [] #copia_df, lista vacia para el sig log
    _log(log, 'carga', df)

    # 1) Equipo normalizado y validado contra el maestro
    df['Cod_Equipo'] = normalizar_equipo_id(df['Cod_Equipo'])
    equipos_planta = dim_equipos.loc[dim_equipos['planta_id'] == planta, 'equipo_id'] # Equipos de la planta especificada
    desconocidos = set(df['Cod_Equipo'].unique()) - set(equipos_planta) # Obtener equipos no presentes en el df maestro, con una diferencia de set's
    if desconocidos:
        print(f"[{nombre}] AVISO: equipos que no existen en dim_equipos: {desconocidos}")
    _log(log, 'equipo_normalizado', df, desconocidos=sorted(desconocidos))

    # 2) Negativos en Ton_Producidas (dudosos quedan para revisión manual)
    df, dudosos = corregir_negativos_con_validacion(df, 'Ton_Producidas', 'Cod_Equipo', nombre_tabla=nombre)
    _log(log, 'negativos', df, dudosos=len(dudosos))

     # 3) Cap_Nominal_TMH vs maestro (outlier x10, no es Cat 10)
    if p['corregir_capacidad']:  # lee p = PARAMS_DEFAULT + params de esta planta (True por defecto)
        df, rep_capacidad = verificar_capacidad_vs_maestro(
            df, columna_cap='Cap_Nominal_TMH', columna_equipo='Cod_Equipo', columna_fecha='Fecha',
            df_maestro=dim_equipos, col_maestro_id='equipo_id', col_maestro_valor='capacidad_nominal_tmh',
            nombre_tabla=nombre)
        _log(log, 'capacidad', df,
             filas_corregidas=int(rep_capacidad['filas_corregidas'].sum()) if len(rep_capacidad) else 0)
        #                     └────────────── valor A ───────────────────┘ if └─ condición ─┘ else └ B ┘
        # A se usa si la condición es verdadera (hay equipos en el reporte); si no, B = 0
        
    # 4) Nulos
    df = imputar_por_tasa_equipo(df, 'Ton_Rechazo', 'Ton_Producidas', 'Cod_Equipo', nombre_tabla=nombre) # Procedemos imputando la tasa de produccion obtenida de cada equipo a los nulos
    df = imputar_horas_parada(df, nombre_tabla=nombre)
    _log(log, 'nulos', df)

    # 5) Fechas -> datetime, luego swap DD/MM (ANTES de duplicados: el swap resuelve colisiones)
    df = validar_columna_temporal(df, 'Fecha', tipo='fecha')
    df = validar_columna_temporal(df, 'Fecha_Carga', tipo='fecha')
    df, rep_fechas = corregir_fechas_ambiguas(df, deltas_validos=p['deltas_validos'], nombre_tabla=nombre)
    _log(log, 'fechas', df, fechas_invertidas=len(rep_fechas))

    # 6) Duplicados por grano
    df, ambiguos = resolver_duplicados_legacy(df, nombre_tabla=nombre)
    _log(log, 'duplicados', df, grupos_ambiguos=len(ambiguos))

    # 7) Cambio de unidad (Cat 10): despues de capacidad (x10) y duplicados, antes de consolidar.
    #    Necesita Cap_Nominal_TMH ya corregida y Fecha/Cod_Equipo ya limpios.
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
    Orden: contaminación cruzada -> duplicados exactos -> colapso de turno -> nulos fuera_especificacion -> duplicados por clave.
    Devuelve (df_nuevo_limpio, log).
    """
    # Contaminación primero: quitar las filas de otra planta antes de todo para que no arrastren nada a los pasos siguientes (colapso, imputación por tasa de equipo).
    # Duplicados exactos antes del colapso: un turno repetido se sumaría dos veces y daría días con más de 24 h. Un turno legítimo nunca es idéntico a otro porque la columna 'turno' los distingue (1, 2, 3).
    # Colapso después de quitar duplicados: así cada día suma solo turnos reales y queda una fila por la agrupacion de (fecha, equipo_id).
    # Imputación después del colapso: la tasa  ( toneladas_fuera_especificacion / toneladas_procesadas )  debe calcularse sobre filas diarias, no sobre fragmentos de turno.
    # Duplicados por clave al final:  Aseguramos y comprobamos que (fecha, equipo_id) sea único y avisa si hay conflictivos.
        
    nombre = f"prodNuevo_{planta}"
    df, log = df_raw.copy(), []
    _log(log, 'carga', df)

    # 1) Contaminacion cruzada
    df = eliminar_contaminacion_cruzada(df, planta, dim_equipos)
    _log(log, 'contaminacion', df)

    # 2) Duplicados eexactos
    df = df.drop_duplicates()
    _log(log, 'duplicados_exactos', df)

    # 2) Colapso de turnos
    df = colapsar_grano_turno(
        df,
        columnas_flujo_partible=['horas_operativas', 'horas_parada', 'toneladas_procesadas', 'toneladas_fuera_especificacion'],
        columnas_fijas=['capacidad_nominal_tmh'],
        nombre_planta=planta)
    _log(log, 'colapso_turno', df)

    # 3) Imputar tasas por equipo
    df = imputar_por_tasa_equipo(df, 'toneladas_fuera_especificacion', 'toneladas_procesadas',
                                 'equipo_id', nombre_tabla=nombre)
    _log(log, 'nulos', df)

    # 4) Duplicados por clave
    df, exactos, conflictivos = resolver_duplicados( # Tras el colapso (fecha, equipo_id) debe ser única.Con columnas_grano_esperado, si una clave aún tuviera valores distintos (turnos sin colapsar), avisa y NO borra; sin eso, subset_clave dejaría solo 1 de los 3 turnos.

        df,
        subset_clave=['fecha', 'equipo_id'],
        columnas_desempate=None,
        nombre_tabla=nombre,    
        columnas_grano_esperado=['horas_operativas', 'horas_parada', 'toneladas_procesadas',
                                 'toneladas_fuera_especificacion', 'capacidad_nominal_tmh'])
    _log(log, 'duplicados', df, exactos=len(exactos), conflictivos=len(conflictivos))

    return df, log


def procesar_planta(df_legacy_raw, df_nuevo_raw, planta, dim_equipos, params=None): #Orquesta procesa_legacy y procesa_nuevo
    """
    Legacy + nuevo + consolidación + validación de cierre.
    Devuelve (df_consolidado, resumen) con resumen = logs de cada etapa + resultado del cierre.
    """
    p = {**PARAMS_DEFAULT, **(params or {})}

    legacy, log_legacy, huecos_legacy = procesar_legacy(df_legacy_raw, planta, dim_equipos, p)  #salidas con return, funcion ()
    nuevo, log_nuevo = procesar_nuevo(df_nuevo_raw, planta, dim_equipos, p)

    df_consolidado = consolidar_legacy_y_nuevo(legacy, nuevo, nombre_planta=planta)

    equipos = dim_equipos.loc[dim_equipos['planta_id'] == planta, 'equipo_id']
    cierre, huecos_cierre = validar_cierre(df_consolidado, p['fecha_ini'], p['fecha_fin'], equipos, nombre_planta=planta)

    esperados = p['huecos_esperados']
    cierre['ok'] = None if esperados is None else (cierre['n_huecos'] == esperados)
    if cierre['ok'] is False:
        print(f"[{planta}] CIERRE NO CUADRA: n_huecos {cierre['n_huecos']} vs esperados {esperados}")

    resumen = {'log_legacy': log_legacy, 'log_nuevo': log_nuevo, 'cierre': cierre,
               'huecos_legacy': huecos_legacy, 'huecos_cierre': huecos_cierre}
    return df_consolidado, resumen
# =========================================================

# =========================================================
# 4) CONSOLIDACION Y CIERRE
def consolidar_legacy_y_nuevo(df_legacy, df_nuevo, nombre_planta=""): #Elimina columnas de soporte auxiliares y concatena
    """
    Une legacy y nuevo en el esquema de 'nuevo'. Descarta Cap_Nominal_TMH / capacidad_nominal_tmh
    (viven solo en dim_equipos), Fecha_Carga y columnas auxiliares de diagnóstico.
    """
    mapeo = {
        'Fecha': 'fecha', 'Cod_Equipo': 'equipo_id',
        'Horas_Trab': 'horas_operativas', 'Horas_Parada': 'horas_parada',
        'Ton_Producidas': 'toneladas_procesadas', 'Ton_Rechazo': 'toneladas_fuera_especificacion',
    }

    # Legacy: igualar nombres al esquema de nuevo y quitar lo que no pasa a la tabla final
    legacy = df_legacy.rename(columns=mapeo)
    legacy = legacy.drop(
        columns=['Cap_Nominal_TMH', 'Fecha_Carga', 'anio_mes', 'eficiencia_implicita'],
        errors='ignore')  # anio_mes y eficiencia_implicita solo existen si vienes del cuaderno

    if 'turno' not in legacy.columns:  # Legacy es de grano diario y no tiene turnos
        legacy['turno'] = np.nan       # Se agrega VACIO para que el esquema coincida al CONCANTENAR

    nuevo = df_nuevo.drop(columns='capacidad_nominal_tmh')
    nuevo['fecha'] = pd.to_datetime(nuevo['fecha'])  # datetime, para que coincida con el calendario de validar_cierre

    df_consolidado = pd.concat([legacy, nuevo], ignore_index=True)
    print(f"[{nombre_planta}] Shape consolidado: {df_consolidado.shape}")
    return df_consolidado


def validar_cierre(df_consolidado, fecha_ini, fecha_fin, equipos, col_fecha='fecha',     # Calendario ideal: todas las parejas (fecha, equipo) que deberían existir, verifica datos completos y compara huecos esperado
                   col_equipo='equipo_id', nombre_planta=""): 
    esperado = pd.MultiIndex.from_product( #Mas de 1 indice(Fecha + equipo_id)  | from_product(arma las combinaciones posibles del date_range y equipos ) 
        [pd.date_range(fecha_ini, fecha_fin),  #(multiindex_1)
        list(equipos)], #(multiindex_2)
        names=[col_fecha, col_equipo]) 

    # Parejas que sí existen en la tabla consolidada
    reales = df_consolidado.set_index([col_fecha, col_equipo]).index

    # Esperado menos real = huecos
    huecos_cierre = esperado.difference(reales) # resta a lo esperado, los reales y deja las parejas de huecos cierre que faltan.

    resultado = {'esperadas': len(esperado), 'reales': len(df_consolidado), 'n_huecos': len(huecos_cierre)} #Cantidad de huevos del df_consolidado, vs huecos reales
    print(f"[{nombre_planta}] Cierre: esperadas {resultado['esperadas']} | "
          f"reales {resultado['reales']} | n_huecos {resultado['n_huecos']}")
    return resultado, huecos_cierre
# =========================================================