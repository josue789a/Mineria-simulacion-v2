# src/carga_sql.py
# Modelo SQL de la V2 (13 tablas) y carga desde DataFrames.
# Regla: la transformacion vive en produccion.py / notebook; aqui solo se declara el
# esquema y se carga. Asi se puede probar "el DataFrame esta bien" separado de "la carga funciono".

import pandas as pd
from sqlalchemy import (create_engine, text, Column, String, Unicode, Integer, Float,
                        Date, Time, ForeignKey)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# =========================================================
# 1) DIMENSIONES
class DimPlantas(Base):
    __tablename__ = 'dim_plantas'
    planta_id = Column(String(5), primary_key=True)
    nombre_planta = Column(String(50))
    region = Column(String(30))
    tipo_clima = Column(String(60))
    factor_capacidad = Column(Float)
    anio_inicio_operacion = Column(Integer)


class DimEquipos(Base):
    __tablename__ = 'dim_equipos'
    equipo_id = Column(String(20), primary_key=True)
    planta_id = Column(String(5), ForeignKey('dim_plantas.planta_id'))
    nombre_equipo = Column(String(50))
    area = Column(String(30))
    tipo_equipo = Column(String(30))
    capacidad_nominal_tmh = Column(Float)      # era Integer en V1: el maestro trae decimales
    anio_instalacion = Column(Integer)
    clase_confiabilidad = Column(String(15))


class DimMineral(Base):
    __tablename__ = 'dim_mineral'
    mineral_id = Column(String(5), primary_key=True)
    nombre = Column(String(30))
    unidad_ley = Column(String(10))
    unidad_precio = Column(String(15))


class DimCategoriaGasto(Base):
    __tablename__ = 'dim_categoria_gasto'
    categoria_id = Column(String(5), primary_key=True)
    nombre = Column(String(50))


class DimCategoriaCausa(Base):
    __tablename__ = 'dim_categoria_causa'
    causa = Column(Unicode(100), primary_key=True)    # Unicode = NVARCHAR, por las tildes
    categoria_causa = Column(Unicode(30))


class DimMetasMensuales(Base):
    __tablename__ = 'dim_metas_mensuales'
    anio_mes = Column(String(7), primary_key=True)    # formato 2024-01
    planta_id = Column(String(5), ForeignKey('dim_plantas.planta_id'), primary_key=True)
    meta_toneladas_planta = Column(Float)
    real_toneladas_planta = Column(Float)


# =========================================================
# 2) HECHOS OPERATIVOS (salen del pipeline)
class FactProduccion(Base):
    __tablename__ = 'fact_produccion'
    equipo_id = Column(String(20), ForeignKey('dim_equipos.equipo_id'), primary_key=True)
    fecha = Column(Date, primary_key=True)
    horas_operativas = Column(Float)
    horas_parada = Column(Float)
    toneladas_procesadas = Column(Float)
    toneladas_fuera_especificacion = Column(Float)
    # capacidad_nominal_tmh ya no va aqui: vive solo en dim_equipos


class FactParadas(Base):
    __tablename__ = 'fact_paradas'
    parada_id = Column(String(20), primary_key=True)
    equipo_id = Column(String(20), ForeignKey('dim_equipos.equipo_id'))
    fecha = Column(Date)
    hora_inicio_aprox = Column(Time)
    duracion_horas = Column(Float)
    tipo_parada = Column(String(20))
    causa = Column(Unicode(100), ForeignKey('dim_categoria_causa.causa'))
    costo_estimado_soles = Column(Float)


class FactMantenimiento(Base):
    __tablename__ = 'fact_mantenimiento'
    orden_id = Column(String(20), primary_key=True)
    parada_id = Column(String(20), ForeignKey('fact_paradas.parada_id'))
    equipo_id = Column(String(20), ForeignKey('dim_equipos.equipo_id'))
    fecha_apertura = Column(Date)
    tipo_orden = Column(String(20))
    horas_hombre = Column(Float)
    num_tecnicos = Column(Integer)
    repuesto_principal = Column(String(50))
    costo_repuestos_soles = Column(Float)


# =========================================================
# 3) HECHOS METALURGICO-FINANCIEROS (ya vienen limpios)
class FactPreciosMercado(Base):
    __tablename__ = 'fact_precios_mercado'          # sin planta_id a proposito: precio global
    fecha = Column(Date, primary_key=True)
    precio_cu_usd_lb = Column(Float)
    precio_zn_usd_lb = Column(Float)
    precio_ag_usd_oz = Column(Float)
    tipo_cambio_pen_usd = Column(Float)


class FactProduccionMineral(Base):
    __tablename__ = 'fact_produccion_mineral'
    fecha = Column(Date, primary_key=True)
    planta_id = Column(String(5), ForeignKey('dim_plantas.planta_id'), primary_key=True)
    ley_cabeza_cu_pct = Column(Float)
    ley_cabeza_zn_pct = Column(Float)
    ley_cabeza_ag_gt = Column(Float)
    ley_concentrado_cu_pct = Column(Float)
    toneladas_procesadas_planta = Column(Float)
    recuperacion_pct = Column(Float)
    fino_contenido_cu_ton = Column(Float)
    fino_recuperado_cu_ton = Column(Float)
    fino_contenido_zn_ton = Column(Float)
    fino_recuperado_zn_ton = Column(Float)
    fino_contenido_ag_kg = Column(Float)
    fino_recuperado_ag_kg = Column(Float)
    toneladas_concentrado_cu = Column(Float)


class FactVentas(Base):
    __tablename__ = 'fact_ventas'
    fecha = Column(Date, primary_key=True)
    planta_id = Column(String(5), ForeignKey('dim_plantas.planta_id'), primary_key=True)
    ingreso_cu_usd = Column(Float)
    ingreso_zn_usd = Column(Float)
    ingreso_ag_usd = Column(Float)
    ingreso_total_usd = Column(Float)
    ingreso_total_pen = Column(Float)


class FactGastos(Base):
    __tablename__ = 'fact_gastos'
    fecha = Column(Date, primary_key=True)
    planta_id = Column(String(5), ForeignKey('dim_plantas.planta_id'), primary_key=True)
    categoria_id = Column(String(5), ForeignKey('dim_categoria_gasto.categoria_id'), primary_key=True)
    monto_soles = Column(Float)


# =========================================================
# 4) CONEXION
def crear_base(nombre_db, servidor=r'localhost\SQLEXPRESS'):
    """Crea la base si no existe (se conecta a master)."""
    import pyodbc
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        f'SERVER={servidor};DATABASE=master;Trusted_Connection=yes;', autocommit=True)
    cur = conn.cursor()
    cur.execute(f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '{nombre_db}') "
                f"CREATE DATABASE {nombre_db}")
    cur.close()
    conn.close()
    print(f"Base '{nombre_db}' ok")


def crear_engine(nombre_db, servidor=r'localhost\SQLEXPRESS'):
    # fast_executemany: sin esto pyodbc inserta fila por fila y 44 mil filas tardan mucho
    return create_engine(
        f'mssql+pyodbc://@{servidor}/{nombre_db}'
        '?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes',
        fast_executemany=True)


# =========================================================
# 5) CARGA
def cargar_tablas(engine, tablas, recrear=True):
    """
    tablas: dict {nombre_tabla: DataFrame}, con las 13 tablas del modelo.
    - Verifica que cada DataFrame tenga EXACTAMENTE las columnas del modelo (antes de tocar SQL).
    - Carga en orden de claves foraneas (sorted_tables), no en el orden del dict.
    - Compara filas cargadas vs filas del DataFrame. Devuelve el reporte.
    """
    faltan_df = [t.name for t in Base.metadata.sorted_tables if t.name not in tablas]
    if faltan_df:
        raise KeyError(f"Faltan DataFrames para: {faltan_df}")

    # 1) Validar columnas ANTES de borrar nada
    for t in Base.metadata.sorted_tables:
        esperadas = [c.name for c in t.columns]
        reales = list(tablas[t.name].columns)
        if set(esperadas) != set(reales):
            raise ValueError(f"[{t.name}] columnas no coinciden | "
                             f"faltan en df: {sorted(set(esperadas) - set(reales))} | "
                             f"sobran en df: {sorted(set(reales) - set(esperadas))}")

    # 2) Esquema
    if recrear:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        print("Tablas recreadas")

    # 3) Carga en orden de FK
    reporte = []
    for t in Base.metadata.sorted_tables:
        df = tablas[t.name][[c.name for c in t.columns]]
        df.to_sql(t.name, engine, index=False, if_exists='append', chunksize=5000)
        with engine.connect() as conn:
            n_sql = conn.execute(text(f"SELECT COUNT(*) FROM {t.name}")).scalar()
        reporte.append({'tabla': t.name, 'filas_df': len(df), 'filas_sql': n_sql,
                        'ok': len(df) == n_sql})
        print(f"{t.name}: {len(df)} -> {n_sql}")

    reporte = pd.DataFrame(reporte)
    if not reporte['ok'].all():
        raise RuntimeError(f"Conteos que no cuadran:\n{reporte[~reporte['ok']]}")
    return reporte
