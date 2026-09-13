# Estructura de archivos — Proyecto Mineria v2

```
Mineria-simulacion v2/
├── README_v2.md
├── GUIA_DEL_PROYECTO_v2.md
├── .gitignore
│
├── data/
│   ├── data_master/        (7 archivos, ya limpios)
│   │   ├── dim_plantas.csv
│   │   ├── dim_equipos.csv
│   │   ├── dim_mineral.csv
│   │   ├── dim_categoria_gasto.csv
│   │   ├── dim_categoria_causa.csv
│   │   ├── dim_metas_mensuales.csv
│   │   └── fact_gastos.csv
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
│   ├── interim/             (vacía — destino sugerido para pasos intermedios)
│   └── processed/           (vacía — destino sugerido para fact_mantenimiento consolidado)
│
├── notebooks/
│   └── Exploracion1.ipynb
│
├── src/
│   ├── eda.py
│   ├── generar_dataset_v2.py
│   ├── aplicar_realismo_v2.py
│   ├── generar_capa_metalurgica_v2.py
│   ├── inyectar_errores_v2.py
│   └── answer_key_errores_v2.csv
│
├── assets/                  (vacía)
└── files/                   (vacía)
```

## Notas

- `answer_key_errores_v2.csv` vive en `src/`, **no** en `docs/` (esa carpeta no existe en la estructura real, aunque `GUIA_DEL_PROYECTO_v2.md` la mencione).
- `data/interim/` y `data/processed/` están vacías pero ya preparadas — destino natural para el pipeline de reconciliación de `fact_mantenimiento`, `fact_paradas` y `fact_produccion`.
- `assets/` y `files/` están vacías sin un propósito claro definido todavía.
