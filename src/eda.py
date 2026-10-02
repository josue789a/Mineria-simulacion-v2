# src/eda.py

import re
import pandas as pd

# =========================================================
# 0.1) Formatos de fecha/hora reconocidos por el proyecto
FORMATOS_FECHA = {
    'YMD': '%Y-%m-%d',
    'YMD_SLASH': '%Y/%m/%d',
    'DMY': '%d-%m-%Y',
    'DMY_SLASH': '%d/%m/%Y',
    'YMD_TIME': '%Y-%m-%d %H:%M:%S',
}

FORMATOS_HORA = {
    'HH_MM': '%H:%M',
    'HH_MM_SS': '%H:%M:%S',
}

# 0.2) Vocabulario de tipos: que dtype de pandas corresponde cada etiqueta de tipo usada en los esquemas (ej. esquema_paradas). Esto es  fijo para todo el proyecto no cambia de una tabla a otra puesto usa los tipos de pandas, y por lo mismo que no hace pegarlo en cada cuaderno cuando corresponda usar la funcion aplicar de aplicar trasnformaciones
DTYPE_ESPERADO = {
    'fecha':      'datetime64[us]',
    'hora':       object,
    'fecha_hora': 'datetime64[us]',
    'entero':     'Int64',
    'decimal':    'float64',
    'categorico': 'string',
}

# 0.3) Conversores que necesitan el DataFrame completo (contexto de toda la columna, no valor por valor) -- caso fecha/hora, donde hay que mirar TODA la columna para detectar el formato antes de convertir.
CONVERSOR_TEMPORAL = {
    'fecha': lambda df, col: validar_columna_temporal(df, col, tipo='fecha'),
    'hora':  lambda df, col: validar_columna_temporal(df, col, tipo='hora'),
}

# 0.4) Conversores que operan sobre la Serie sola (vectorizado, sin contexto extra) -- caso entero/decimal/categórico.
CONVERSOR_CATEGORICO_NUMERICO = {
    'entero':     lambda serie: pd.to_numeric(serie, errors='coerce').astype('Int64'),
    'decimal':    lambda serie: pd.to_numeric(serie, errors='coerce'),
    'categorico': lambda serie: serie.astype('string').str.strip(),
}
# =========================================================


# =========================================================
## 1) FUNCION PARA VERIFICAR CALIDAD BASICA DE DATAFRAMES
def reporte_calidad(df, nombre_df=""):
    reporte = pd.DataFrame({
        'columna': df.columns,
        'tipo_dato': df.dtypes.values,
        'duplicados': df.duplicated().mean(),
        'no_nulos': df.count().values,
        'nulos': df.isnull().sum().values,
        'pct_nulos': (df.isnull().mean() * 100).round(2),
        'unicos': df.nunique().values,
    })

    reporte = reporte.sort_values('pct_nulos', ascending=False)
    reporte = reporte.reset_index(drop=True)

    total_filas = len(df)
    filas_duplicadas = df.duplicated().sum()

    print(f"\n--- Resumen: {nombre_df or 'DataFrame'} ---")
    print(f"Total filas del df: {total_filas}")
    print(f"Sumatoria filas duplicadas: {filas_duplicadas} "
          f"({(filas_duplicadas / total_filas * 100):.2f}%)")
    print(f"Columnas: {len(df.columns)}")

    return reporte
# =========================================================


# =========================================================
## 2) FUNCIONES PARA AVERIGUAR LA NATURALEZA DE UNA COLUMNA DE FECHA U HORA
def clasificar_formato_fecha(valor):

    if pd.isna(valor):
        return None

    valor = str(valor).strip()

    if re.fullmatch(r'\d{4}-\d{1,2}-\d{1,2}', valor):
        return 'YMD'
    if re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}', valor):
        return 'YMD_SLASH'
    if re.fullmatch(r'\d{1,2}-\d{1,2}-\d{4}', valor):
        return 'DMY'
    if re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}', valor):
        return 'DMY_SLASH'
    if re.fullmatch(r'\d{4}-\d{1,2}-\d{1,2} \d{2}:\d{2}:\d{2}', valor):
        return 'YMD_TIME'

    return 'DESCONOCIDO'
# =========================================================


# =========================================================
def clasificar_formato_hora(valor):

    if pd.isna(valor):
        return None

    valor = str(valor).strip()

    if re.fullmatch(r'\d{2}:\d{2}', valor):
        return 'HH_MM'
    if re.fullmatch(r'\d{2}:\d{2}:\d{2}', valor):
        return 'HH_MM_SS'

    return 'DESCONOCIDO'
# =========================================================


# =========================================================
## 3) FUNCION PARA RESOLVER DUPLICADOS
def resolver_duplicados(df, subset_clave, columnas_desempate=None, nombre_tabla="",
                          columnas_grano_esperado=None):
    if columnas_grano_esperado:
        chequeo = df.groupby(subset_clave)[columnas_grano_esperado].nunique()
        rotos = chequeo[(chequeo > 1).any(axis=1)]

        if len(rotos) > 0:
            print(f"⚠️ [{nombre_tabla}] ALERTA: {len(rotos)} '{subset_clave}' tienen "
                  f"múltiples valores en {columnas_grano_esperado}. La clave NO es segura tal cual.")
            return df, pd.DataFrame(), rotos

    mask_dup = df.duplicated(subset=subset_clave, keep=False)
    dup = df[mask_dup]

    exactos = dup[dup.duplicated(keep=False)]
    conflictivos = dup.drop(exactos.index)

    print(f"[{nombre_tabla}] duplicados exactos: {len(exactos)} filas | "
          f"con conflicto real: {len(conflictivos)} filas")

    df_limpio = df.drop_duplicates(subset=None if not conflictivos.empty else subset_clave,
                                    keep='first')

    if not conflictivos.empty and columnas_desempate:
        cols = columnas_desempate if isinstance(columnas_desempate, list) else [columnas_desempate]
        df_limpio = (df.sort_values(cols)
                       .drop_duplicates(subset=subset_clave, keep='last'))

    return df_limpio, exactos, conflictivos
# =========================================================


# =========================================================
## 4) FUNCION ORQUESTADORA PARA UNA COLUMNA DE TIEMPO, SEA FECHA U HORA
## Reemplaza a la antigua validar_fechas() — esa quedó descartada porque
## solo cubría fecha, no centralizaba el guard de nulos, y dependía de una
## variable 'formatos' que en algunas copias del archivo no llegó a
## definirse (bug latente que solo se disparaba con formatos mezclados).
def validar_columna_temporal(df, columna, tipo='fecha'):
    clasificador = clasificar_formato_fecha if tipo == 'fecha' else clasificar_formato_hora
    formatos = FORMATOS_FECHA if tipo == 'fecha' else FORMATOS_HORA

    no_nulos = df[columna].notna()
    valores_str = df.loc[no_nulos, columna].astype(str).str.strip()

    tipo_detectado = pd.Series(index=df.index, dtype='object')
    tipo_detectado.loc[no_nulos] = valores_str.apply(clasificador)

    conteo_formatos = tipo_detectado.value_counts()
    print(f"  ↳ [validar_columna_temporal] Verificación de '{columna}' (tipo={tipo}):")
    print(conteo_formatos)
    print()

    formato_unico = len(conteo_formatos) == 1 and conteo_formatos.index[0] != 'DESCONOCIDO'

    if formato_unico:
        fmt = formatos[conteo_formatos.index[0]]
        if tipo == 'fecha':
            df[columna] = pd.to_datetime(df[columna], format=fmt)
        else:
            df[columna] = pd.to_datetime(df[columna], format=fmt).dt.time
        print(f"  ↳ [validar_columna_temporal] Validación correcta. Formato único. Columna convertida.")
        print()
        return df

    print(f"  ↳ [validar_columna_temporal] La columna NO pasó la validación de formato único.")
    print(f"  ↳ [validar_columna_temporal] Formatos encontrados: {dict(conteo_formatos)}")
    print(f"  ↳ [validar_columna_temporal] Por consecuente, aplicando conversión por máscara "
          f"(cada subconjunto con su propio formato para cada tipo detectado)...")

    convertidos = pd.Series(pd.NaT, index=df.index, dtype='object')
    formatos_sin_conversor = []
    for tipo_fmt, _ in conteo_formatos.items():
        fmt = formatos.get(tipo_fmt)
        if fmt is None:
            formatos_sin_conversor.append(tipo_fmt)
            continue
        mask = tipo_detectado == tipo_fmt
        if tipo == 'fecha':
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt)
        else:
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt).dt.time

    df[columna] = convertidos #Convertidos , nuetra serie vacia que creamos toma nuestra 'columna' el dato que nosotros necesitamos convertir

    if tipo == 'fecha':
        df[columna] = pd.to_datetime(df[columna])

    n_convertidos = df[columna].notna().sum()
    n_total = len(df[columna])
    if formatos_sin_conversor:
        print(f"  ↳ [validar_columna_temporal] Conversión por máscara aplicada: "
              f"{n_convertidos}/{n_total} filas convertidas. "
              f"Formatos sin conversor (quedaron NaT): {formatos_sin_conversor}")
    else:
        print(f"  ↳ [validar_columna_temporal] Conversión por máscara aplicada: "
              f"{n_convertidos}/{n_total} filas convertidas correctamente.")
    print()

    return df
# =========================================================


# =========================================================
## 5) FUNCION PARA EXPLORAR DATOS DE UNA COLUMNA ESPECIFICA
## 5) FUNCION PARA EXPLORAR DATOS DE UNA COLUMNA ESPECIFICA
def explorar_columna(df, columna, tipo=None, top_n=10):
    serie = df[columna]
    n_total = len(serie)
    n_nulos = serie.isna().sum()
    n_validos = n_total - n_nulos

    print(f"\n--- Exploración columna: {columna} (dtype={serie.dtype}, tipo={tipo or 'inferido'}) ---")
    print(f"Filas totales: {n_total} | No nulos: {n_validos} ({n_validos/n_total:.1%}) | Nulos: {n_nulos} ({n_nulos/n_total:.1%})")

    if tipo in ('fecha', 'hora', 'fecha_hora') or pd.api.types.is_datetime64_any_dtype(serie):
        print(f"Rango: {serie.min()} -> {serie.max()}")
        print(f"Días/valores únicos: {serie.nunique()}")
        if tipo in ('fecha', 'fecha_hora'):
            rango_completo = pd.date_range(serie.min(), serie.max())
            faltantes = rango_completo.difference(pd.to_datetime(serie.dropna().unique()))
            print(f"Fechas ausentes en el rango: {len(faltantes)}")

    elif tipo in ('entero', 'decimal') or pd.api.types.is_numeric_dtype(serie):
        print(serie.describe())
        negativos = (serie < 0).sum()
        ceros = (serie == 0).sum()
        pct_neg = negativos / n_validos if n_validos else 0
        pct_ceros = ceros / n_validos if n_validos else 0
        print(f"Negativos: {negativos} ({pct_neg:.1%}) | Ceros: {ceros} ({pct_ceros:.1%})")

    elif tipo == 'categorico' or serie.dtype in ('string', object):
        conteo = serie.value_counts(dropna=False) #no borres con dropna, haz value_counts de la serie (la columna definida para la funcion)
        print(f"Categorías únicas: {serie.nunique()}") #numero unicos
        print(conteo.head(top_n))
        if len(conteo) > top_n:
            print(f"... ({len(conteo) - top_n} categorías más)")

    else:
        print("Tipo no reconocido para exploración -- mostrando .describe() genérico:")
        print(serie.describe())

    return None
# =========================================================


# =========================================================
## 6) FUNCION ORQUESTADORA: recorre un esquema (definido en el cuaderno,
## específico de cada tabla) y compara dtype actual vs esperado,
## aplicando el conversor que corresponda solo si hace falta.
def orquestar_transformaciones_cols(df, esquema,
                              dtype_esperado=DTYPE_ESPERADO,
                              conv_temporal=CONVERSOR_TEMPORAL,
                              conv_categorico_numerico=CONVERSOR_CATEGORICO_NUMERICO):
    for columna, tipo_esperado in esquema.items():

        if columna not in df.columns:
            print(f"[orquestador] AVISO '{columna}': no existe en el DataFrame, se omite.")
            continue

        dtype_objetivo = dtype_esperado.get(tipo_esperado)
        if dtype_objetivo is None:
            print(f"[orquestador] AVISO '{columna}': no hay dtype esperado definido para tipo '{tipo_esperado}'.")
            continue

        dtype_actual = df[columna].dtype
        if dtype_actual == dtype_objetivo:
            print(f"[orquestador] OK '{columna}': ya es {tipo_esperado} ({dtype_actual}), se omite.")
            continue

        print()
        print(f"[orquestador] CONVIERTE '{columna}': {dtype_actual} -> {tipo_esperado} (esperado {dtype_objetivo})")

        if tipo_esperado in conv_temporal:
            df = conv_temporal[tipo_esperado](df, columna)
        elif tipo_esperado in conv_categorico_numerico:
            df[columna] = conv_categorico_numerico[tipo_esperado](df[columna])
        else:
            print(f"[orquestador] AVISO '{columna}': no hay conversor definido para tipo '{tipo_esperado}'.")

    return df
# =========================================================


# =========================================================
## 7) FUNCION PARA VALIDAR Y CORREGIR NEGATIVOS, DISTINGUIENDO
## ERROR DE SIGNO PURO DE POSIBLE REVERSION (busca valor espejo
## positivo dentro del mismo grupo antes de corregir)

def corregir_negativos_con_validacion(df, columna, col_grupo, nombre_tabla=""):
    negativos = df[df[columna] < 0]  # los negativos no necesariamente están mal, podrían ser reversiones (espejo)
    idx_dudosos = [  # dudosos = negativos que SÍ tienen un valor espejo positivo, dentro del MISMO groupby_col
        idx for idx, row in negativos.iterrows()
        if len(df[(df[col_grupo] == row[col_grupo]) & (df[columna] == abs(row[columna]))]) > 0
        # len cuenta cuántas filas cumplen ambas condiciones a la vez (mismo grupo Y mismo valor absoluto);
        # si es mayor a 0, entonces existe al menos un espejo y se marca como dudoso
    ]
    idx_seguros = negativos.index.difference(idx_dudosos)  # del indice de negativos, quita los dudosos

    df.loc[idx_seguros, columna] = df.loc[idx_seguros, columna].abs()  # corrige SOLO los seguros (sin espejo)
    print(f"[{nombre_tabla}] {len(idx_seguros)} corregidos, {len(idx_dudosos)} dudosos")

    return df, df.loc[idx_dudosos]  # los dudosos los devolvemos para  inspección manual si procede


# =========================================================
## 8) FUNCION PARA NORMALIZAR CODIGOS DE EQUIPO (formato PC-EQ-01)
def normalizar_equipo_id(serie):
    """PC_EQ01 / pc-eq-1 / ' PC-EQ-01 ' -> PC-EQ-01"""
    return (serie.str.strip()
                 .str.upper()
                 .str.replace('_', '-', regex=False)
                 .str.replace(r"^([A-Z]{2})(EQ)", r'\1-\2', regex=True)
                 .str.replace(r'EQ(\d)', r'EQ-\1', regex=True))
# =========================================================


# =========================================================
## 9) FUNCION PARA DETECTAR OUTLIERS POR IQR (opcionalmente por grupo). Diagnóstico.
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
# =========================================================


# =========================================================
## 10) FUNCION PARA VERIFICAR UN ATRIBUTO DE EQUIPO CONTRA EL MAESTRO (dim_equipos)
## Depende de outliers_iqr (sección 9).
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
# =========================================================


# =========================================================
## 11) FUNCION PARA CORREGIR FECHAS DD/MM vs MM/DD MAL INTERPRETADAS (Cat 12)
## Compara col_fecha contra col_carga; ambas deben estar ya en datetime.
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
# =========================================================
