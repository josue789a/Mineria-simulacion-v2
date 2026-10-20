# RESUMEN EJECUTIVO Y AUDITORÍA INTEGRAL: PROYECTO MINERÍA V2.1

**Proyecto Oficial Activo:** `v12. INFORME CORRECTO.pbip`  
**Ubicación de Entrega:** Carpeta `2.1`  
**Estado:** Auditado, depurado, optimizado y verificado  

---

## 1. VISIÓN GENERAL Y ALCANCE DE LA VERSIÓN 2.1

El proyecto de analítica para minería evolucionó de una visión mono-planta (V1) a una plataforma integral multi-planta (V2 / V2.1) que consolida tres operaciones mineras simultáneas: **Planta Centro (PC)**, **Planta Sur (PS)** y **Planta Norte (PN)**.

La solución integra el ciclo de vida completo de datos:
1. **Pipeline de Ingesta y Limpieza:** Reconciliación de datos legados y modernos, corrección de granularidad de turnos a diario, imputación de tonelajes fuera de especificación y validación estricta de integridad referencial.
2. **Modelo Relacional en SQL Server (`mineria_v2`):** Esquema estrella de 13 tablas con claves primarias y foráneas enforced.
3. **Semántica Analítica en Power BI:** Modelo tabular TMDL con 80 medidas DAX optimizadas tras una exhaustiva depuración de 34 medidas huérfanas.
4. **Reporte Ejecutivo y Operativo:** 6 páginas analíticas y 1 tooltip interactivo de alta densidad informativa.

---

## 2. AUDITORÍA FINAL Y OPTIMIZACIÓN (LO QUE SE REALIZÓ EN V2.1)

### 2.1 Diagnóstico de Partida y Reducción de Espacio
El proyecto presentaba múltiples iteraciones históricas, respaldos redundantes y parches intermedios.
- **Tamaño original:** ~84 MB
- **Tamaño depurado (.zip):** ~16 MB (**Reducción del 81%**)

### 2.2 Componentes y Residuos Eliminados
1. **`_archivo_iteraciones/` (Completa):** Se eliminaron las versiones intermedias V9, V10, v11, backups de rescate y scripts de automatización `.ps1` y `.py`.
2. **`AUDITORIAS/` (Completa):** Se suprimieron más de 20 paquetes zip de entregas previas y comprobaciones temporales.
3. **Parches Sueltos:** Se retiraron `fix_cardvisual_details.py`, `set_pareto_line_color.py`, `LEEME_PARCHE_PAGINA5.txt` y `recargar_fact_gastos_sql.py`. El archivo consolidado `fact_gastos.csv` permanece intacto en `data_master`.
4. **Residuos y Cachés Locales:** Eliminación de carpetas `__pycache__`, accesos directos `.lnk` y el archivo `cache.abf` (que se regenera limpio al refrescar contra SQL Server).
5. **Notebooks Antiguos:** La carpeta `dashboard resumen/` desactualizada fue reemplazada por la versión consolidada y documentada en esta carpeta `2.1`.

### 2.3 Depuración de Medidas DAX (De 114 a 80 Activas)
Se eliminaron **34 medidas DAX huérfanas** que no participaban en ningún visual, filtro, tabla ni cálculo dependiente:
- **Metalurgia sin visual (11 medidas):** `Ley Cu Cabeza %`, `Ley Cu Concentrado %`, `Ley Ag Cabeza oz/t`, `Ley Zn Cabeza %`, `Recuperacion Cu %`, `Concentrado Cu t`, `Fino Cu Contenido t`, `Fino Cu Recuperado t`, `Meta Toneladas Planta % Avance`, etc.
- **Rankings y comparativos de planta (8 medidas):** `Rank Planta OEE`, `Rank Planta MTBF`, `Rank Planta MTTR`, `Rank Planta Utilidad`, `% del grupo`, `OEE vs Grupo (pp)`, `Toneladas Planta % Grupo`.
- **Restos de pruebas y cálculos temporales (15 medidas):** `Chequeo_Fechas_Huerfanas`, `OEE_LY_*`, `Tendencia_DatesYTD_OEE`, `pareto4_% del_total`, `pareto5_Clasificacion_ABC`, medidas vacías temporales (`Medida`, `Medida 2`).

> **Respaldo de Seguridad:** Todas las fórmulas DAX completas de las 34 medidas eliminadas se encuentran preservadas en:
> `medidas_dax_eliminadas_backup.tmdl`

### 2.4 Matriz de Comprobaciones Técnicas
| Aspecto Verificado | Resultado | Detalle |
| :--- | :---: | :--- |
| **Medidas Huérfanas** | **0** | De 34 medidas inactivas a 0. Las 80 medidas restantes están 100% en uso. |
| **Integridad de Visuales** | **100% OK** | Las **291 referencias** entre visuales y campos del modelo resuelven con 0 errores. |
| **Estructura TMDL** | **Válida** | Se preservaron saltos de línea, lineageTags, particiones y metadatos nativos. |
| **Páginas del Reporte** | **7 Páginas** | Confirmadas en `pageOrder`. Eliminados placeholders rojos de parches anteriores. |

---

## 3. ARQUITECTURA DEL MODELO DE DATOS

El modelo de datos implementa un esquema estrella en dos niveles unidos por la dimensión central `dim_plantas`:

![Modelo Estrella v2](capturas_dashboard/Modelo_estrella_v2.png)

1. **Nivel Operativo (Grano Equipo-Día / Evento):**
   - Hechos: `fact_produccion`, `fact_paradas`, `fact_mantenimiento`.
   - Dimensiones: `dim_equipos` (conecta con `dim_plantas` por `planta_id`), `DimCalendario`.
2. **Nivel Corporativo / Financiero (Grano Planta-Día):**
   - Hechos: `fact_produccion_mineral`, `fact_ventas`, `fact_gastos`.
   - Dimensiones: `dim_plantas`, `dim_minerales`, `dim_categoria_gastos`.
3. **Nivel de Mercado (Grano Diario Global):**
   - Hechos: `fact_precios_mercado` (Cu, Zn, Ag y tipo de cambio USD/PEN).

---

## 4. RECORRIDO DEL DASHBOARD POWER BI Y CAPTURAS

El reporte cuenta con 6 páginas principales y 1 tooltip interactivo.

### 4.1 Página 1: Executive Overview (Multi-Planta)
* **Objetivo:** Visión gerencial de alto nivel para comparar el rendimiento económico y operativo de las tres operaciones mineras.
* **Componentes:** 3 gráficos de barras comparativas (OEE, Toneladas y Utilidad por planta), 5 tarjetas gerenciales (OEE del grupo, Toneladas totales, Utilidad acumulada, Margen global y Costo de no confiabilidad) y una matriz de benchmarking integral.
* **Captura:**
![Executive Overview](capturas_dashboard/V12_page-0001.jpg)

---

### 4.2 Página 2: Eficiencia Operacional & OEE
* **Objetivo:** Monitoreo profundo de los factores del OEE (Disponibilidad, Rendimiento y Calidad) por planta y equipo.
* **Componentes:** 6 gauges interactivos, 9 tarjetas de métricas operativas, 3 treemaps de distribución por equipo y curvas temporales de producción.
* **Captura:**
![Eficiencia Operacional y OEE](capturas_dashboard/V12_page-0002.jpg)

---

### 4.3 Página 3: Finanzas & Precios de Mercado
* **Objetivo:** Vinculación directa entre volumen producido, cotizaciones internacionales de metales (Cu, Zn, Ag) y resultado financiero.
* **Componentes:** 5 tarjetas de cotizaciones e ingresos, desglose de facturación por mineral, líneas de tendencia de precios internacionales y treemap de costos operativos.
* **Captura:**
![Finanzas y Precios de Mercado](capturas_dashboard/V12_page-0003.jpg)

---

### 4.4 Página 4: Análisis de Paradas & Pérdidas
* **Objetivo:** Identificación de causas raíz de detención y pérdidas operativas por equipo y área.
* **Componentes:** Gráfico circular por tipo de parada (Correctiva, Operativa, Preventiva), ranking Pareto de causas principales y consumo de repuestos.
* **Captura:**
![Analisis de Paradas y Perdidas](capturas_dashboard/V12_page-0004.jpg)

---

### 4.5 Tooltip: TT_repuestos_eqp (Página 4 Tooltip)
* **Objetivo:** Desglose emergente por equipo al pasar el cursor sobre los gráficos de paradas y fallas.
* **Componentes:** Donut chart interactivo (320x240 px) que muestra el gasto discriminado por tipo de repuesto.
* **Captura:**
![TT_repuestos_eqp](capturas_dashboard/V12_page-0007.jpg)

---

### 4.6 Página 5: Mantenimiento & Horas Hombre (HH)
* **Objetivo:** Gestión de eficiencia del área de mantenimiento, ratio preventivo vs correctivo y costos evitables.
* **Componentes:** 16 tarjetas de KPIs de HH, donut charts de tipología de órdenes, gráfico de área de evolución temporal acumulada (YTD) y ranking por especialidad.
* **Captura:**
![Mantenimiento y HH](capturas_dashboard/V12_page-0005.jpg)

---

### 4.7 Página 6: Matriz de Confiabilidad de Equipos
* **Objetivo:** Priorización estratégica de intervención de activos críticos mediante índices de criticidad y MTBF.
* **Componentes:** Scatter plot cuadrante (Índice de Riesgo vs MTBF, con tamaño proporcional al costo evitable), gauges de confiabilidad, análisis Pareto y tabla de decisión de activos.
* **Captura:**
![Matriz de Confiabilidad Equipos](capturas_dashboard/V12_page-0006.jpg)

---

## 5. FORMULACIONES DAX CRÍTICAS ADAPTADAS A MULTI-PLANTA

### 5.1 Utilidad Económica Ponderada
```dax
Ingreso Total PEN = SUM(fact_ventas[ingreso_total_pen])

Gastos Operativos PEN = SUM(fact_gastos[monto_soles])

Utilidad = [Ingreso Total PEN] - [Gastos Operativos PEN] - [Costo Total No Confiabilidad]

Margen Utilidad % = DIVIDE([Utilidad], [Ingreso Total PEN], 0)
```

### 5.2 Rendimiento con Ponderación Real por Capacidad de Equipo
```dax
Rendimiento = 
VAR CapacidadReal = SUM(fact_produccion[toneladas_procesadas])
VAR CapacidadTeorica = 
    SUMX(
        fact_produccion,
        fact_produccion[horas_operativas] * RELATED(dim_equipos[capacidad_nominal_tmh])
    )
RETURN DIVIDE(CapacidadReal, CapacidadTeorica, 0)
```

### 5.3 Costo Promedio de Área Segmentado por Planta
```dax
Costo Promedio Area = 
CALCULATE(
    AVERAGEX(VALUES(dim_equipos[equipo_id]), [Costo Total No Confiabilidad]),
    ALLEXCEPT(dim_equipos, dim_equipos[area], dim_equipos[planta_id])
)
```

### 5.4 Índice de Riesgo de Falla con Ventana Móvil
```dax
@Indice Riesgo Falla = 
VAR UltimaFecha = MAX(DimCalendario[Fecha])
VAR AnioRef = YEAR(UltimaFecha)
VAR HH = CALCULATE(
    SUM(fact_mantenimiento[horas_hombre]),
    DATESINPERIOD(DimCalendario[Fecha], UltimaFecha, -3, MONTH),
    REMOVEFILTERS(fact_paradas[causa])
)
VAR Fallas = CALCULATE(
    COUNTROWS(fact_paradas),
    fact_paradas[tipo_parada] = "CORRECTIVA",
    DATESINPERIOD(DimCalendario[Fecha], UltimaFecha, -3, MONTH),
    REMOVEFILTERS(fact_paradas[causa])
)
VAR Rep = CALCULATE(
    SUM(fact_mantenimiento[costo_repuestos_soles]),
    DATESINPERIOD(DimCalendario[Fecha], UltimaFecha, -3, MONTH),
    REMOVEFILTERS(fact_paradas[causa])
)
VAR Antiguedad = MAX(0, AnioRef - MAX(dim_equipos[anio_instalacion]))
RETURN (HH * 0.3) + (Fallas * 50) + (Rep * 0.002) + (Antiguedad * 8)
```

---

## 6. INSTRUCCIONES DE PUESTA EN MARCHA PARA EL USUARIO

1. **Apertura y Refresco en Power BI Desktop:**
   - Abrir el archivo `v12. INFORME CORRECTO.pbip`.
   - En la pestaña Inicio, presionar **Refrescar**.
   - Power BI se conectará a la base de datos SQL Server (`mineria_v2`) y recreará automáticamente el archivo de almacenamiento local `cache.abf` con datos limpios y coherentes.
2. **Página de Inicio Recomendada:**
   - Al abrir, el proyecto se encuentra situado en `TT_repuestos_eqp` (página de tooltip).
   - Para presentaciones o publicación en Power BI Service, situarse en la **Página 1: Executive Overview** y guardar el reporte.
3. **Estructura de la Carpeta 2.1:**
   - `Mineria_v2-AntiGravity_LIMPIO.zip`: Repositorio limpio completo del proyecto (16 MB).
   - `medidas_dax_eliminadas_backup.tmdl`: Respaldo textual de las 34 medidas DAX eliminadas.
   - `Exploracion_Dashboard_Resumen_v2.1.ipynb`: Cuaderno Jupyter completo y actualizado con todo el pipeline y la sección 10 de auditoría.
   - `capturas_dashboard/`: Todas las imágenes y capturas en alta resolución del dashboard y modelo estrella.
   - `RESUMEN_EJECUTIVO_MINERIA_V2.1.md`: Este informe ejecutivo completo.
