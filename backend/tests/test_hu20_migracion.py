from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text


def test_upgrade_hu20_conserva_hitos_historicos_sin_inventar_activaciones(db_engine):
    ruta = Path(__file__).parents[1] / (
        "migrations/versions/e77280c6486a_hu_20_hitos_de_elaboracion_y_activacion_.py"
    )
    spec = spec_from_file_location("migracion_hu20", ruta)
    migracion = module_from_spec(spec)
    spec.loader.exec_module(migracion)
    creado = datetime(2025, 1, 1, tzinfo=UTC)
    inicio = datetime(2025, 2, 1, tzinfo=UTC)
    activacion = datetime(2025, 3, 1, tzinfo=UTC)
    # El estado o el ingreso histórico a seguimiento, por sí solos, no prueban
    # que un convenio haya completado la formalización.
    casos = [
        (1, "MANUAL_ORI", None, "EN_TRAMITE", None),
        (2, "SOLICITUD", 20, "EN_TRAMITE", None),
        (3, "SOLICITUD", 30, "VIGENTE", "2025-03-01"),
        (4, "MANUAL_ORI", None, "VIGENTE", "2025-03-01"),
        (5, "MANUAL_ORI", None, "VIGENTE", None),
        (6, "SOLICITUD", 60, "CANCELADO", None),
    ]
    with db_engine.connect() as conexion, conexion.begin():
        esquema = f"hu20_{uuid4().hex}"
        conexion.execute(text(f'CREATE SCHEMA "{esquema}"'))
        conexion.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
        conexion.execute(text("""
            CREATE TABLE convenio (
                id integer PRIMARY KEY, origen text, solicitud_id integer,
                estado text, fecha_firma date, creado_en timestamptz
            )
        """))
        conexion.execute(text("CREATE TABLE etapa (id integer PRIMARY KEY, codigo text)"))
        conexion.execute(text("""
            CREATE TABLE historial_etapa (
                convenio_id integer, etapa_origen_id integer,
                etapa_destino_id integer, fecha_cambio timestamptz
            )
        """))
        conexion.execute(text("""
            INSERT INTO etapa VALUES (1, 'ELABORACION'), (2, 'FIRMA_ARCHIVO_SEGUIMIENTO')
        """))
        for identificador, origen, solicitud_id, estado, firma in casos:
            conexion.execute(text("""
                INSERT INTO convenio VALUES (:id, :origen, :solicitud, :estado, :firma, :creado)
            """), {
                "id": identificador, "origen": origen, "solicitud": solicitud_id,
                "estado": estado, "firma": firma, "creado": creado,
            })
            if identificador != 1:
                conexion.execute(text("""
                    INSERT INTO historial_etapa VALUES (:id, NULL, 1, :inicio),
                        (:id, 1, 2, :activacion)
                """), {"id": identificador, "inicio": inicio, "activacion": activacion})
        migracion.op = Operations(MigrationContext.configure(conexion))
        migracion.upgrade()

        columnas = {c["name"]: c for c in inspect(conexion).get_columns("convenio")}
        assert columnas["elaboracion_iniciada_en"]["nullable"] is True
        assert columnas["activado_en"]["nullable"] is True
        filas = conexion.execute(text("""
            SELECT id, elaboracion_iniciada_en, activado_en FROM convenio ORDER BY id
        """)).all()
        assert filas == [
            (1, creado, None), (2, inicio, None), (3, inicio, activacion),
            (4, inicio, activacion), (5, inicio, None), (6, inicio, None),
        ]
        assert conexion.scalar(text("""
            SELECT count(*) FROM convenio WHERE origen = 'MANUAL_ORI' AND solicitud_id IS NULL
        """)) == 3
        # DDL y datos de prueba se descartan junto con este esquema aislado.
        conexion.rollback()
