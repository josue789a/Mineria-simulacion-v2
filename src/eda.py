# src/eda.py

import pandas as pd


def reporte_calidad(df, nombre_df=""): #Alias para la funcion EDA del comando de calidad
    
    # Métricas a nivel de columna
    reporte = pd.DataFrame({
        'dataframe': nombre_df,
        'columna': df.columns,
        'tipo_dato': df.dtypes.values,
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
    
    return reporte