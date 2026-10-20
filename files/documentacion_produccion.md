# Pipeline de reconciliacion de produccion (src/produccion.py)

Documento de apoyo del proyecto Mineria-simulacion v2. Explica que hace el orquestador, en que orden y por que, y que parte de lo hecho a mano en el cuaderno reproduce. Alcance verificado: **planta PC**. PS y PN estan pendientes de correr con este pipeline; no se afirma nada de ellas aqui.


## 1. Donde vive cada funcion

Regla: lo generico, que sirve a mas de una tabla, vive en `eda.py` y se importa. Lo que solo tiene sentido para produccion vive en `produccion.py`. Ninguna funcion esta definida en los dos archivos.

| Archivo | Funciones |
|---|---|
| eda.py (generico) | `normalizar_equipo_id`, `outliers_iqr`, `verificar_capacidad_vs_maestro`, `corregir_fechas_ambiguas`, `corregir_negativos_con_validacion`, `resolver_duplicados`, `validar_columna_temporal` |
| produccion.py (propio) | `imputar_por_tasa_equipo`, `imputar_horas_parada`, `resolver_duplicados_legacy`, `corregir_unidad_toneladas_cortas`, `detectar_huecos`, `detectar_contaminacion_cruzada`, `eliminar_contaminacion_cruzada`, `colapsar_grano_turno`, `consolidar_legacy_nuevo`, `validar_cierre` |


## 2. Flujo general

`procesar_planta` recibe los dos archivos crudos de una planta (legacy y nuevo) y `dim_equipos`. Corre `procesar_legacy` y `procesar_nuevo` por separado, los une con `consolidar_legacy_nuevo` al esquema de nuevo, y `validar_cierre` compara el calendario completo (fecha x equipo) contra lo obtenido. La diferencia son los huecos, que se contrastan con `huecos_esperados`.


## 3. procesar_legacy: pasos y orden

| # | Paso | Funcion | Por que en ese lugar |
|---|---|---|---|
| 1 | Normalizar equipo y avisar de codigos no existentes en dim_equipos | `normalizar_equipo_id` | Todo lo demas agrupa por equipo; con codigos sucios cada equipo se parte en varios grupos |
| 2 | Negativos en Ton_Producidas (los dudosos, con espejo positivo, quedan para revision) | `corregir_negativos_con_validacion` | Antes de la unidad, que usa la eficiencia |
| 3 | Capacidad x10 vs maestro (Cat 10) | `verificar_capacidad_vs_maestro` (usa `outliers_iqr`) | La unidad divide por la capacidad: con el x10 sin corregir el calculo sale mal |
| 4 | Nulos: Ton_Rechazo por tasa del equipo; Horas_Parada = 24 - Horas_Trab | `imputar_por_tasa_equipo`, `imputar_horas_parada` | Ver seccion 9, punto debil |
| 5 | Fechas a datetime y swap dia/mes (Cat 12) | `validar_columna_temporal`, `corregir_fechas_ambiguas` | Antes de duplicados: el swap resuelve colisiones falsas de clave |
| 6 | Duplicados: se conserva la fila con Fecha_Carga - Fecha = 1 | `resolver_duplicados_legacy` | Necesita la fecha ya corregida. No frena si un grupo es ambiguo: solo lo reporta |
| 7 | Cambio silencioso de unidad (Cat 10) | `corregir_unidad_toneladas_cortas` | Despues de capacidad y duplicados |
| 8 | Huecos: solo reporte, no se imputa (Cat 13) | `detectar_huecos` | Al final; una fecha mal leida parece un hueco |


## 4. procesar_nuevo: pasos y orden

| # | Paso | Funcion | Por que en ese lugar |
|---|---|---|---|
| 1 | Quitar filas de otra planta (Cat 11) | `eliminar_contaminacion_cruzada` | Cruza equipo_id con dim_equipos; son filas con prefijo de planta valido pero ajeno al archivo |
| 2 | Quitar duplicados exactos | `df.drop_duplicates()` | Antes del colapso: un turno repetido se sumaria dos veces |
| 3 | Colapsar grano turno a grano diario | `colapsar_grano_turno` | Un nulo en un turno deja el dia nulo (propagar_nulos=True) |
| 4 | Nulos de toneladas_fuera_especificacion por tasa del equipo | `imputar_por_tasa_equipo` | Despues del colapso, a nivel dia |
| 5 | Duplicados por clave (fecha, equipo_id) | `resolver_duplicados` | Hoy es una comprobacion: debe dar 0 exactos y 0 conflictivos |


## 5. Orden obligatorio vs flexible

- **Obligatorio:** equipo antes de todo lo que agrupa por equipo; fechas antes de duplicados; fechas antes de huecos; capacidad antes de unidad; duplicados exactos antes del colapso de turno.
- **Flexible:** negativos (cualquier punto antes de unidad), contaminacion (primero es lo mas limpio) y la comprobacion final de duplicados por clave.
- El orden actual es el que reproduce lo hecho a mano en PC. Es valido, pero no es el unico posible.


## 6. Numeros y umbrales: de donde salen

Se separa lo que es logica o definicion de lo que es un valor escogido y sin calibrar.

| Valor | Donde | Origen |
|---|---|---|
| 0.907185 | `corregir_unidad_toneladas_cortas` | **Definicion:** 1 tonelada corta = 0.907185 toneladas metricas. Se aplica multiplicando para volver a metricas |
| Eficiencia > 1.0 | idem (`umbral_certeza`) | **Logica:** eficiencia = ton / (horas x capacidad). Procesar mas que la capacidad nominal en el dia es evidencia directa de problema. Tras corregir en PC quedan 0 filas > 1.0 |
| Techo 0.99 | idem (`techo`) | **Valor escogido:** solo para listar candidatas. En PC hubo 56 filas > 0.99 antes de corregir y 53 despues (celdas 103 y 104): esas 53 estan entre 0.99 y 1.0 y no se distinguen de filas normales, por eso no se corrigen |
| deltas (-2,-1,0,1) | `PARAMS_DEFAULT` | **Mixto:** lo normal es Fecha_Carga - Fecha = 1 (~99.6% segun el comentario de la celda 88 del cuaderno). El rango de tolerancia es un valor escogido, sin calibrar |
| 1.5 x IQR | `outliers_iqr` | **Convencion** estandar para marcar valores atipicos: mas alla de 1.5 veces la distancia entre los cuartiles. No calibrado a estos datos |
| 24 horas | `imputar_horas_parada` | **Logica:** el dia tiene 24 horas. La relacion Horas_Parada = 24 - Horas_Trab esta verificada solo en PC |


## 7. Que NO hace el orquestador

- **No descubre.** No sabe cual equipo tiene el x10, cual tiene toneladas cortas ni que dias faltan. Aplica reglas generales y luego se verifica que coincidan con lo hallado a mano.
- **No detecta la fecha de migracion (Cat 9).** Recibe legacy y nuevo ya separados.
- **No toma los juicios.** Que Cat 13 quede como hueco, que Cat 12 sea un supuesto y que las filas limitrofes de unidad no se corrijan son decisiones del autor escritas en el codigo.


## 8. Verificacion en PC (regresion contra el trabajo manual)

Se corrio `procesar_planta` sobre los crudos de PC y se comparo contra `prodPC_final` hecho a mano.

- Mismas 14607 claves (fecha, equipo_id) en ambas tablas.
- Horas operativas, horas de parada y toneladas procesadas: 0 diferencias. Todo legacy: 0 diferencias.
- toneladas_fuera_especificacion: 36 diferencias, todas en nuevo. 10 caen en dias de turno con un turno nulo (el manual sumaba solo los turnos con dato y subestimaba; el orquestador imputa por tasa). Las otras 26 son de 0.1 a 0.5 t, por la mediana de la tasa de imputacion.
- Hallazgos que corrigio la regresion: faltaba el paso de unidad en `procesar_legacy` y los duplicados exactos de turno se sumaban dos veces al colapsar (6 dias con mas de 24 horas).


## 9. Limitaciones conocidas y mejoras posibles

- **PC-EQ-05, 2025-04-16:** la imputacion por tasa (94.3) queda por debajo de la suma parcial de los turnos observados (112.3). El valor real es al menos 112.3. Afecta 1 fila.
- **Imputar Ton_Rechazo antes de duplicados y unidad (paso 4 de legacy):** la tasa del equipo se calcula con filas que luego se descartan o se corrigen. En PC no cambia el resultado frente al manual; es el punto mas debil del orden. Mejora posible: imputar despues de la unidad (no probada).
- **Imputar fuera_especificacion antes de colapsar,** a nivel de turno, garantizaria que la suma del dia sea mayor o igual a lo observado (no probada).
- **Filas limitrofes de unidad:** segun el cierre de PC, 2 filas limitrofes de la Cat 10 no se corrigen por ser indistinguibles de filas normales.
- **Paso 6 de legacy** no frena si un grupo de duplicados no tiene exactamente una fila valida: revisar `grupos_ambiguos` en el log.
- **`procesar_nuevo`** recibe `params` pero ya no lo usa; `propagar_nulos` queda en su valor por defecto (True).
