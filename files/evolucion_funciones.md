# Evolución de funciones — `eda.py`

Documento único de trazabilidad para todas las funciones reutilizables
del proyecto. Cada función conserva su documentación completa (sin
recortes ni resúmenes respecto a su versión original) — este archivo
solo las reorganiza bajo un mismo índice, en vez de tener un `.md`
suelto por función.

## Índice

- [Función: `validar_columna_temporal` y `aplicar_transformaciones`](#función-validar_columna_temporal-y-aplicar_transformaciones)
- [Función: `explorar_columna`](#función-explorar_columna)

---

## Función: `validar_columna_temporal` y `aplicar_transformaciones`

Apunte de trazabilidad: qué cambió en cada versión, por qué, y el código
completo de cada paso para poder comparar. Cada bloque marca los cambios
con comentarios `# <<< NUEVO` / `# <<< CAMBIO` para que sean fáciles de
ubicar dentro del código completo.

---

### V0 — Origen: `validar_fechas` (en `eda.py`)

Función original, solo para fechas (no reusable para horas). No
diferenciaba de qué función venía cada print, y el camino de "formatos
mezclados" no confirmaba el resultado final de la conversión.

```python
def validar_fechas(df, columna):

    formatos = {
        'YMD': '%Y-%m-%d',
        'YMD_SLASH': '%Y/%m/%d',
        'DMY': '%d-%m-%Y',
        'DMY_SLASH': '%d/%m/%Y',
        'YMD_TIME': '%Y-%m-%d %H:%M:%S'
    }

    verificacion_fechas = pd.DataFrame({
        'fecha_original': df[columna],
        'tipo_fecha': df[columna].apply(clasificar_formato_fecha)
    })

    conteo_formatos = verificacion_fechas['tipo_fecha'].value_counts()
    conteo_original = df[columna].count()

    print("\nVerificación:")
    print(verificacion_fechas)

    if len(conteo_formatos) == 1 and conteo_formatos.sum() == conteo_original:

        df[columna] = pd.to_datetime(df[columna])

        print("\nValidación correcta.")
        print("Todas las fechas tienen un único formato.")
        print("Fecha convertida a datetime.")

    else:

        print("\nLa columna no pasó la validación.")
        print("\nFormatos encontrados:")
        print(conteo_formatos)

        fechas_convertidas = pd.Series(
            pd.NaT,
            index=df.index,
            dtype='datetime64[ns]'
        )

        for tipo_fecha, cantidad in conteo_formatos.items():

            formato = formatos.get(tipo_fecha)

            if formato is None:
                continue

            mask = verificacion_fechas['tipo_fecha'] == tipo_fecha

            fechas_convertidas.loc[mask] = pd.to_datetime(
                df.loc[mask, columna],
                format=formato
            )

        df[columna] = fechas_convertidas
        # <<< SIN CAMBIOS: nunca imprime un mensaje de cierre confirmando
        #     el resultado de esta rama (limitación heredada hasta V3)
```

**Limitaciones detectadas:**
- Solo sirve para `fecha`; para `hora` habría que duplicar toda la función.
- El diccionario `formatos` está *hardcodeado dentro* de la función (no
  reusable, no configurable desde afuera).
- La rama de "formatos mezclados" termina en silencio — convierte y no
  dice si funcionó.

---

### V1 — Generalización: nace `validar_columna_temporal(df, columna, tipo)`

**Cambio principal:** se agrega el parámetro `tipo` (`'fecha'` u
`'hora'`) para que la MISMA función sirva para ambos casos, eligiendo
dinámicamente qué clasificador y qué diccionario de formatos usar. Se
mueven `FORMATOS_FECHA`/`FORMATOS_HORA` fuera de la función (a nivel de
módulo) para que sean reusables. También se centraliza el manejo de
nulos antes de clasificar.

```python
def validar_columna_temporal(df, columna, tipo='fecha'):
    """
    tipo: 'fecha' o 'hora' — decide qué clasificador y qué diccionario de
    formatos usar. La lógica de validación/conversión es idéntica para
    ambos casos, solo cambia qué función de clasificación se invoca.
    """
    # <<< NUEVO: selección dinámica de herramientas según 'tipo' —
    #     esto es lo que reemplaza tener una función separada por cada caso
    clasificador = clasificar_formato_fecha if tipo == 'fecha' else clasificar_formato_hora
    formatos = FORMATOS_FECHA if tipo == 'fecha' else FORMATOS_HORA

    # <<< NUEVO: guard de nulos centralizado — en V0 no existía este paso
    #     explícito, dependía de que apply() tolerara NaN silenciosamente
    no_nulos = df[columna].notna()
    valores_str = df.loc[no_nulos, columna].astype(str).str.strip()

    tipo_detectado = pd.Series(index=df.index, dtype='object')
    tipo_detectado.loc[no_nulos] = valores_str.apply(clasificador)

    conteo_formatos = tipo_detectado.value_counts()
    print(f"\nVerificación de '{columna}' (tipo={tipo}):")
    print(conteo_formatos)

    formato_unico = len(conteo_formatos) == 1 and conteo_formatos.index[0] != 'DESCONOCIDO'

    if formato_unico:
        fmt = formatos[conteo_formatos.index[0]]
        # <<< NUEVO: bifurcación fecha vs hora en la conversión final
        if tipo == 'fecha':
            df[columna] = pd.to_datetime(df[columna], format=fmt)
        else:
            df[columna] = pd.to_datetime(df[columna], format=fmt).dt.time
        print("Validación correcta. Formato único. Columna convertida.")
        return df

    print("\nLa columna NO pasó la validación de formato único.")
    print("Formatos encontrados:", dict(conteo_formatos))

    convertidos = pd.Series(pd.NaT, index=df.index, dtype='object')
    for tipo_fmt, _ in conteo_formatos.items():
        fmt = formatos.get(tipo_fmt)
        if fmt is None:
            continue
        mask = tipo_detectado == tipo_fmt
        if tipo == 'fecha':
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt)
        else:
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt).dt.time

    df[columna] = convertidos
    # <<< SIN CAMBIOS respecto a V0: sigue sin mensaje de cierre aquí
    return df
```

**Se mantiene la misma limitación de V0:** el camino "formatos
mezclados" convierte pero no confirma el resultado con un print.

---

### V2 — Prefijos: diferenciar quién imprime qué (`[orquestador]` vs `↳`)

**Cambio principal:** en este punto la función ya se usa dentro de
`aplicar_transformaciones` (el "orquestador" que recorre el contrato de
columnas). Al mezclar ambas funciones en un mismo log, no se podía
distinguir a simple vista qué línea venía de cuál. Se agregan prefijos y
sangría/flecha para marcar la jerarquía de llamada.

**En `aplicar_transformaciones` (el orquestador):**
```python
def aplicar_transformaciones(df, esquema,
                              dtype_esperado=DTYPE_ESPERADO,
                              conv_columna=CONVERSORES_COLUMNA,
                              conv_simples=CONVERSORES_SIMPLES):
    for columna, tipo_esperado in esquema.items():

        if columna not in df.columns:
            # <<< CAMBIO: antes "AVISO  '{columna}'...", ahora con prefijo
            print(f"[orquestador] AVISO '{columna}': no existe en el DataFrame, se omite.")
            continue

        dtype_objetivo = dtype_esperado.get(tipo_esperado)
        if dtype_objetivo is None:
            print(f"[orquestador] AVISO '{columna}': no hay dtype esperado definido para tipo '{tipo_esperado}'.")
            continue

        dtype_actual = df[columna].dtype
        if dtype_actual == dtype_objetivo:
            # <<< CAMBIO: antes "OK     '{columna}'...", ahora con prefijo
            print(f"[orquestador] OK '{columna}': ya es {tipo_esperado} ({dtype_actual}), se omite.")
            continue

        # <<< CAMBIO: antes "CONVIERTE '{columna}'...", ahora con prefijo
        print(f"[orquestador] CONVIERTE '{columna}': {dtype_actual} -> {tipo_esperado} (esperado {dtype_objetivo})")

        if tipo_esperado in conv_columna:
            df = conv_columna[tipo_esperado](df, columna)
        elif tipo_esperado in conv_simples:
            df[columna] = conv_simples[tipo_esperado](df[columna])
        else:
            print(f"[orquestador] AVISO '{columna}': no hay conversor definido para tipo '{tipo_esperado}'.")

    return df
```

**En `validar_columna_temporal` (la función invocada):**
```python
    conteo_formatos = tipo_detectado.value_counts()
    # <<< CAMBIO: antes "\nVerificación de...", ahora con sangría + flecha
    #     que indica "esto cuelga de la línea [orquestador] de arriba"
    print(f"  ↳ [validar_columna_temporal] Verificación de '{columna}' (tipo={tipo}):")
    print(conteo_formatos)

    formato_unico = len(conteo_formatos) == 1 and conteo_formatos.index[0] != 'DESCONOCIDO'

    if formato_unico:
        fmt = formatos[conteo_formatos.index[0]]
        if tipo == 'fecha':
            df[columna] = pd.to_datetime(df[columna], format=fmt)
        else:
            df[columna] = pd.to_datetime(df[columna], format=fmt).dt.time
        # <<< CAMBIO: prefijo agregado
        print(f"  ↳ [validar_columna_temporal] Validación correcta. Formato único. Columna convertida.")
        return df

    # <<< CAMBIO: prefijos agregados a ambas líneas
    print(f"  ↳ [validar_columna_temporal] La columna NO pasó la validación de formato único.")
    print(f"  ↳ [validar_columna_temporal] Formatos encontrados: {dict(conteo_formatos)}")

    convertidos = pd.Series(pd.NaT, index=df.index, dtype='object')
    for tipo_fmt, _ in conteo_formatos.items():
        fmt = formatos.get(tipo_fmt)
        if fmt is None:
            continue
        mask = tipo_detectado == tipo_fmt
        if tipo == 'fecha':
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt)
        else:
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt).dt.time

    df[columna] = convertidos
    return df
```

**Resultado en consola en este punto:**
```
[orquestador] CONVIERTE 'fecha': str -> fecha (esperado datetime64[us])
  ↳ [validar_columna_temporal] Verificación de 'fecha' (tipo=fecha):
YMD          2246
DMY_SLASH    1404
  ↳ [validar_columna_temporal] La columna NO pasó la validación de formato único.
  ↳ [validar_columna_temporal] Formatos encontrados: {'YMD': 2246, 'DMY_SLASH': 1404}
[orquestador] OK 'hora_inicio_aprox': ya es hora (object), se omite.
```
Ya se distingue el origen de cada línea, pero todo sigue pegado sin aire
visual, y el camino "formatos mezclados" sigue sin cerrar con un mensaje
de confirmación.

---

### V3 — Espaciado: dar aire al output

**Cambio principal:** se agregan `print()` (línea en blanco) antes de
cada evento real (`CONVIERTE`, y alrededor de los sub-bloques de
`validar_columna_temporal`). Las líneas `OK` — que no disparan ningún
sub-bloque — se dejan compactas entre sí a propósito, porque son ruido
de bajo interés.

**En `aplicar_transformaciones`:**
```python
        dtype_actual = df[columna].dtype
        if dtype_actual == dtype_objetivo:
            print(f"[orquestador] OK '{columna}': ya es {tipo_esperado} ({dtype_actual}), se omite.")
            continue

        # <<< NUEVO: línea en blanco antes de cada conversión real,
        #     separa visualmente este bloque del anterior
        print()
        print(f"[orquestador] CONVIERTE '{columna}': {dtype_actual} -> {tipo_esperado} (esperado {dtype_objetivo})")
```

**En `validar_columna_temporal`:**
```python
    conteo_formatos = tipo_detectado.value_counts()
    print(f"  ↳ [validar_columna_temporal] Verificación de '{columna}' (tipo={tipo}):")
    print(conteo_formatos)
    print()  # <<< NUEVO: respiro antes del veredicto

    formato_unico = len(conteo_formatos) == 1 and conteo_formatos.index[0] != 'DESCONOCIDO'

    if formato_unico:
        fmt = formatos[conteo_formatos.index[0]]
        if tipo == 'fecha':
            df[columna] = pd.to_datetime(df[columna], format=fmt)
        else:
            df[columna] = pd.to_datetime(df[columna], format=fmt).dt.time
        print(f"  ↳ [validar_columna_temporal] Validación correcta. Formato único. Columna convertida.")
        print()  # <<< NUEVO: cierre del bloque
        return df

    print(f"  ↳ [validar_columna_temporal] La columna NO pasó la validación de formato único.")
    print(f"  ↳ [validar_columna_temporal] Formatos encontrados: {dict(conteo_formatos)}")
    print()  # <<< NUEVO: cierre del bloque (aunque en V3 aún no había
             #     mensaje de conversión aplicada — eso llega en V4)

    convertidos = pd.Series(pd.NaT, index=df.index, dtype='object')
    for tipo_fmt, _ in conteo_formatos.items():
        fmt = formatos.get(tipo_fmt)
        if fmt is None:
            continue
        mask = tipo_detectado == tipo_fmt
        if tipo == 'fecha':
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt)
        else:
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt).dt.time

    df[columna] = convertidos
    return df
```

---

### V4 — Cierre explícito del camino "formatos mezclados" (versión final)

**Problema detectado:** al correr el pipeline completo (`Restart & Run
All`), se notó que el log terminaba justo después de "Formatos
encontrados", sin confirmar si la conversión por máscara se había
aplicado ni con qué resultado — daba la falsa impresión de que la
función "se quedaba ahí" en vez de seguir procesando.

**Cambio principal:** se agrega un mensaje de transición
("Por consecuente, aplicando conversión por máscara...") y, al final del
bucle, un mensaje de cierre que reporta cuántas filas se convirtieron
sobre el total, y qué formatos (si los hay) se quedaron sin conversor
definido (esos quedan como `NaT`).

```python
def validar_columna_temporal(df, columna, tipo='fecha'):
    """
    tipo: 'fecha' o 'hora' — decide qué clasificador y qué diccionario de
    formatos usar. La lógica de validación/conversión es idéntica para
    ambos casos, solo cambia qué función de clasificación se invoca.
    """
    clasificador = clasificar_formato_fecha if tipo == 'fecha' else clasificar_formato_hora
    formatos = FORMATOS_FECHA if tipo == 'fecha' else FORMATOS_HORA

    no_nulos = df[columna].notna()
    valores_str = df.loc[no_nulos, columna].astype(str).str.strip()

    tipo_detectado = pd.Series(index=df.index, dtype='object')
    tipo_detectado.loc[no_nulos] = valores_str.apply(clasificador)

    conteo_formatos = tipo_detectado.value_counts()
    print(f"  ↳ [validar_columna_temporal] Verificación de '{columna}' (tipo={tipo}):")
    print(conteo_formatos)
    print()

    formato_unico = len(conteo_formatos) == 1 and conteo_formatos.index[0] != 'DESCONOCIDO'

    if formato_unico:
        fmt = formatos[conteo_formatos.index[0]]
        if tipo == 'fecha':
            df[columna] = pd.to_datetime(df[columna], format=fmt)
        else:
            df[columna] = pd.to_datetime(df[columna], format=fmt).dt.time
        print(f"  ↳ [validar_columna_temporal] Validación correcta. Formato único. Columna convertida.")
        print()
        return df

    print(f"  ↳ [validar_columna_temporal] La columna NO pasó la validación de formato único.")
    print(f"  ↳ [validar_columna_temporal] Formatos encontrados: {dict(conteo_formatos)}")
    # <<< NUEVO: mensaje de transición — deja explícito que la función
    #     SIGUE trabajando, no se detiene aquí
    print(f"  ↳ [validar_columna_temporal] Por consecuente, aplicando conversión por máscara "
          f"(cada subconjunto con su propio formato)...")

    convertidos = pd.Series(pd.NaT, index=df.index, dtype='object')
    # <<< NUEVO: lista para registrar formatos que no tienen conversor
    #     (ej. 'DESCONOCIDO') y así poder reportarlos al final
    formatos_sin_conversor = []
    for tipo_fmt, _ in conteo_formatos.items():
        fmt = formatos.get(tipo_fmt)
        if fmt is None:
            formatos_sin_conversor.append(tipo_fmt)  # <<< NUEVO
            continue
        mask = tipo_detectado == tipo_fmt
        if tipo == 'fecha':
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt)
        else:
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt).dt.time

    df[columna] = convertidos

    # <<< NUEVO: bloque completo de cierre — esto es lo que faltaba
    #     desde V0. Reporta el resultado real de la conversión.
    n_convertidos = convertidos.notna().sum()
    n_total = len(convertidos)
    if formatos_sin_conversor:
        print(f"  ↳ [validar_columna_temporal] Conversión por máscara aplicada: "
              f"{n_convertidos}/{n_total} filas convertidas. "
              f"Formatos sin conversor (quedaron NaT): {formatos_sin_conversor}")
    else:
        print(f"  ↳ [validar_columna_temporal] Conversión por máscara aplicada: "
              f"{n_convertidos}/{n_total} filas convertidas correctamente.")
    print()

    return df
```

**Resultado final en consola (ejemplo real, `fact_paradas_PC['fecha']`):**
```
[orquestador] CONVIERTE 'fecha': str -> fecha (esperado datetime64[us])
  ↳ [validar_columna_temporal] Verificación de 'fecha' (tipo=fecha):
YMD          2246
DMY_SLASH    1404
Name: count, dtype: int64

  ↳ [validar_columna_temporal] La columna NO pasó la validación de formato único.
  ↳ [validar_columna_temporal] Formatos encontrados: {'YMD': 2246, 'DMY_SLASH': 1404}
  ↳ [validar_columna_temporal] Por consecuente, aplicando conversión por máscara (cada subconjunto con su propio formato)...
  ↳ [validar_columna_temporal] Conversión por máscara aplicada: 3650/3650 filas convertidas correctamente.

[orquestador] CONVIERTE 'hora_inicio_aprox': str -> hora (esperado <class 'object'>)
  ↳ [validar_columna_temporal] Verificación de 'hora_inicio_aprox' (tipo=hora):
HH_MM    3650
Name: count, dtype: int64

  ↳ [validar_columna_temporal] Validación correcta. Formato único. Columna convertida.

[orquestador] OK 'costo_estimado_soles': ya es decimal (float64), se omite.
[orquestador] OK 'causa': ya es categorico (str), se omite.
```

---

### V5 — Dos bugs encontrados al correr sobre datos reales (`fact_paradas_PC`)

Al correr el pipeline completo sobre datos reales con formatos
mezclados de verdad (`YMD` + `DMY_SLASH` en `fecha`), aparecieron dos
problemas que V4 no cubría — uno bloqueante y uno silencioso.

#### Bug A — `SyntaxError` por un carácter suelto

Al copiar el código de vuelta a `src/eda.py`, quedó un carácter `a`
pegado accidentalmente al final de una línea:

```python
        if fmt is None:a          # <-- esto no es Python válido
            formatos_sin_conversor.append(tipo_fmt)
```

**Efecto:** con esto en el archivo, `from src.eda import
validar_columna_temporal` no podía ejecutarse — el módulo entero fallaba
al importarse. Como consecuencia, se terminó redefiniendo la función
directamente en una celda del notebook para poder seguir trabajando,
generando dos copias de la misma función circulando a la vez (una rota
en el archivo, otra parcheada a mano en el notebook) — con el riesgo de
no saber cuál de las dos corrió realmente en cada ejecución.

**Fix:** quitar la `a`, dejando `if fmt is None:` normal.

#### Bug B — el dtype no quedaba forzado en el camino "formatos mezclados"

Este es más sutil porque no lanza ningún error — el pipeline corre y el
log de V4 incluso confirma "N/N filas convertidas correctamente". El
problema es que ese conteo mide *valores* convertidos, no el *dtype*
final de la columna.

```python
convertidos = pd.Series(pd.NaT, index=df.index, dtype='object')  # <-- nace 'object'
...
convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt)  # inserta Timestamps
...
df[columna] = convertidos   # <-- sigue siendo Series dtype='object' por fuera
```

En pandas, insertar objetos `Timestamp` dentro de una `Series` que nació
`dtype='object'` **no la reconvierte automáticamente** a
`datetime64`. Los valores quedan correctos individualmente, pero la
columna entera se queda "disfrazada" de `object` — así que
`reporte_calidad` seguía mostrando `fecha` como `object` en vez de
`datetime64[us]`, incumpliendo el contrato sin que nada lo señalara.

**Cómo se detectó:** al correr el orquestador **dos veces seguidas**
sobre el mismo DataFrame, la segunda corrida sí mostraba
`datetime64[us]` — pero no porque el bug estuviera resuelto, sino
porque en la segunda vuelta la columna ya traía puros `Timestamp`
impresos siempre con el mismo patrón de texto (`YMD_TIME`), así que caía
en el camino "formato único" de la función — el que sí asigna
`pd.to_datetime(...)` directo y por lo tanto sí deja un dtype real. Esa
segunda corrida "tapaba" el problema de la primera.

**Fix:** forzar el cast explícito al final del camino "formatos
mezclados", solo para `tipo == 'fecha'` (para `'hora'` el contrato
espera `object` con `datetime.time` adentro, así que ese caso no se
toca):

```python
    df[columna] = convertidos

    # <<< FIX: 'convertidos' nació dtype='object'; aunque adentro tenga
    #     puros Timestamps, la Series por fuera sigue siendo object hasta
    #     que se re-castea explícitamente.
    if tipo == 'fecha':
        df[columna] = pd.to_datetime(df[columna])
```

#### Código completo, con ambos fixes aplicados (versión vigente)

```python
def validar_columna_temporal(df, columna, tipo='fecha'):
    """
    tipo: 'fecha' o 'hora' — decide qué clasificador y qué diccionario de
    formatos usar. La lógica de validación/conversión es idéntica para
    ambos casos, solo cambia qué función de clasificación se invoca.
    """
    clasificador = clasificar_formato_fecha if tipo == 'fecha' else clasificar_formato_hora
    formatos = FORMATOS_FECHA if tipo == 'fecha' else FORMATOS_HORA

    no_nulos = df[columna].notna()
    valores_str = df.loc[no_nulos, columna].astype(str).str.strip()

    tipo_detectado = pd.Series(index=df.index, dtype='object')
    tipo_detectado.loc[no_nulos] = valores_str.apply(clasificador)

    conteo_formatos = tipo_detectado.value_counts()
    print(f"  ↳ [validar_columna_temporal] Verificación de '{columna}' (tipo={tipo}):")
    print(conteo_formatos)
    print()

    formato_unico = len(conteo_formatos) == 1 and conteo_formatos.index[0] != 'DESCONOCIDO'

    if formato_unico:
        fmt = formatos[conteo_formatos.index[0]]
        if tipo == 'fecha':
            df[columna] = pd.to_datetime(df[columna], format=fmt)
        else:
            df[columna] = pd.to_datetime(df[columna], format=fmt).dt.time
        print(f"  ↳ [validar_columna_temporal] Validación correcta. Formato único. Columna convertida.")
        print()
        return df

    print(f"  ↳ [validar_columna_temporal] La columna NO pasó la validación de formato único.")
    print(f"  ↳ [validar_columna_temporal] Formatos encontrados: {dict(conteo_formatos)}")
    print(f"  ↳ [validar_columna_temporal] Por consecuente, aplicando conversión por máscara "
          f"(cada subconjunto con su propio formato)...")

    convertidos = pd.Series(pd.NaT, index=df.index, dtype='object')
    formatos_sin_conversor = []
    for tipo_fmt, _ in conteo_formatos.items():
        fmt = formatos.get(tipo_fmt)
        if fmt is None:                                    # <<< FIX A: sin la "a" suelta (SyntaxError)
            formatos_sin_conversor.append(tipo_fmt)
            continue
        mask = tipo_detectado == tipo_fmt
        if tipo == 'fecha':
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt)
        else:
            convertidos.loc[mask] = pd.to_datetime(df.loc[mask, columna], format=fmt).dt.time

    df[columna] = convertidos

    # <<< FIX B: forzar el dtype correcto para 'fecha' -- ver explicación arriba
    if tipo == 'fecha':
        df[columna] = pd.to_datetime(df[columna])

    n_convertidos = df[columna].notna().sum()
    n_total = len(df[columna])
    if formatos_sin_conversor:
        print(f"  ↳ [validar_columna_temporal] Conversión por máscara aplicada: "
              f"{n_convertidos}/{n_total} filas convertidas. "
              f"Formatos sin conversor (quedaron NaT): {formatos_sin_conversor}")
    else:
        print(f"  ↳ [validar_columna_temporal] Conversión por máscara aplicada: "
              f"{n_convertidos}/{n_total} filas convertidas correctamente.")
    print()

    return df
```

#### Función complementaria: verificación de calidad post-transformación

Para no depender de leer el log línea por línea, se agregó una función
que corre *después* de `aplicar_transformaciones` y confirma, columna
por columna, que el dtype final cumple el contrato y que no aparecieron
nulos nuevos (señal de una conversión fallida silenciosa, como el Bug B
de arriba lo hubiera sido si nadie lo revisaba):

```python
def verificar_calidad_transformacion(df, esquema, dtype_esperado, nulos_antes):
    """
    Corre DESPUÉS de aplicar_transformaciones. Compara:
      1) dtype final vs dtype esperado del contrato -> confirma que la
         conversión realmente terminó en el tipo correcto (no solo que
         'se intentó').
      2) nulos actuales vs nulos_antes -> si subieron, alguna fila no se
         pudo convertir (ej. quedó NaT por formato DESCONOCIDO) y antes
         no era nula, así que hay que investigarla, no ignorarla.
    """
    print("=== Verificación de calidad post-transformación ===\n")
    hubo_fallas = False

    for columna, tipo_esperado in esquema.items():
        if columna not in df.columns:
            continue

        dtype_actual = df[columna].dtype
        dtype_objetivo = dtype_esperado.get(tipo_esperado)
        ok_dtype = (dtype_actual == dtype_objetivo)
        n_nulos_ahora = df[columna].isna().sum()
        n_nulos_antes = nulos_antes.get(columna, 0)
        delta_nulos = n_nulos_ahora - n_nulos_antes

        estado = "OK" if ok_dtype else "FALLA"
        if not ok_dtype:
            hubo_fallas = True
        print(f"[{estado}] '{columna}': dtype={dtype_actual} (esperado {dtype_objetivo}) | "
              f"nulos={n_nulos_ahora} (antes: {n_nulos_antes})")

        if delta_nulos > 0:
            hubo_fallas = True
            print(f"       ⚠ +{delta_nulos} nulos NUEVOS -- alguna fila no se pudo "
                  f"convertir (revisar formatos DESCONOCIDO u otro caso no cubierto)")

    print()
    print("Resultado: TODO OK" if not hubo_fallas else "Resultado: HAY QUE REVISAR ALGO")
    return not hubo_fallas
```

Uso:
```python
## 1) capturar nulos ANTES de tocar nada
nulos_antes = fact_paradas_PC[list(esquema_paradas.keys())].isna().sum().to_dict()

## 2) correr el orquestador
fact_paradas_PC = aplicar_transformaciones(fact_paradas_PC, esquema_paradas)

## 3) verificar calidad del resultado (dtype real, no solo "se intentó")
verificar_calidad_transformacion(fact_paradas_PC, esquema_paradas, DTYPE_ESPERADO, nulos_antes)
```

#### Lección clave de esta versión

Correr el mismo pipeline dos veces sobre el mismo DataFrame puede
esconder bugs, porque la segunda corrida ya no ve los datos crudos —
ve datos parcialmente transformados por la primera pasada, que pueden
"accidentalmente" tomar un camino distinto del código (aquí, pasar de
"formatos mezclados" a "formato único" porque todos los `Timestamp` se
ven iguales como texto). La forma correcta de validar un fix es
`Restart & Run All` y confirmar en la **primera y única** pasada, no
correr una celda repetidamente hasta que el resultado se vea bien.

---

### Explicación básica del flujo lógico (versión final)

1. **`aplicar_transformaciones` (el orquestador)** recorre un
   diccionario `esquema` que dice qué tipo *debería* tener cada
   columna (ej. `'fecha': 'fecha'`, `'causa': 'categorico'`).
2. Para cada columna, compara el `dtype` actual contra el `dtype`
   esperado (`DTYPE_ESPERADO`). Si ya coincide → `OK`, no hace nada.
3. Si no coincide, decide **cómo** convertirla:
   - Si el tipo necesita ver la columna completa (fecha/hora, porque
     hay que detectar el formato mirando todos los valores a la vez) →
     llama a `validar_columna_temporal` vía `CONVERSORES_COLUMNA`.
   - Si el tipo se puede convertir fila por fila sin contexto extra
     (entero, decimal, categórico) → aplica directamente la función de
     `CONVERSORES_SIMPLES` sobre la serie.
4. **`validar_columna_temporal`** intenta primero el camino rápido: si
   *toda* la columna tiene un único formato reconocido, convierte todo
   de una sola pasada.
5. Si hay formatos mezclados (el caso real de `fecha` en este dataset:
   `YMD` y `DMY_SLASH` conviviendo), no fuerza un formato equivocado
   sobre las filas que no le corresponden — separa la columna en
   grupos según el formato detectado (`mask`) y convierte cada grupo
   con su propio formato.
6. Al terminar la conversión por máscara, si `tipo == 'fecha'` se
   fuerza un cast final (`pd.to_datetime(df[columna])`) para que el
   dtype de la columna quede realmente como `datetime64`, no solo
   "conteniendo" objetos `Timestamp` dentro de una `Series` `object`
   (ver V5, Bug B).
7. Al final, reporta cuántas filas quedaron convertidas sobre el total,
   y si algún formato (ej. `DESCONOCIDO`) no tenía un conversor
   definido y por tanto esas filas quedaron como `NaT` (fecha vacía),
   para que quede documentado y no se pierda silenciosamente.
8. Aparte, `verificar_calidad_transformacion` (V5) corre después del
   orquestador para confirmar, por columna, que el dtype final cumple
   el contrato — sin depender de leer el log ni de correr el pipeline
   más de una vez para "ver si quedó bien".

**Por qué importa el prefijo `[orquestador]` vs `↳ [validar_columna_temporal]`:**
Sin esa distinción, al ver el log era imposible saber si una línea
venía de la función que *decide qué convertir* o de la función que
*hace la conversión en sí* — especialmente en pipelines con varias
columnas y varias plantas (PN/PC/PS), donde el mismo patrón se repite
muchas veces seguidas.


---

## Función: `explorar_columna`

Apunte de trazabilidad, mismo formato que `evolucion_validar_columna_temporal.md`:
qué cambió en cada versión, cuál fue la situación real que lo motivó, y el
código completo de cada paso para poder comparar.

---

### V0 — Origen

Exploración por rama según tipo de columna (`fecha`/`hora`, numérico,
categórico), con `describe()` y conteo de negativos/ceros para columnas
numéricas.

```python
def explorar_columna(df, columna, tipo=None, top_n=10):
    serie = df[columna]
    print(f"\n--- Exploración columna: {columna} (dtype={serie.dtype}, tipo={tipo or 'inferido'}) ---")

    if tipo in ('fecha', 'hora', 'fecha_hora') or pd.api.types.is_datetime64_any_dtype(serie):
        print(f"Rango: {serie.min()} -> {serie.max()}")
        print(f"Días/valores únicos: {serie.nunique()}")
        if tipo in ('fecha', 'fecha_hora'):
            rango_completo = pd.date_range(serie.min(), serie.max())
            faltantes = rango_completo.difference(pd.to_datetime(serie.dropna().unique()))
            print(f"Fechas ausentes en el rango: {len(faltantes)}")

    elif tipo in ('entero', 'decimal') or pd.api.types.is_numeric_dtype(serie):
        print(serie.describe())
        negativos = (serie < 0).sum()
        ceros = (serie == 0).sum()
        print(f"Negativos: {negativos} | Ceros: {ceros}")

    elif tipo == 'categorico' or serie.dtype in ('string', object):
        conteo = serie.value_counts(dropna=False)
        print(f"Categorías únicas: {serie.nunique()}")
        print(conteo.head(top_n))
        if len(conteo) > top_n:
            print(f"... ({len(conteo) - top_n} categorías más)")

    else:
        print("Tipo no reconocido para exploración -- mostrando .describe() genérico:")
        print(serie.describe())

    return None
```

**Limitación detectada (situación problema real, no hipotética):**

Explorando `Ton_Rechazo` en `prodLegacy_PC`, `describe()` mostró
`count = 4244` sobre un total de 4374 filas. Para saber si eso era un
3% de nulos (ruido de captura normal) o algo más serio, hubo que restar
a mano (`4374 - 4244 = 130`, luego `130/4374`) fuera de la función —
la función misma nunca lo entregó. Lo mismo hubiera pasado con
cualquier otra columna numérica del proyecto: la completitud del dato
(cuántos nulos, qué porcentaje) es información que se necesita **cada
vez**, no un caso especial de `Ton_Rechazo`.

Además, el porcentaje de negativos/ceros se imprimía como conteo
absoluto — sin el total ni el % correspondiente, comparar la severidad
de un hallazgo entre columnas de distinto tamaño (ej. `prodLegacy_PC`
con 4374 filas vs. `prodLegacy_PN` con 7616) exigía sacar la cuenta
cada vez a mano.

---

### V1 — Header de completitud + porcentajes

**Cambio principal:** se calcula `n_total`/`n_nulos`/`n_validos` **una
sola vez, antes del branching por tipo**, porque es información que
aplica a cualquier tipo de columna (fecha, numérica o categórica) —
no es exclusiva de las numéricas. Se imprime siempre, como parte fija
del encabezado. Los porcentajes de negativos/ceros se calculan sobre
`n_validos` (no sobre `n_total`), para no inflar el porcentaje con
filas que ya ni participan en el conteo por ser nulas.

```python
def explorar_columna(df, columna, tipo=None, top_n=10):
    serie = df[columna]
    n_total = len(serie)
    n_nulos = serie.isna().sum()
    n_validos = n_total - n_nulos                                  # <<< NUEVO

    print(f"\n--- Exploración columna: {columna} (dtype={serie.dtype}, tipo={tipo or 'inferido'}) ---")
    # <<< NUEVO: header de completitud, antes del branching -- aplica a cualquier tipo
    print(f"Filas totales: {n_total} | No nulos: {n_validos} ({n_validos/n_total:.1%}) | Nulos: {n_nulos} ({n_nulos/n_total:.1%})")

    if tipo in ('fecha', 'hora', 'fecha_hora') or pd.api.types.is_datetime64_any_dtype(serie):
        print(f"Rango: {serie.min()} -> {serie.max()}")
        print(f"Días/valores únicos: {serie.nunique()}")
        if tipo in ('fecha', 'fecha_hora'):
            rango_completo = pd.date_range(serie.min(), serie.max())
            faltantes = rango_completo.difference(pd.to_datetime(serie.dropna().unique()))
            print(f"Fechas ausentes en el rango: {len(faltantes)}")

    elif tipo in ('entero', 'decimal') or pd.api.types.is_numeric_dtype(serie):
        print(serie.describe())
        negativos = (serie < 0).sum()
        ceros = (serie == 0).sum()
        # <<< CAMBIO: antes solo conteo absoluto, ahora también % sobre n_validos
        pct_neg = negativos / n_validos if n_validos else 0
        pct_ceros = ceros / n_validos if n_validos else 0
        print(f"Negativos: {negativos} ({pct_neg:.1%}) | Ceros: {ceros} ({pct_ceros:.1%})")

    elif tipo == 'categorico' or serie.dtype in ('string', object):
        conteo = serie.value_counts(dropna=False)
        print(f"Categorías únicas: {serie.nunique()}")
        print(conteo.head(top_n))
        if len(conteo) > top_n:
            print(f"... ({len(conteo) - top_n} categorías más)")

    else:
        print("Tipo no reconocido para exploración -- mostrando .describe() genérico:")
        print(serie.describe())

    return None
```

**Por qué el header va antes del `if/elif` y no dentro de cada rama:**
duplicar `n_total`/`n_nulos`/`% completitud` en las tres ramas (fecha,
numérico, categórico) sería repetir la misma cuenta tres veces con el
riesgo de que una de las copias se desactualice si se edita solo una
rama más adelante. Calcularlo una vez arriba y listo es más simple y
es coherente con "generalizar cuando se repite el patrón" — aquí se
repetía en las tres ramas desde el principio, así que subirlo al
encabezado no es anticiparse, es sacar algo que ya era común a las tres.

**Lo que se dejó fuera a propósito, por ahora:** no se agregó el mismo
detalle de % a la rama `categorico` (ej. "% que representa la categoría
más frecuente") ni a la rama `fecha` (ej. "% de fechas faltantes sobre
el rango"). No hay todavía un caso real del proyecto que lo haya pedido
— se agrega cuando aparezca, no antes (mismo criterio aplicado en
`validar_columna_temporal`).

---

### Patrón para este proyecto de ahora en adelante

Cada función reutilizable de `eda.py` que reciba una mejora motivada por
un caso real (no una mejora especulativa) se documenta en su propio
archivo `evolucion_<nombre_funcion>.md`, con esta estructura fija:

1. **V0 (o la versión vigente actual)** — código completo tal cual está.
2. **Situación problema** — el caso real y concreto del proyecto que
   expuso la limitación (nunca una limitación hipotética o "por si
   acaso").
3. **V(n+1)** — código completo con los cambios marcados inline como
   `# <<< NUEVO` / `# <<< CAMBIO`, y una explicación breve del porqué
   de cada cambio.
4. Si algo se consideró y se dejó fuera a propósito, se anota también
   (como arriba) — para no repetir la misma discusión más adelante.

Esto da un historial de "por qué la función es como es hoy", no solo
"qué hace hoy" — la versión anterior nunca se pierde, queda como
referencia dentro del mismo archivo en vez de perderse en el historial
de git o en una celda de notebook sobreescrita.

