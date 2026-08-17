# Guía del proyecto — v2 (Multi-Planta)

Guía única, en el orden real de trabajo: primero resuelves el reto de
limpieza, después cargas tu resultado a SQL Server, y por último
construyes/ajustas el dashboard en Power BI. Reemplaza a
`INSTRUCCIONES_v2.md` y `RETO_LIMPIEZA_v2.md` como documentos separados.

---

## Parte 1 — El reto: reconciliación multi-planta (nivel difícil)

### Escenario simulado

El grupo minero opera 3 plantas concentradoras. Cada una migró de su
sistema antiguo a uno nuevo **en una fecha distinta** — no fue un cambio
coordinado del grupo, cada planta lo hizo a su propio ritmo. Tu trabajo es
escribir un pipeline en Python que reconcilie los 3 pares de archivos
(legacy/nuevo) más los archivos de paradas y mantenimiento, y produzca un
único conjunto de tablas limpias y consistentes, listas para SQL Server.

**Nadie te dice la fecha exacta en que migró cada planta — es parte del
reto descubrirlo mirando los datos** (pista: revisa dónde cambia el
esquema de columnas dentro de cada archivo, o si separaron los archivos
por planta, dónde el patrón de columnas de uno deja de aparecer).

### Archivos de entrada (crudos — carpeta `data/raw/`)

| Archivo | Qué representa |
|---|---|
| `fact_produccion_PN_legacy.csv` / `fact_produccion_PN_nuevo.csv` | Producción Planta Norte, antes/después de su migración |
| `fact_produccion_PC_legacy.csv` / `fact_produccion_PC_nuevo.csv` | Ídem, Planta Centro |
| `fact_produccion_PS_legacy.csv` / `fact_produccion_PS_nuevo.csv` | Ídem, Planta Sur |
| `fact_paradas_PN_raw.csv`, `_PC_raw.csv`, `_PS_raw.csv` | Eventos de parada por planta, sin estandarizar |
| `fact_mantenimiento_PN_raw.csv`, `_PC_raw.csv`, `_PS_raw.csv` | Órdenes de mantenimiento por planta |
| `dim_equipos.csv` | Maestro de equipos de las 3 plantas — este SÍ está limpio (carpeta `data/external/`) |

### Categorías de problemas a resolver (pistas, no respuestas)

Las primeras 8 son las mismas categorías que ya resolviste en v1/v1.5
(esquemas distintos, fechas mixtas, equipo sin estandarizar, nulos,
outliers, duplicados con y sin corrección, grano inconsistente, texto sin
estandarizar) — pero ahora aplicadas 3 veces, con parámetros distintos
por planta (equipos y meses afectados no son los mismos en las 3).

Las siguientes son **nuevas en v2**, pensadas para que este reto sea
genuinamente más difícil:

**9. Fecha de migración desconocida y distinta por planta**
No asumas que las 3 plantas migraron el mismo día, ni que migraron en un
1° de mes o en un cambio de año. Tu pipeline debería poder detectar el
punto de corte de cada planta a partir de la evidencia en los datos, no
de un valor fijo que tú adivines y hardcodees sin verificar.

**10. Cambio silencioso de unidad de medida**
En un equipo, durante un mes, dentro del archivo legacy de una planta,
los valores de toneladas vienen en una unidad distinta a la habitual —
sin ninguna columna ni marca que lo indique. La única forma de detectarlo
es que esos valores no cuadran con la capacidad nominal del equipo de una
manera sistemática y acotada a ese periodo (piensa qué factor de
conversión numérico haría que los valores "vuelvan a tener sentido" si tu
hipótesis es correcta).

**11. Contaminación cruzada entre archivos de distinta planta**
Algunas filas del archivo "nuevo" de una planta en realidad pertenecen a
OTRA planta (un error de exportación mezcló datos entre sistemas). No son
errores de formato del `equipo_id` — el prefijo de planta en esas filas
es válido, solo que no corresponde al archivo donde aparece. Vas a
necesitar cruzar contra `dim_equipos` para detectar la inconsistencia
entre "de qué planta dice venir el archivo" y "a qué planta pertenece
realmente ese equipo_id".

**12. Ambigüedad genuina de formato de fecha**
Dentro del archivo legacy de al menos una planta, hay un subconjunto de
fechas donde día y mes son ambos ≤12 — es decir, `05/03/2025` podría ser
5 de marzo o 3 de mayo, y **no hay forma de saberlo con certeza absoluta
solo mirando esa fila**. Vas a tener que decidir un criterio razonable
(¿consistencia con el resto de fechas del archivo? ¿con el rango de
`Fecha_Carga`?) y **documentar explícitamente que es un supuesto, no una
certeza** — así se maneja este tipo de ambigüedad en datos reales.

**13. Bloque de días completos faltantes (no aleatorio)**
En un equipo de cada planta, falta un tramo contiguo de varios días
seguidos — no son huecos aleatorios dispersos en el tiempo, es un bloque
compacto (simula una caída de sistema real). Antes de decidir si imputar,
interpolar o dejar como hueco documentado, piensa qué tan largo es el
tramo y si tiene sentido rellenarlo o no.

**14. Encoding roto en columnas de texto**
Algunas filas de `causa` (en paradas) y de `tipo_parada` tienen los
caracteres con tilde/ñ corrompidos (un problema clásico de leer un
archivo UTF-8 como si fuera Latin-1, o viceversa). Vas a necesitar
detectar el patrón de corrupción y decidir si es reconstruible con
certeza o si toca normalizar a una categoría aproximada.

### Cómo saber si lo resolviste bien

Al final, tu tabla de producción reconciliada debería tener, por planta,
un número de filas consistente con su rango de fechas y sus 10 equipos
(sin huecos que tú no hayas decidido dejar deliberadamente, y sin
sobrantes por duplicados sin resolver). Los totales mensuales por equipo,
dentro de cada planta, deberían verse razonables y sin saltos irreales —
ojo, ahora también deberías notar que **cada planta tiene un nivel base y
una estacionalidad distinta** (eso es correcto, no es un error tuyo, es
el diseño real de la v2 — no "corrijas" esa diferencia entre plantas, es
información válida).

### Autovalidación (usar SOLO después de intentarlo)

`answer_key_errores_v2.csv` (carpeta `docs/`) documenta los errores de
las categorías 9, 10, 11 y 13 (los que tienen un valor puntual
verificable). Las categorías 12 (ambigüedad de fecha) y 14 (encoding) no
tienen una "respuesta única" en el answer key a propósito — son casos
donde lo que se evalúa es tu criterio y cómo lo documentas, no si
adivinaste un valor exacto.

**No mires el answer key antes de intentar resolver el reto tú mismo** —
pierde todo el valor como ejercicio si lo haces. Úsalo solo para
verificar tu trabajo al final, o si llevas un buen rato atascado en una
categoría específica y quieres una pista más concreta.

### Recomendación de documentación

Lleva una bitácora de cada decisión (qué encontraste, qué criterio
usaste, por qué) — con las categorías 12 y 14 esto es aún más
importante, porque ahí no hay una única respuesta correcta y tu
razonamiento ES la evidencia de tu trabajo.

---

## Parte 2 — Una vez resuelto el reto: qué deberías tener

Al terminar la Parte 1, tu propio pipeline debería producir tu versión
limpia de `fact_produccion`, `fact_paradas` y `fact_mantenimiento`
(carpeta `data/processed/`). Súmalas a lo que ya tenías dado
(`data/external/`) para completar las 13 tablas del modelo:

- [ ] `dim_plantas.csv` *(dado)*
- [ ] `dim_equipos.csv` *(dado)*
- [ ] `dim_mineral.csv` *(dado)*
- [ ] `dim_categoria_gasto.csv` *(dado)*
- [ ] `dim_categoria_causa.csv` *(dado)*
- [ ] `dim_metas_mensuales.csv` *(dado)*
- [ ] `fact_produccion_realista.csv` ← **la produce tu pipeline** (Parte 1)
- [ ] `fact_paradas.csv` ← **la produce tu pipeline** (Parte 1)
- [ ] `fact_mantenimiento.csv` ← **la produce tu pipeline** (Parte 1)
- [ ] `fact_precios_mercado.csv` *(dado)*
- [ ] `fact_produccion_mineral.csv` *(dado, u opcionalmente tu propia versión derivada — ver nota abajo)*
- [ ] `fact_ventas.csv` *(dado, u opcionalmente tu propia versión derivada)*
- [ ] `fact_gastos.csv` *(dado — nunca derivable, viene de otro sistema)*

> **Nota sobre `fact_produccion_mineral.csv` y `fact_ventas.csv`**: si
> quieres llevar el ejercicio un paso más allá, puedes construir tu propio
> pipeline que las derive a partir de tu `fact_produccion_realista.csv`
> ya limpia (agregando a nivel planta-día y aplicando ley/recuperación
> propias). No van a coincidir número por número con las versiones dadas
> — eso es esperado, no un error — porque cada una asume su propia lógica
> de cálculo. Si lo haces, guárdalas aparte
> (`fact_produccion_mineral_propia.csv`) sin sobrescribir el original.

---

## Parte 3 — Carga a SQL Server

- **Orden de carga**: primero las tablas `dim_*` (dimensiones), después
  las `fact_*` (para que las FK tengan a qué apuntar, si defines llaves
  foráneas reales en SQL Server).
- **Longitud de campos `String`**: en v1 ya hubo un bug real de
  longitudes muy cortas en SQLAlchemy. Con `equipo_id` ahora más largo
  (`PN-EQ-01` en vez de `EQ-01`), revisa que tus columnas `String` tengan
  margen suficiente (usa `String(20)` o más, no `String(10)`).
- **`fact_precios_mercado.csv` no lleva `planta_id`** — no intentes
  forzar una columna de planta ahí, es intencional que sea una tabla
  compartida entre las 3 plantas (ver README, sección "Decisión de
  diseño importante").

---

## Parte 4 — Relaciones del modelo en Power BI

### Relaciones a crear

```
dim_plantas (planta_id) ──1:N──> dim_equipos (planta_id)
dim_plantas (planta_id) ──1:N──> fact_produccion_mineral (planta_id)
dim_plantas (planta_id) ──1:N──> fact_ventas (planta_id)
dim_plantas (planta_id) ──1:N──> fact_gastos (planta_id)
dim_plantas (planta_id) ──1:N──> dim_metas_mensuales (planta_id)
```

### Relación que NO debes crear

`fact_precios_mercado` **no se relaciona con `dim_plantas`** (no tiene esa
columna). Se relaciona solo por `fecha` con `DimCalendario` y con
`fact_produccion_mineral`/`fact_ventas` — el precio "fluye" hacia cada
planta a través de la fecha compartida, no de una FK directa a planta.

### `dim_equipos` como puente

`dim_equipos` es el punto de unión entre `fact_produccion_realista`,
`fact_paradas` y `fact_mantenimiento` — y también es el puente hacia
`dim_plantas` vía su columna `planta_id`. No necesitas relacionar
`fact_produccion_realista` directamente con `dim_plantas`; ya llega
indirectamente a través de `dim_equipos`.

### Slicer/filtro recomendado

Agrega un slicer de `dim_plantas[nombre_planta]` en cada página del
dashboard (no solo en una) — así cualquier KPI existente (OEE, MTBF,
Utilidad, etc.) puede filtrarse por planta sin rehacer ninguna medida.

---

## Parte 5 — Sugerencia de páginas nuevas para el dashboard

No es obligatorio, pero para que el esfuerzo de escalar a multi-planta se
note en el dashboard (y no solo en los datos), esta página nueva es la
que más valor agrega:

**Página "Comparación de Plantas"**
- Tabla/matriz: Planta x OEE, MTBF, MTTR, Disponibilidad, Utilidad — una
  fila por planta, para comparar de un vistazo.
- Ranking de plantas (usa la medida `Rank Planta` del README).
- Mapa o gráfico de barras: % de contribución de cada planta al total de
  toneladas / utilidad del grupo.
- Tendencia de OEE por planta en el tiempo (2024-2027), una línea por
  planta en el mismo gráfico — ahí se debería notar visualmente que PS
  mejora más rápido que PN (así se diseñó a propósito en los parámetros).
