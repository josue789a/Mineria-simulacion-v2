# src/eda.py


##1) FUNCION PARA VERIFIZAR LIMPIEZA BASICA DE DATAFRAMES
import pandas as pd


def reporte_calidad(df, nombre_df=""):
    # Métricas a nivel de columna
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
    print(f"Total filas: {total_filas}")
    print(f"Filas duplicadas: {filas_duplicadas} "
          f"({(filas_duplicadas / total_filas * 100):.2f}%)")
    print(f"Columnas: {len(df.columns)}")

    return reporte
    
    

 ## 2) FUNCION PARA AVERIGUAR LA NATURALEZA DE LA COLUMNA DE FECHA
 ## Aplica un formato al valor asignado, por ejemplo value es YYYYMMDD sera 'YMD', si por el contrario es DDMMYYY sera 'DMY', por tanto aplicarlo sobre una columna, crearia una nueva columna
import re

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

## 2) FUNCION PARA UNA VEZ AVERIGUADO QUE LOS VALORES DE FORMATO FECHO SEAN IGUALES, REALIZA LA TRASNFORMACION SIEMPRE Y CUANDO ESTE ENTRE LO DEFINIDO
def validar_fechas(df, columna):

    formatos = {
        'YMD': '%Y-%m-%d',
        'YMD_SLASH': '%Y/%m/%d',
        'DMY': '%d-%m-%Y',
        'DMY_SLASH': '%d/%m/%Y',
        'YMD_TIME': '%Y-%m-%d %H:%M:%S'
    }

    verificacion_fechas = pd.DataFrame({
        'fecha_original': df[columna],
        'tipo_fecha': df[columna].apply(clasificar_formato_fecha)
    })

    conteo_formatos = verificacion_fechas['tipo_fecha'].value_counts()
    conteo_original = df[columna].count()

    print("\nVerificación:")
    print(verificacion_fechas)

    if len(conteo_formatos) == 1 and conteo_formatos.sum() == conteo_original:

        df[columna] = pd.to_datetime(df[columna])

        print("\nValidación correcta.")
        print("Todas las fechas tienen un único formato.")
        print("Fecha convertida a datetime.")

    else:

        print("\nLa columna no pasó la validación.")
        print("\nFormatos encontrados:")
        print(conteo_formatos)

        fechas_convertidas = pd.Series(
            pd.NaT,
            index=df.index,
            dtype='datetime64[ns]'
        )

        for tipo_fecha, cantidad in conteo_formatos.items():

            formato = formatos.get(tipo_fecha)

            if formato is None:
                continue

            mask = verificacion_fechas['tipo_fecha'] == tipo_fecha

            fechas_convertidas.loc[mask] = pd.to_datetime(
                df.loc[mask, columna],
                format=formato
            )

        df[columna] = fechas_convertidas
