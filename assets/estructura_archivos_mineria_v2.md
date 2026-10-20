# Estructura de archivos — Proyecto Mineria v2

```
Mineria-simulacion v2/
├── README_v2.md
├── GUIA_DEL_PROYECTO_v2.md
├── .gitignore
│
├── data/
│   ├── data_master/        (9 archivos, ya limpios)
│   │   ├── dim_plantas.csv
│   │   ├── dim_equipos.csv
│   │   ├── dim_mineral.csv
│   │   ├── dim_categoria_gasto.csv
│   │   ├── dim_categoria_causa.csv
│   │   ├── dim_metas_mensuales.csv
│   │   ├── fact_gastos.csv
│   │   ├── fact_produccion_mineral.csv
│   │   └── fact_ventas.csv
│   │
│   ├── raw/                (13 archivos, sin limpiar)
│   │   ├── fact_mantenimiento_PC_raw.csv
│   │   ├── fact_mantenimiento_PN_raw.csv
│   │   ├── fact_mantenimiento_PS_raw.csv
│   │   ├── fact_paradas_PC_raw.csv
│   │   ├── fact_paradas_PN_raw.csv
│   │   ├── fact_paradas_PS_raw.csv
│   │   ├── fact_precios_mercado.csv
│   │   ├── fact_produccion_PC_legacy.csv
│   │   ├── fact_produccion_PC_nuevo.csv
│   │   ├── fact_produccion_PN_legacy.csv
│   │   ├── fact_produccion_PN_nuevo.csv
│   │   ├── fact_produccion_PS_legacy.csv
│   │   └── fact_produccion_PS_nuevo.csv
│   │
│   ├── interim/            (vacía — pasos intermedios; ignorada por .gitignore)
│   │
│   └── processed/          (4 archivos, salida del pipeline de reconciliación)
│       ├── fact_produccion.csv
│       ├── fact_paradas.csv
│       ├── fact_mantenimiento.csv
│       └── _log_exportaciones.csv
│
├── notebooks/
│   ├── Exploracion1_nuevo.ipynb     (cuaderno vigente: EDA, limpieza, carga SQL y recorrido del dashboard)
│   └── Resumen Ejecutivo.md         (resumen ejecutivo y auditoría integral, v2.1)
│
├── src/
│   ├── eda.py
│   ├── produccion.py
│   ├── carga_sql.py
│   ├── generar_dataset_v2.py
│   ├── aplicar_realismo_v2.py
│   ├── generar_capa_metalurgica_v2.py
│   ├── inyectar_errores_v2.py
│   └── answer_key_errores_v2.csv
│
├── assets/
│   ├── Pagina_01.png … Pagina_07.png    (capturas del dashboard, usadas en el notebook)
│   ├── estructura_archivos_mineria_v2.md
│   └── estructura_archivos_mineria_v2.png
│
└── files/
    ├── Dashboard Proyecto minero.pbip
    ├── Dashboard Proyecto minero.pbix
    ├── Dashboard Proyecto minero.Report/          (páginas y visuales del informe)
    ├── Dashboard Proyecto minero.SemanticModel/   (modelo tabular TMDL: tablas, relaciones, medidas DAX)
    ├── documentacion_produccion.md
    ├── documentacion_produccion.pdf
    ├── evolucion_funciones.md
    └── evolucion_validar_columna_temporal.md
```

## Notas

- El cuaderno vigente es `notebooks/Exploracion1_nuevo.ipynb`; reemplaza al antiguo `Exploracion1.ipynb`.
- `notebooks/Resumen Ejecutivo.md` documenta la auditoría final y la depuración del proyecto (v2.1).
- Las imágenes del notebook se enlazan con ruta relativa, por ejemplo `../assets/Pagina_01.png`.
- `answer_key_errores_v2.csv` vive en `src/`, **no** en `docs/` (esa carpeta no existe en la estructura real, aunque `GUIA_DEL_PROYECTO_v2.md` la mencione).
- `data/processed/` ya contiene las tres tablas reconciliadas (`fact_produccion`, `fact_paradas`, `fact_mantenimiento`) más el log de exportaciones.
- `data/data_master/` incluye `fact_produccion_mineral.csv` y `fact_ventas.csv`; `fact_precios_mercado.csv` permanece en `data/raw/`.
- `files/` contiene el proyecto de Power BI (`.pbip`/`.pbix`) y la documentación de apoyo.
- `data/interim/` y `.ipynb_checkpoints/` están en `.gitignore`.
