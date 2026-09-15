# src/eda.py

import re
import pandas as pd

# =========================================================
# Diccionarios GLOBALES — visibles para cualquier función del notebook
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
# =========================================================


# =========================================================
## 1) FUNCION PARA VERIFICAR CALIDAD BASICA DE DATAFRAMES
def reporte_calidad(df, nombre_df=""):
    # Métricas de calidad a nivel de columna del dataframe
    reporte = pd.DataFrame({
        'columna': df.columns,
        'tipo_dato': df.dtypes.values,
        'duplicados': df.duplicated().mean(),
        'no_nulos': df.count().values,
        'nulos': df.isnull().sum().values,
        'pct_nulos': (df.isnull().mean() * 100).round(2),
        'unicos': df.nunique().values,
    })

    # Ordenamos por % de nulos descendente
    reporte = reporte.sort_values('pct_nulos', ascending=False)
    reporte = reporte.reset_index(drop=True)

    # Info general del DataFrame
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
## Clasificadores puros: reciben un valor, lo limpian, y devuelven una
## etiqueta de formato, o 'DESCONOCIDO' si no calza con nada.
def clasificar_formato_fecha(valor):

    if pd.isna(valor):  # 1) si ES nulo: NO se limpia, se corta aquí mismo y retorna None
        return None

    valor = str(valor).strip()  # 2) si NO es nulo, limpieza básica ANTES de comparar y string para que re no reciba algo que no sea string y falle

    # re.fullmatch(patron, valor) Devuelve un objeto "match" (que en un IF se
    # evalúa como TRUE) si todo el string del regex(patron) de principio a
    # fin coincide con el valor. Devuelve None (→ False en el if) si no
    # coincide completo.
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

    return 'DESCONOCIDO'  # si no calzó con ningún patrón anterior, queda marcado como
                           # DESCONOCIDO — esa etiqueta la usa luego validar_columna_temporal
                           # para decidir qué hacer con esas filas (las deja como NaT)
# =========================================================


# =========================================================
def clasificar_formato_hora(valor):

    if pd.isna(valor):  # 1) revisa si este valor puntual es nulo
        return None

    valor = str(valor).strip()  # 2) si NO es nulo, limpieza básica ANTES de comparar y string para que re no reciba algo que no sea string y falle

    if re.fullmatch(r'\d{2}:\d{2}', valor):          # formato hora:minutos
        return 'HH_MM'

    if re.fullmatch(r'\d{2}:\d{2}:\d{2}', valor):    # formato hora:minutos:segundos
        return 'HH_MM_SS'

    return 'DESCONOCIDO'
# =========================================================


# =========================================================
## 3) FUNCION PARA RESOLVER DUPLICADOS, ASIGNANDO UN SUBSET DE COMPONENTES DEL EVENTO, Y COLUMNAS CON EL GRANO UNICO ESPERADO
def resolver_duplicados(df, subset_clave, columnas_desempate=None, nombre_tabla="",
                          columnas_grano_esperado=None):
    # subset_clave: obligatorio, define el evento.
    # columnas_desempate y columnas_grano_esperado: opcionales.

    # 1) Validar el grano (opcional) — cada columna listada debe tener un
    #    solo valor único dentro de cada evento.
    if columnas_grano_esperado:
        chequeo = df.groupby(subset_clave)[columnas_grano_esperado].nunique()
        rotos = chequeo[(chequeo > 1).any(axis=1)]  # basta 1 columna rota (no única) para marcar la fila

        if len(rotos) > 0:
            print(f"⚠️ [{nombre_tabla}] ALERTA: {len(rotos)} '{subset_clave}' tienen "
                  f"múltiples valores en {columnas_grano_esperado}. La clave NO es segura tal cual.")
            return df, pd.DataFrame(), rotos

    # 2) Detectar todas las instancias de eventos repetidos
    mask_dup = df.duplicated(subset=subset_clave, keep=False)
    dup = df[mask_dup]

    # 3) Separar copia idéntica (exacto) de mismo evento con dato distinto (conflicto)
    exactos = dup[dup.duplicated(keep=False)]
    conflictivos = dup.drop(exactos.index)

    print(f"[{nombre_tabla}] duplicados exactos: {len(exactos)} filas | "
          f"con conflicto real: {len(conflictivos)} filas")

    # 4) Borrar copias idénticas siempre; conflictivos quedan intactos si existen
    df_limpio = df.drop_duplicates(subset=None if not conflictivos.empty else subset_clave,
                                    keep='first')

    # 5) Resolver conflictos con la regla de desempate (opcional)
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
    """
    tipo: 'fecha' o 'hora' — decide qué clasificador y qué diccionario de
    formatos usar. La lógica de validación/conversión es idéntica para
    ambos casos, solo cambia qué función de clasificación se invoca.
    """
    clasificador = clasificar_formato_fecha if tipo == 'fecha' else clasificar_formato_hora
    formatos = FORMATOS_FECHA if tipo == 'fecha' else FORMATOS_HORA

    # guard de nulos centralizado: solo clasificamos lo que no es nulo
    no_nulos = df[columna].notna()
    # Si la columna recibe re.fullmatch y el valor no es string, falla —
    # por eso nos aseguramos de que sea string antes de aplicar la función
    valores_str = df.loc[no_nulos, columna].astype(str).str.strip()

    tipo_detectado = pd.Series(index=df.index, dtype='object')
    tipo_detectado.loc[no_nulos] = valores_str.apply(clasificador)

    conteo_formatos = tipo_detectado.value_counts()  # qué formatos aparecieron y cuántas veces
    print(f"\nVerificación de '{columna}' (tipo={tipo}):")
    print(conteo_formatos)

    # True si esta columna (sea fecha u hora) trajo un único formato
    # consistente en todos sus valores no nulos — independiente de si
    # 'tipo' es fecha u hora, eso solo decide QUÉ clasificador se usó.
    formato_unico = len(conteo_formatos) == 1 and conteo_formatos.index[0] != 'DESCONOCIDO'

    if formato_unico:
        # camino simple: un solo pd.to_datetime(..., format=fmt) para toda la columna
        fmt = formatos[conteo_formatos.index[0]]
        if tipo == 'fecha':
            df[columna] = pd.to_datetime(df[columna], format=fmt)
        else:
            df[columna] = pd.to_datetime(df[columna], format=fmt).dt.time
        print("Validación correcta. Formato único. Columna convertida.")
        return df

    # camino "formatos mezclados": cada subconjunto se convierte con SU propio formato, usando una máscara — nunca se fuerza un formato
    # equivocado sobre el resto de los datos.
    print("\nLa columna NO pasó la validación de formato único.")
    print("Formatos encontrados:", dict(conteo_formatos))

    convertidos = pd.Series(pd.NaT, index=df.index, dtype='object')
    for tipo_fmt, _ in conteo_formatos.items():
        fmt = formatos.get(tipo_fmt)
        if fmt is None:
            continue  # DESCONOCIDO: queda como NaT(Not a Time), hay que revisarlo aparte
        mask = tipo_detectado == tipo_fmt
        if tipo == 'fecha':
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt)
        else:
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt).dt.time

    df[columna] = convertidos
    return df
# =========================================================

# =========================================================
## 5) FUNCION PARA EXPLORAR DATOS DE UNA COLUMNA ESPECIFICA
def explorar_columna(df, columna, tipo=None, top_n=10):
    """
    Explora el CONTENIDO de una columna (no su salud) -- distribución
    de valores, rango, outliers evidentes. Complementa a reporte_calidad,
    no la reemplaza.

    tipo: si se pasa (ej. desde esquema_paradas), adapta la exploración
          al tipo de negocio esperado; si no se pasa, infiere del dtype actual.
    """
    serie = df[columna]
    print(f"\n--- Exploración: {columna} (dtype={serie.dtype}, tipo={tipo or 'inferido'}) ---")

    if tipo in ('fecha', 'hora', 'fecha_hora') or pd.api.types.is_datetime64_any_dtype(serie):
        print(f"Rango: {serie.min()} -> {serie.max()}")
        print(f"Días/valores únicos: {serie.nunique()}")
        # huecos en fechas -- útil para detectar el bloque de días faltantes
        if tipo in ('fecha', 'fecha_hora'):
            rango_completo = pd.date_range(serie.min(), serie.max())
            faltantes = rango_completo.difference(pd.to_datetime(serie.dropna().unique()))
            print(f"Fechas ausentes en el rango: {len(faltantes)}")

    elif tipo in ('entero', 'decimal') or pd.api.types.is_numeric_dtype(serie):
        print(serie.describe())
        negativos = (serie < 0).sum()
        ceros = (serie == 0).sum()
        print(f"Negativos: {negativos} | Ceros: {ceros}")

    elif tipo == 'categorico' or serie.dtype in ('string', object):
        conteo = serie.value_counts(dropna=False)
        print(f"Categorías únicas: {serie.nunique()}")
        print(conteo.head(top_n))
        if len(conteo) > top_n:
            print(f"... ({len(conteo) - top_n} categorías más)")

    else:
        print("Tipo no reconocido para exploración -- mostrando .describe() genérico:")
        print(serie.describe())

    return None