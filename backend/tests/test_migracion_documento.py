from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text


def _cargar_migracion():
    ruta = (
        Path(__file__).parents[1]
        / "migrations/versions/d8f4b2a1c6e7_generalizar_documento_mer.py"
    )
    spec = spec_from_file_location("migracion_documento_mer", ruta)
    assert spec is not None and spec.loader is not None
    migracion = module_from_spec(spec)
    spec.loader.exec_module(migracion)
    return migracion


def test_migracion_conserva_documento_hu11(db_engine):
    esquema = f"test_migracion_documento_{uuid4().hex}"
    migracion = _cargar_migracion()

    with db_engine.connect() as conexion:
        transaccion = conexion.begin()
        try:
            conexion.execute(text(f'CREATE SCHEMA "{esquema}"'))
            conexion.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
            conexion.execute(text("CREATE TABLE usuario (id SERIAL PRIMARY KEY)"))
            conexion.execute(
                text("CREATE TABLE solicitud_convenio (id SERIAL PRIMARY KEY)")
            )
            conexion.execute(text("CREATE TABLE convenio (id SERIAL PRIMARY KEY)"))
            conexion.execute(
                text(
                    """
                    CREATE TABLE documento_solicitud (
                        id SERIAL PRIMARY KEY,
                        solicitud_id INTEGER NOT NULL
                            REFERENCES solicitud_convenio(id) ON DELETE CASCADE,
                        tipo_documento VARCHAR(40) NOT NULL,
                        nombre_original VARCHAR(255) NOT NULL,
                        tipo_mime VARCHAR(100) NOT NULL,
                        tamano_bytes INTEGER NOT NULL,
                        clave_objeto VARCHAR(255) NOT NULL UNIQUE,
                        creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
                        CONSTRAINT ck_documento_solicitud_tamano
                            CHECK (tamano_bytes > 0),
                        CONSTRAINT ck_documento_solicitud_tipo CHECK (
                            tipo_documento IN (
                                'CAMARA_COMERCIO', 'RUT',
                                'CEDULA_REPRESENTANTE_LEGAL',
                                'OTRO_DOCUMENTO_REPRESENTACION', 'OTRO_SOPORTE'
                            )
                        )
                    )
                    """
                )
            )
            conexion.execute(
                text(
                    "CREATE INDEX ix_documento_solicitud_solicitud_id "
                    "ON documento_solicitud (solicitud_id)"
                )
            )
            solicitud_id = conexion.execute(
                text("INSERT INTO solicitud_convenio DEFAULT VALUES RETURNING id")
            ).scalar_one()
            documento_id = conexion.execute(
                text(
                    """
                    INSERT INTO documento_solicitud (
                        solicitud_id, tipo_documento, nombre_original,
                        tipo_mime, tamano_bytes, clave_objeto
                    ) VALUES (
                        :solicitud_id, 'RUT', 'rut.pdf',
                        'application/pdf', 123, 'solicitudes/1/rut.pdf'
                    ) RETURNING id
                    """
                ),
                {"solicitud_id": solicitud_id},
            ).scalar_one()

            migracion.op = Operations(MigrationContext.configure(conexion))
            migracion.upgrade()

            assert (
                conexion.execute(
                    text("SELECT to_regclass('documento_id_seq')::text")
                ).scalar_one()
                == "documento_id_seq"
            )
            assert conexion.execute(
                text("SELECT to_regclass('documento_solicitud_id_seq')")
            ).scalar_one_or_none() is None

            fila = conexion.execute(
                text(
                    """
                    SELECT solicitud_id, convenio_id, tipo, nombre_archivo,
                           ruta_almacenamiento, tipo_mime, tamano_bytes,
                           version, es_vigente, cargado_por_id
                    FROM documento WHERE id = :id
                    """
                ),
                {"id": documento_id},
            ).one()
            assert fila == (
                solicitud_id,
                None,
                "RUT",
                "rut.pdf",
                "solicitudes/1/rut.pdf",
                "application/pdf",
                123,
                None,
                True,
                None,
            )

            documento_mer_id = conexion.execute(
                text(
                    """
                    INSERT INTO documento (
                        solicitud_id, tipo, nombre_archivo, tipo_mime,
                        tamano_bytes, ruta_almacenamiento
                    ) VALUES (
                        :solicitud_id, 'FORMATO_SOLICITUD', 'formato.pdf',
                        'application/pdf', 321, 'solicitudes/1/formato.pdf'
                    ) RETURNING id
                    """
                ),
                {"solicitud_id": solicitud_id},
            ).scalar_one()
            assert documento_mer_id is not None
            conexion.execute(
                text("DELETE FROM documento WHERE id = :id"),
                {"id": documento_mer_id},
            )

            convenio_id = conexion.execute(
                text("INSERT INTO convenio DEFAULT VALUES RETURNING id")
            ).scalar_one()
            conexion.execute(
                text("UPDATE documento SET convenio_id = :convenio_id WHERE id = :id"),
                {"convenio_id": convenio_id, "id": documento_id},
            )
            with pytest.raises(RuntimeError, match="No se puede restaurar"):
                migracion.downgrade()
            conexion.execute(
                text("UPDATE documento SET convenio_id = NULL WHERE id = :id"),
                {"id": documento_id},
            )

            migracion.downgrade()
            assert (
                conexion.execute(
                    text("SELECT to_regclass('documento_solicitud_id_seq')::text")
                ).scalar_one()
                == "documento_solicitud_id_seq"
            )
            assert conexion.execute(
                text("SELECT to_regclass('documento_id_seq')")
            ).scalar_one_or_none() is None
            restaurada = conexion.execute(
                text(
                    "SELECT solicitud_id, tipo_documento, nombre_original, "
                    "clave_objeto FROM documento_solicitud WHERE id = :id"
                ),
                {"id": documento_id},
            ).one()
            assert restaurada == (
                solicitud_id,
                "RUT",
                "rut.pdf",
                "solicitudes/1/rut.pdf",
            )
        finally:
            transaccion.rollback()
