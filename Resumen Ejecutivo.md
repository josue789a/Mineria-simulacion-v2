# RESUMEN EJECUTIVO Y AUDITORÍA INTEGRAL: PROYECTO MINERÍA V2.1

**Proyecto Oficial Activo:** `v12. INFORME CORRECTO.pbip`  
**Ubicación de Entrega:** Carpeta `2.1`  
**Estado:** Auditado, depurado, optimizado y verificado  

---

## RESULTADOS EN BREVE

El proyecto consolida la producción, las paradas, el mantenimiento y los costos de tres plantas concentradoras (Norte, Centro y Sur) en un único modelo analítico y un dashboard de 6 páginas. Sobre datos simulados del periodo 2024-2027, el análisis arroja cinco conclusiones:

- **Planta Sur es la más eficiente.** Su OEE es de 83,7 %, frente a 82,6 % de Centro y 82,5 % de Norte. La ventaja proviene de la disponibilidad de sus equipos (94,9 % frente a ~93,7 %).
- **Las fallas cuestan S/ 110 millones**, el 29 % del gasto operativo del grupo. Las paradas correctivas concentran el 72 % del costo de paradas y el 88 % del gasto en repuestos.
- **Cinco equipos generan el 29 % de ese costo.** Son los Molinos SAG y de Bolas 1 de Norte y Centro y la Faja Transportadora 3 de Norte, todos de confiabilidad baja (MTBF ~107 h).
- **El problema es interno.** Seis causas (mantenimiento programado y cinco tipos de falla) explican el 93 % del costo de paradas; el clima, la energía y los insumos pesan cerca del 2 %.
- **El mantenimiento es mayoritariamente reactivo.** El 70 % de las órdenes y el 73 % de las horas-hombre se destinan a correcciones.

| Planta | OEE | Disponibilidad | Toneladas (millones) | % del grupo | MTBF (h) | MTTR (h) | Costo de no confiabilidad (S/ millones) | Costo por tonelada (S/) |
|---|---|---|---|---|---|---|---|---|
| Norte (PN) | 82,5 % | 93,6 % | 114,9 | 33,1 % | 163 | 7,8 | 39,7 | 0,35 |
| Centro (PC) | 82,6 % | 93,8 % | 92,1 | 26,5 % | 171 | 7,9 | 38,6 | 0,42 |
| Sur (PS) | 83,7 % | 94,9 % | 140,0 | 40,4 % | 207 | 7,0 | 32,1 | 0,23 |
| **Grupo** | **82,9 %** | **94,1 %** | **347,0** | 100 % | — | — | **110,4** | **0,32** |

---

## 1. VISIÓN GENERAL Y ALCANCE DE LA VERSIÓN 2.1

El proyecto de analítica para minería evolucionó de una visión mono-planta (V1) a una plataforma integral multi-planta (V2 / V2.1) que consolida tres operaciones mineras simultáneas: **Planta Centro (PC)**, **Planta Sur (PS)** y **Planta Norte (PN)**.

La solución integra el ciclo de vida completo de datos:
1. **Pipeline de Ingesta y Limpieza:** Reconciliación de datos legados y modernos, corrección de granularidad de turnos a diario, imputación de tonelajes fuera de especificación y validación estricta de integridad referencial.
2. **Modelo Relacional en SQL Server (`mineria_v2`):** Esquema estrella de 13 tablas con claves primarias y foráneas enforced.
3. **Semántica Analítica en Power BI:** Modelo tabular TMDL con 80 medidas DAX optimizadas tras una exhaustiva depuración de 34 medidas huérfanas.
4. **Reporte Ejecutivo y Operativo:** 6 páginas analíticas y 1 tooltip interactivo de alta densidad informativa.

---

## 2. ARQUITECTURA DEL MODELO DE DATOS

El modelo de datos implementa un esquema estrella en tres niveles unidos por la dimensión central `dim_plantas`:

<!-- Pendiente: reemplazar esta imagen por una captura de la vista de modelo de Power BI (la actual es el árbol de carpetas) -->
![Executive Overview](../assets/estructura_archivos_mineria_v2.png)

1. **Nivel Operativo (Grano Equipo-Día / Evento):**
   - Hechos: `fact_produccion`, `fact_paradas`, `fact_mantenimiento`.
   - Dimensiones: `dim_equipos` (conecta con `dim_plantas` por `planta_id`), `dim_categoria_causa`, `DimCalendario`.
2. **Nivel Corporativo / Financiero (Grano Planta-Día):**
   - Hechos: `fact_produccion_mineral`, `fact_ventas`, `fact_gastos`, `dim_metas_mensuales`.
   - Dimensiones: `dim_plantas`, `dim_mineral`, `dim_categoria_gasto`.
3. **Nivel de Mercado (Grano Diario Global):**
   - Hechos: `fact_precios_mercado` (Cu, Zn, Ag y tipo de cambio USD/PEN), compartida por las tres plantas y sin `planta_id` por diseño.

---

## 3. RECORRIDO DEL DASHBOARD POWER BI Y CAPTURAS

El reporte cuenta con 6 páginas principales y 1 tooltip interactivo.

### 3.1 Página 1: Executive Overview (Multi-Planta)
* **Objetivo:** Visión gerencial de alto nivel para comparar el rendimiento económico y operativo de las tres operaciones mineras.
* **Componentes:** 3 gráficos de barras comparativas (OEE, Toneladas y Utilidad por planta), 5 tarjetas gerenciales (OEE del grupo, Toneladas totales, Utilidad acumulada, Margen global y Costo de no confiabilidad) y una matriz de benchmarking integral.
* **Captura:**
![Executive Overview](../assets/Pagina_01.png)

---

### 3.2 Página 2: Eficiencia Operacional & OEE
* **Objetivo:** Monitoreo profundo de los factores del OEE (Disponibilidad, Rendimiento y Calidad) por planta y equipo.
* **Componentes:** 6 gauges interactivos, 9 tarjetas de métricas operativas, 3 treemaps de distribución por equipo y curvas temporales de producción.
* **Captura:**
![Eficiencia Operacional y OEE](../assets/Pagina_02.png)

---

### 3.3 Página 3: Finanzas & Precios de Mercado
* **Objetivo:** Vinculación directa entre volumen producido, cotizaciones internacionales de metales (Cu, Zn, Ag) y resultado financiero.
* **Componentes:** 5 tarjetas de cotizaciones e ingresos, desglose de facturación por mineral, líneas de tendencia de precios internacionales y treemap de costos operativos.
* **Captura:**
![Finanzas y Precios de Mercado](../assets/Pagina_03.png)

---

### 3.4 Página 4: Análisis de Paradas & Pérdidas
* **Objetivo:** Identificación de causas raíz de detención y pérdidas operativas por equipo y área.
* **Componentes:** Gráfico circular por tipo de parada (Correctiva, Operativa, Preventiva), ranking Pareto de causas principales y consumo de repuestos.
* **Captura:**
![Analisis de Paradas y Perdidas](../assets/Pagina_04.png)

---

### 3.5 Tooltip: TT_repuestos_eqp (Página 4 Tooltip)
* **Objetivo:** Desglose emergente por equipo al pasar el cursor sobre los gráficos de paradas y fallas.
* **Componentes:** Donut chart interactivo (320x240 px) que muestra el gasto discriminado por tipo de repuesto.
* **Captura:**
![TT_repuestos_eqp](../assets/Pagina_07.png)

---

### 3.6 Página 5: Mantenimiento & Horas Hombre (HH)
* **Objetivo:** Gestión de eficiencia del área de mantenimiento, ratio preventivo vs correctivo y costos evitables.
* **Componentes:** 16 tarjetas de KPIs de HH, donut charts de tipología de órdenes, gráfico de área de evolución temporal acumulada (YTD) y ranking por especialidad.
* **Captura:**
![Mantenimiento y HH](../assets/Pagina_05.png)

---

### 3.7 Página 6: Matriz de Confiabilidad de Equipos
* **Objetivo:** Priorización estratégica de intervención de activos críticos mediante índices de criticidad y MTBF.
* **Componentes:** Scatter plot cuadrante (Índice de Riesgo vs MTBF, con tamaño proporcional al costo evitable), gauges de confiabilidad, análisis Pareto y tabla de decisión de activos.
* **Captura:**
![Matriz de Confiabilidad Equipos](../assets/Pagina_06.png)

---

## 4. HALLAZGOS CLAVE

### 4.1 Desempeño por planta
Planta Sur obtiene el mayor OEE del grupo (83,7 %). Las tres plantas tienen el mismo rendimiento (90 %) y la misma calidad (98 %); la diferencia está solo en la disponibilidad, que en Sur es de 94,9 % y en las otras dos, de 93,6 % y 93,8 %. Sur procesa además el 40,4 % de las toneladas del grupo.

### 4.2 Confiabilidad
Sur registra 1.609 fallas, contra 1.920 en Centro y 2.017 en Norte, con un tiempo medio entre fallas de 207 h (171 h y 163 h respectivamente) y una reparación promedio de 7,0 h (7,9 h y 7,8 h). Su costo de no confiabilidad por tonelada es S/ 0,23, frente a S/ 0,42 en Centro y S/ 0,35 en Norte.

### 4.2.1 Costo de las paradas
El costo total de no confiabilidad (paradas + repuestos) asciende a S/ 110,4 millones. Por tipo de parada:

| Tipo | Paradas | % de las horas | % del costo |
|---|---|---|---|
| Correctiva | 5.546 | 68 % | 72 % |
| Preventiva | 2.362 | 25 % | 26 % |
| Operativa | 2.619 | 7 % | 2 % |

### 4.3 Activos críticos
Cinco de los 30 equipos concentran el 29 % del costo de no confiabilidad (entre S/ 5,9 y S/ 6,6 millones cada uno): Molino SAG y Molino de Bolas 1 en Norte y Centro, y Faja Transportadora 3 en Norte. Todos pertenecen a la clase de confiabilidad "baja" y su MTBF es de ~107 h, frente a ~294 h en los equipos de clase "alta". Por área, Molienda (40 %) y Chancado (38 %) suman el 78 % del costo.

### 4.4 Causas de parada
Seis causas explican el 93 % del costo de paradas: mantenimiento programado (25 %) y cinco tipos de falla (mecánica, atoro de mineral, rotura de faja, eléctrica y lubricación; ~14 % cada una). Las causas externas (clima, corte de energía, falta de insumos o de mineral) suman cerca del 2 %. El 4,7 % del costo corresponde a paradas con causa "Indeterminado".

### 4.5 Mantenimiento
Las órdenes correctivas representan el 70 % del total, el 73 % de las horas-hombre (50.630 de 69.301 h) y el 88 % del gasto en repuestos. Hay 0,43 órdenes preventivas por cada correctiva.

---

## 5. RECOMENDACIONES

1. **Plan de confiabilidad para los 5 activos críticos** (Molinos SAG y Bolas 1 de Norte y Centro; Faja 3 de Norte), por ser los de mayor costo y menor MTBF.
2. **Transferir las prácticas de Planta Sur** a Norte y Centro, con una meta de disponibilidad cercana al 95 %.
3. **Aumentar la proporción de mantenimiento preventivo**, hoy menor a una orden por cada dos correctivas.
4. **Reducir las paradas sin causa registrada** (4,7 % del costo) para completar el análisis de causa raíz.

---

## 6. CALIDAD DE DATOS: RECONCILIACIÓN MULTI-PLANTA

Los archivos de origen presentaban 14 categorías de problemas, con una migración de sistema en fechas distintas por planta. El pipeline en Python (`src/produccion.py`, `src/eda.py`) los resuelve de forma documentada:

| Problema | Tratamiento |
|---|---|
| Esquemas distintos (legacy y nuevo) | Unificación al esquema nuevo, por planta |
| Código de equipo sin estandarizar | Normalización a `PC-EQ-01` y validación contra `dim_equipos` |
| Filas de otra planta en el archivo | Detección cruzada con `dim_equipos` y eliminación |
| Cambio silencioso de unidad (toneladas cortas) | Detección por eficiencia imposible (> 100 %) y conversión |
| Capacidad nominal multiplicada por 10 | Corrección con el valor maestro de `dim_equipos` |
| Fechas con día y mes ambiguos | Corrección con la fecha de carga; **supuesto documentado** |
| Duplicados con corrección posterior | Se conserva la fila con carga válida; los grupos ambiguos se reportan |
| Grano por turno | Colapso a grano diario, propagando nulos |
| Nulos | Imputación por tasa histórica del equipo y por horas disponibles |
| Toneladas negativas | Corrección de signo, con revisión de casos con espejo |
| Días faltantes por caída de sistema | Se dejan como hueco documentado, sin imputar |

**Resultado de cierre:** 43.819 filas de producción frente a 43.830 esperadas (3 plantas × 10 equipos × 1.461 días). Las 11 diferencias corresponden a un bloque de días consecutivos en un equipo por planta, y no hay duplicados. Paradas pasó de 10.736 a 10.527 filas y mantenimiento de 7.986 a 7.908.

---

## 7. MEDIDAS DAX CLAVE

```dax
-- OEE = Disponibilidad x Rendimiento x Calidad
Disponibilidad =
DIVIDE(
    SUM(fact_produccion[horas_operativas]),
    SUM(fact_produccion[horas_operativas]) + SUM(fact_produccion[horas_parada]),
    0
)

Rendimiento =
VAR CapacidadReal = SUM(fact_produccion[toneladas_procesadas])
VAR CapacidadTeorica =
    SUMX(
        fact_produccion,
        fact_produccion[horas_operativas] * RELATED(dim_equipos[capacidad_nominal_tmh])
    )
RETURN DIVIDE(CapacidadReal, CapacidadTeorica, 0)

Calidad =
1 - DIVIDE(
    SUM(fact_produccion[toneladas_fuera_especificacion]),
    SUM(fact_produccion[toneladas_procesadas]),
    0
)

OEE = [Disponibilidad] * [Rendimiento] * [Calidad]

-- Comparación entre plantas
OEE Grupo = CALCULATE([OEE], ALLSELECTED(dim_plantas))
OEE vs Grupo (pp) = ([OEE] - [OEE Grupo]) * 100
Toneladas Planta % Grupo =
DIVIDE([Toneladas Planta], CALCULATE([Toneladas Planta], ALLSELECTED(dim_plantas)), 0)

-- Confiabilidad y costo
MTBF_Hr =
VAR HorasOperativas = SUM(fact_produccion[horas_operativas])
VAR NumFallas =
    CALCULATE(
        COUNTROWS(fact_paradas),
        fact_paradas[tipo_parada] = "CORRECTIVA",
        REMOVEFILTERS(fact_paradas[causa])
    )
RETURN DIVIDE(HorasOperativas, NumFallas, 0)

Costo Total No Confiabilidad =
SUM(fact_paradas[costo_estimado_soles]) + SUM(fact_mantenimiento[costo_repuestos_soles])

Utilidad = [Ingreso Total PEN] - [Gastos Operativos PEN] - [Costo Total No Confiabilidad]

-- Priorización de activos (ventana móvil de 3 meses)
@Indice Riesgo Falla =
VAR UltimaFecha = MAX(DimCalendario[Fecha])
VAR AnioRef = YEAR(UltimaFecha)
VAR HH = CALCULATE(SUM(fact_mantenimiento[horas_hombre]),
    DATESINPERIOD(DimCalendario[Fecha], UltimaFecha, -3, MONTH), REMOVEFILTERS(fact_paradas[causa]))
VAR Fallas = CALCULATE(COUNTROWS(fact_paradas), fact_paradas[tipo_parada] = "CORRECTIVA",
    DATESINPERIOD(DimCalendario[Fecha], UltimaFecha, -3, MONTH), REMOVEFILTERS(fact_paradas[causa]))
VAR Rep = CALCULATE(SUM(fact_mantenimiento[costo_repuestos_soles]),
    DATESINPERIOD(DimCalendario[Fecha], UltimaFecha, -3, MONTH), REMOVEFILTERS(fact_paradas[causa]))
VAR Antiguedad = MAX(0, AnioRef - MAX(dim_equipos[anio_instalacion]))
RETURN (HH * 0.3) + (Fallas * 50) + (Rep * 0.002) + (Antiguedad * 8)
```

---

## 8. LIMITACIONES

- **Datos sintéticos:** generados con semilla fija; demuestran el método y no reflejan una operación real.
- **Margen de utilidad (~97 %):** los ingresos simulados son muy altos respecto a los gastos; la utilidad es útil para comparar plantas, no como resultado financiero realista.
- **Rendimiento constante (90 %):** los datos limpios no muestran estacionalidad por lluvias ni tendencia anual, por lo que el OEE es estable en el tiempo.
- **Metas mensuales:** se calculan a partir del propio historial (promedio de 6 meses × 1,02), de modo que cada planta las cumple en ~50 % de los meses; no son metas comerciales externas.
- **Fechas ambiguas:** su corrección se basa en un criterio razonable (fecha de carga), no en una certeza.

---

## 9. COMPETENCIAS DEMOSTRADAS

| Etapa | Qué demuestra |
|---|---|
| Python (pandas) | Pipeline modular y parametrizado de reconciliación, con validación de cierre y bitácora de decisiones |
| SQL Server | Esquema estrella de 13 tablas con integridad referencial |
| Power BI y DAX | Modelo semántico con 80 medidas, comparación entre plantas e indicadores de confiabilidad |
| Diseño de dashboard | 6 páginas orientadas a decisión, con tooltip de detalle |
