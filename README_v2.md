# Dataset simulado — Grupo Minero Multi-Planta (v2)

Dataset 100% sintético (semilla fija, reproducible) que simula la operación
de **3 plantas concentradoras** de un mismo grupo minero durante **4 años**
(2024-01-01 a 2027-12-31): confiabilidad de equipos, producción, y ciclo
metalúrgico-financiero completo, con precios de mercado compartidos entre
plantas. Pensado como evolución del proyecto v2 (1 planta) hacia un caso
de **consolidación multi-sitio**, el tipo de modelo que se usa en BI
corporativo real cuando una empresa opera más de una unidad de negocio.

> **Por qué existe esta versión**: escalar solo el volumen de filas
> (más años, más copias) no agrega dificultad analítica real. Agregar
> **plantas con parámetros distintos** sí lo hace — obliga a resolver
> jerarquías nuevas, consolidación, y comparación entre unidades, que es
> justamente el tipo de pregunta que hace un negocio real ("¿qué planta
> rinde mejor y por qué?").

---

## Las 3 plantas (ver `dim_plantas.csv`)

| Planta | Región | Clima | Antigüedad | Tamaño (capacidad) |
|---|---|---|---|---|
| **PN — Planta Norte** | Costa | Seco, riesgo El Niño feb-mar | Más antigua (desde 2015) | 1.0x (base) |
| **PC — Planta Centro** | Sierra Centro | Lluvias fuertes ene-mar | Intermedia (desde 2012) | 0.8x (la más pequeña) |
| **PS — Planta Sur** | Sierra Sur | Lluvias moderadas | Más nueva (desde 2019) | 1.2x (la más grande) |

Cada planta tiene el mismo catálogo de 10 equipos (mismo flujo de proceso:
Chancado → Molienda → Flotación → Espesado → Filtrado), pero con
**confiabilidad, capacidad, ley de mineral y estacionalidad propias** —
no son copias, son 3 operaciones distintas dentro del mismo grupo.

---

## Modelo de datos (13 tablas, esquema estrella en dos niveles)

```
NIVEL OPERATIVO (equipo-día / evento, por planta)
dim_plantas (3 filas)
      │
      └──< dim_equipos (30 filas: 10 equipos x 3 plantas, equipo_id con prefijo PN-/PC-/PS-)
                │
                ├──< fact_produccion_realista (43,830 filas)
                │
                └──< fact_paradas (10,527 filas)
                          │         │
                          │         └──> dim_categoria_causa (global, compartida)
                          │
                          └──< fact_mantenimiento (7,908 filas)

NIVEL METALÚRGICO-FINANCIERO (planta-día)
dim_mineral (3 filas: Cu, Zn, Ag) ─ global, compartida
fact_precios_mercado (1,461 filas) ─ GLOBAL: mismo precio de mercado para
      │                               las 3 plantas el mismo día
      │
      └──< fact_produccion_mineral (4,383 filas = 1,461 días x 3 plantas)
      └──< fact_ventas (4,383 filas)         [usa fact_precios_mercado]

dim_categoria_gasto (4 filas) ─ global, compartida
      │
      └──< fact_gastos (17,532 filas = 1,461 días x 3 plantas x 4 categorías)

dim_metas_mensuales (144 filas = 48 meses x 3 plantas)
```

**Total: ~90,200 filas** en el conjunto completo.

**Decisión de diseño importante**: `fact_precios_mercado.csv` es la única
tabla nueva de v2 que NO tiene `planta_id` — el precio del cobre en el
mercado internacional no cambia porque cambie la planta que vende. Esto
es intencional: refleja cómo funciona un mercado de commodities real, y
es el tipo de relación (tabla compartida vs. tabla por entidad) que hay
que saber modelar bien en un esquema multi-sitio.

---

## Diccionario de datos — Nivel operativo

### `dim_plantas.csv`
| Campo | Descripción |
|---|---|
| planta_id | PN / PC / PS |
| nombre_planta | Nombre descriptivo |
| region | Costa / Sierra Centro / Sierra Sur |
| tipo_clima | Descripción del patrón climático que afecta la estacionalidad |
| factor_capacidad | Multiplicador de capacidad nominal respecto al catálogo base |
| anio_inicio_operacion | Año de inicio de operaciones de la planta |

### `dim_equipos.csv`
| Campo | Descripción |
|---|---|
| equipo_id | PN-EQ-01 … PS-EQ-10 (prefijo de planta + número de catálogo) |
| planta_id | FK a dim_plantas |
| nombre_equipo, area, tipo_equipo | Igual que v1/v2 |
| capacidad_nominal_tmh | Ajustada por `factor_capacidad` de la planta |
| anio_instalacion | Ajustado ±3 años según antigüedad relativa de la planta |
| clase_confiabilidad | alta/media/baja — ajustada por planta en equipos clave (ver script) |

### `fact_produccion_realista.csv` (grano: equipo + día)
Mismas columnas que v2, con tendencia + estacionalidad + ruido con memoria
aplicados **por planta** (parámetros distintos, ver `aplicar_realismo_v2.py`).

### `fact_paradas.csv` / `fact_mantenimiento.csv`
Misma estructura que v1/v2. `equipo_id` ahora lleva el prefijo de planta,
así que se filtran/agrupan igual que antes vía `dim_equipos`.

### `dim_categoria_causa.csv`
Sin cambios respecto a v2 — es una dimensión global (Mecánico, Eléctrico,
Medioambiental, Logístico-Insumos, Externo, Planificado, Indeterminado),
aplica igual a las 3 plantas.

---

## Diccionario de datos — Nivel metalúrgico-financiero

### `fact_precios_mercado.csv` (NUEVO en v2, grano: fecha, GLOBAL)
| Campo | Descripción |
|---|---|
| fecha | Fecha diaria |
| precio_cu_usd_lb / precio_zn_usd_lb | Precio de referencia (random walk acotado) |
| precio_ag_usd_oz | Precio de referencia plata |
| tipo_cambio_pen_usd | Tipo de cambio (random walk acotado 3.65–3.85) |

### `fact_produccion_mineral.csv` (grano: fecha x planta)
Igual estructura que v2, pero con **ley base distinta por planta**
(PS tiene la mejor geología: ley Cu 0.90% base vs 0.65% de PN) y
recuperación calculada con las horas de parada de EQ-07 **de esa planta**.

### `fact_ventas.csv` (grano: fecha x planta)
Igual que v2, pero el ingreso se calcula cruzando la producción propia de
cada planta con el precio **compartido** de `fact_precios_mercado.csv`.

### `fact_gastos.csv` (grano: fecha x planta x categoría)
Igual que v2, con `MANO_OBRA_BASE` distinta por planta (refleja tamaño de
plantilla distinto según el tamaño de cada planta).

### `dim_metas_mensuales.csv` (grano: año-mes x planta)
Cada planta tiene su propia meta (promedio móvil 6 meses x 1.02),
calculada de forma independiente — no existe una meta consolidada del
grupo como dato, esa se calcula en Power BI sumando las 3.

---

## KPIs — igual que v2, más los nuevos de consolidación multi-planta

Todas las fórmulas de v2 (OEE, MTBF, MTTR, Disponibilidad, % Toneladas
Perdidas, Utilidad, % Avance vs meta, Ley promedio ponderada,
Recuperación) siguen aplicando igual, con `planta_id` como filtro/slicer
adicional en cada visual.

**Nuevos KPIs de consolidación, útiles solo con múltiples plantas:**

**Ranking de plantas por OEE**
```
Rank Planta = RANKX(ALL(dim_plantas), [OEE Promedio Planta], , DESC)
```

**Utilidad consolidada del grupo**
```
Utilidad Grupo = SUMX(dim_plantas, [Utilidad Planta])
```
(la misma medida de Utilidad de v2, pero sin filtrar por planta, o
sumada explícitamente sobre las 3)

**% Contribución de cada planta al total de toneladas**
```
% Contribución = DIVIDE([Toneladas Planta], CALCULATE([Toneladas Total], ALL(dim_plantas)))
```

---

## Reproducibilidad — scripts y semillas (v2)

| Script | Genera | Semilla |
|---|---|---|
| `generar_dataset_v2.py` | dim_plantas, dim_equipos, fact_produccion (base), fact_paradas, fact_mantenimiento | SEED=100 |
| `aplicar_realismo_v2.py` | fact_produccion_realista (tendencia+estacionalidad+ruido, por planta) | SEED=121 |
| `generar_capa_metalurgica_v2.py` | dim_mineral, fact_precios_mercado, fact_produccion_mineral, fact_ventas, dim_categoria_gasto, fact_gastos, dim_metas_mensuales | SEED=133 |
| `inyectar_errores_v2.py` | Versión "sucia" de producción/paradas/mantenimiento por planta, con migración escalonada y 14 categorías de error (ver `RETO_LIMPIEZA_v2.md`) | SEED=77 |

`dim_categoria_causa.csv` se reutiliza tal cual de v2 (es una dimensión
global que no depende de plantas).

> **Actualización**: a diferencia de lo planteado inicialmente, v2 **sí
> tiene su propio ejercicio de datos sucios** — más difícil que el de
> v1/v2, con migración escalonada (cada planta migra en una fecha
> distinta y oculta) y 6 categorías de error nuevas (cambio silencioso de
> unidad, contaminación cruzada entre plantas, ambigüedad genuina de
> fecha, bloques de días faltantes, encoding roto). Ver
> `RETO_LIMPIEZA_v2.md` para el enunciado completo.
>
> **A propósito, esta vez no existe un script de solución
> (`reconciliar_produccion_v2.py`)** — el objetivo es que el propio autor
> del proyecto lo resuelva, para que sea una habilidad genuinamente
> demostrada y no solo documentada. `answer_key_errores_v2.csv` existe
> únicamente para autovalidación posterior, no como guía.

---

## Ver también

- `INSTRUCCIONES_v2.md` — orden de ejecución de los scripts y guía de
  carga a SQL Server / Power BI, incluidas las relaciones nuevas que hay
  que definir para que el modelo multi-planta funcione bien.
- `README_v1.5.md` y `RETO_LIMPIEZA.md` — documentación de la versión de
  1 planta / 2 años, con el ejercicio de limpieza de datos original.

---

## Historial de versiones

**v1**: 4 tablas, 1 planta, 2 años, producción sin tendencia/estacionalidad.

**v1.5**: 11 tablas, 1 planta, 2 años. Agrega tendencia+estacionalidad+ruido,
capa metalúrgico-financiera completa, categorización de causas de parada.
Documentado en `README_v1.5.md`.

**v2 (actual)**: 13 tablas, **3 plantas**, **4 años**, ~90,200 filas.
Agrega jerarquía multi-sitio con parámetros diferenciados por planta
(confiabilidad, capacidad, ley de mineral, estacionalidad climática),
precios de mercado compartidos entre plantas, KPIs de consolidación
grupal, y un reto de limpieza de datos más difícil (migración
escalonada por planta, 14 categorías de error, ver `RETO_LIMPIEZA_v2.md`).

**Pendiente para v3**: carga real a SQL Server con las 3 plantas, diseño
del dashboard de comparación entre plantas, y resolución del reto de
limpieza v2 (pipeline de reconciliación propio, aún sin construir a
propósito).
