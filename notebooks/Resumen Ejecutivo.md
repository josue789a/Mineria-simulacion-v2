# RESUMEN EJECUTIVO Y AUDITORÍA INTEGRAL: PROYECTO MINERÍA V2.1


## 1. VISIÓN GENERAL Y ALCANCE DE LA VERSIÓN 2.1

El proyecto de analítica para minería evolucionó de una visión mono-planta (V1) a una plataforma integral multi-planta en la v2 que consolida tres operaciones mineras simultáneas: **Planta Centro (PC)**, **Planta Sur (PS)** y **Planta Norte (PN)**.

La solución integra el ciclo de vida completo de datos:
1. **Pipeline de Ingesta y Limpieza:** Reconciliación de datos legados y modernos, corrección de granularidad de turnos a diario, imputación de tonelajes fuera de especificación y validación estricta de integridad referencial.
2. **Modelo Relacional en SQL Server (`mineria_v2`):** Esquema estrella de 13 tablas con claves primarias y foráneas enforced.
3. **Semántica Analítica en Power BI:** Modelo tabular TMDL con 80 medidas DAX optimizadas tras una exhaustiva depuración de 34 medidas huérfanas.
4. **Reporte Ejecutivo y Operativo:** 6 páginas analíticas y 1 tooltip interactivo de alta densidad informativa.

---

## 2. ARQUITECTURA DEL MODELO DE DATOS

El modelo de datos implementa un esquema estrella en dos niveles unidos por la dimensión central `dim_plantas`:

![Executive Overview](../assets/estructura_archivos_mineria_v2.png)

1. **Nivel Operativo (Grano Equipo-Día / Evento):**
   - Hechos: `fact_produccion`, `fact_paradas`, `fact_mantenimiento`.
   - Dimensiones: `dim_equipos` (conecta con `dim_plantas` por `planta_id`), `DimCalendario`.
2. **Nivel Corporativo / Financiero (Grano Planta-Día):**
   - Hechos: `fact_produccion_mineral`, `fact_ventas`, `fact_gastos`.
   - Dimensiones: `dim_plantas`, `dim_minerales`, `dim_categoria_gastos`.
3. **Nivel de Mercado (Grano Diario Global):**
   - Hechos: `fact_precios_mercado` (Cu, Zn, Ag y tipo de cambio USD/PEN).

---

## 3. RECORRIDO DEL DASHBOARD POWER BI Y CAPTURAS

El reporte cuenta con 6 páginas principales y 1 tooltip interactivo.

### 4.1 Página 1: Executive Overview (Multi-Planta)
* **Objetivo:** Visión gerencial de alto nivel para comparar el rendimiento económico y operativo de las tres operaciones mineras.
* **Componentes:** 3 gráficos de barras comparativas (OEE, Toneladas y Utilidad por planta), 5 tarjetas gerenciales (OEE del grupo, Toneladas totales, Utilidad acumulada, Margen global y Costo de no confiabilidad) y una matriz de benchmarking integral.
* **Captura:**

![Executive Overview](../assets/Pagina_01.png)
---

### 4.2 Página 2: Eficiencia Operacional & OEE
* **Objetivo:** Monitoreo profundo de los factores del OEE (Disponibilidad, Rendimiento y Calidad) por planta y equipo.
* **Componentes:** 6 gauges interactivos, 9 tarjetas de métricas operativas, 3 treemaps de distribución por equipo y curvas temporales de producción.
* **Captura:**

![Executive Overview](../assets/Pagina_02.png)
---

### 4.3 Página 3: Finanzas & Precios de Mercado
* **Objetivo:** Vinculación directa entre volumen producido, cotizaciones internacionales de metales (Cu, Zn, Ag) y resultado financiero.
* **Componentes:** 5 tarjetas de cotizaciones e ingresos, desglose de facturación por mineral, líneas de tendencia de precios internacionales y treemap de costos operativos.
* **Captura:**

![Executive Overview](../assets/Pagina_03.png)
---

### 4.4 Página 4: Análisis de Paradas & Pérdidas
* **Objetivo:** Identificación de causas raíz de detención y pérdidas operativas por equipo y área.
* **Componentes:** Gráfico circular por tipo de parada (Correctiva, Operativa, Preventiva), ranking Pareto de causas principales y consumo de repuestos.
* **Captura:**

![Executive Overview](../assets/Pagina_04.png)
---

### 4.5 Tooltip: TT_repuestos_eqp (Página 4 Tooltip)
* **Objetivo:** Desglose emergente por equipo al pasar el cursor sobre los gráficos de paradas y fallas.
* **Componentes:** Donut chart interactivo (320x240 px) que muestra el gasto discriminado por tipo de repuesto.
* **Captura:**

![Executive Overview](../assets/Pagina_07.png)
---

### 4.6 Página 5: Mantenimiento & Horas Hombre (HH)
* **Objetivo:** Gestión de eficiencia del área de mantenimiento, ratio preventivo vs correctivo y costos evitables.
* **Componentes:** 16 tarjetas de KPIs de HH, donut charts de tipología de órdenes, gráfico de área de evolución temporal acumulada (YTD) y ranking por especialidad.
* **Captura:**

![Executive Overview](../assets/Pagina_05.png)
---

### 4.7 Página 6: Matriz de Confiabilidad de Equipos
* **Objetivo:** Priorización estratégica de intervención de activos críticos mediante índices de criticidad y MTBF.
* **Componentes:** Scatter plot cuadrante (Índice de Riesgo vs MTBF, con tamaño proporcional al costo evitable), gauges de confiabilidad, análisis Pareto y tabla de decisión de activos.
* **Captura:**

![Executive Overview](../assets/Pagina_06.png)
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

