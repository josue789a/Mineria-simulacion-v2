# src/eda.py


##1) FUNCION PARA VERIFIZAR LIMPIEZA BASICA DE DATAFRAMES

import pandas as pd

def reporte_calidad(df, nombre_df=""): #Alias para la funcion EDA del comando de calidad
    
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
    
    # Ordenamos por % de nulos descendente (problemas más visibles primero)
    reporte = reporte.sort_values('pct_nulos', ascending=False)
    reporte = reporte.reset_index(drop=True)
    
    # Info general de metadata del dataframe 
    total_filas = len(df)
    filas_duplicadas = df.duplicated().sum()
    
    print(f"\n--- Resumen: {nombre_df or 'DataFrame'} ---")
    print(f"Total filas: {total_filas}")
    print(f"Filas duplicadas: {filas_duplicadas} ({(filas_duplicadas/total_filas*100):.2f}%)")
    print(f"Columnas: {len(df.columns)}")


 ## 2) FUNCION PARA AVERIGUAR LA NATURALEZA DE LA COLUMNA DE FECHA

import re

def detectar_fecha(valor):
    """Detecta el formato estructural de una fecha."""

    if pd.isna(valor):
        return None

    valor = str(valor).strip()

    # YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD / YYYY MM DD
    if re.fullmatch(r'\d{4}[-/. ]\d{1,2}[-/. ]\d{1,2}', valor):
        return 'YMD'

    # DD-MM-YYYY / DD/MM/YYYY / DD.MM.YYYY / DD MM YYYY
    if re.fullmatch(r'\d{1,2}[-/. ]\d{1,2}[-/. ]\d{4}', valor):
        return 'DMY'

    # YYYY-MM-DD HH:MM:SS
    if re.fullmatch(r'\d{4}[-/. ]\d{1,2}[-/. ]\d{1,2}.*', valor):
        return 'YMD_TIME'

    return 'DESCONOCIDO'