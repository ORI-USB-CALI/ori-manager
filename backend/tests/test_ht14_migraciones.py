"""H-03: Alembic real en una base desechable local, nunca en la base de la suite."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from backend.core.config import settings


@pytest.fixture
def base_migraciones_ht14():
    url = settings.database_url
    # Este test necesita CREATE DATABASE. Se prohíbe apuntarlo a un servidor remoto.
    assert url.host in {"db", "localhost", "127.0.0.1", "::1"}
    nombre = f"ori_ht14_migracion_{uuid4().hex}"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conexion:
        conexion.execute(text(f'CREATE DATABASE "{nombre}"'))
    motor = create_engine(url.set(database=nombre))

    def migrar(operacion, revision):
        resultado = subprocess.run(
            [sys.executable, "-m", "alembic", operacion, revision],
            cwd=Path(__file__).parents[1],
            env={**os.environ, "DATABASE_NAME": nombre},
            capture_output=True, text=True, check=False,
        )
        assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    try:
        yield motor, migrar
    finally:
        motor.dispose()
        # Solo se elimina el nombre aleatorio creado arriba por esta misma prueba.
        with admin.connect() as conexion:
            conexion.execute(text(f'DROP DATABASE "{nombre}"'))
        admin.dispose()


def test_h03_upgrade_downgrade_reaplicar_preserva_catalogo_e_historia(
    base_migraciones_ht14,
):
    motor, migrar = base_migraciones_ht14
    migrar("upgrade", "a109c8f2b10b")
    with motor.begin() as conexion:
        assert int(conexion.scalar(text("SHOW server_version_num"))) >= 180000
        conexion.execute(text("""
            INSERT INTO pais (codigo_iso, nombre) VALUES
            ('CO', 'Colombia'), ('ES', 'España'),
            ('US', 'Estados Unidos histórico'), ('ZZ', 'País institucional')
        """))
        anteriores = conexion.execute(text("SELECT id, codigo_iso, nombre FROM pais ORDER BY id")).all()
        usuario_id = conexion.scalar(text("""
            INSERT INTO usuario (correo, hash_contrasena, nombre_completo, rol_id, tipo_usuario)
            SELECT 'historia@example.test', 'sin acceso', 'Histórica', id, 'EXTERNO'
            FROM rol WHERE codigo = 'SOLICITANTE_EXTERNO' RETURNING id
        """))
        conexion.execute(text("""
            INSERT INTO aliado (nombre, tipo, tipo_identificacion, identificacion, pais_id)
            SELECT 'Aliado histórico', 'UNIVERSIDAD', 'NIT', '900.123.456', id
            FROM pais WHERE codigo_iso = 'ES'
        """))
        conexion.execute(text("""
            INSERT INTO solicitud_convenio
                (consecutivo, tipo_solicitante, solicitante_id, estado,
                 pais_aliado_propuesto, telefono_aliado_propuesto, identificacion_aliado_propuesto)
            VALUES ('HT14-HISTORICA', 'EXTERNO', :usuario, 'DEVUELTA',
                    'País histórico', '5551234', 'ID legado')
        """), {"usuario": usuario_id})

    def catalogo():
        with motor.connect() as conexion:
            return conexion.execute(text("SELECT id, codigo_iso, nombre FROM pais ORDER BY id")).all()

    def comprobar_historia():
        with motor.connect() as conexion:
            fila = conexion.execute(text("""
                SELECT estado, pais_aliado_propuesto, telefono_aliado_propuesto,
                       identificacion_aliado_propuesto
                FROM solicitud_convenio WHERE consecutivo = 'HT14-HISTORICA'
            """)).one()
            assert tuple(fila) == ("DEVUELTA", "País histórico", "5551234", "ID legado")
            assert conexion.scalar(text("SELECT identificacion FROM aliado")) == "900.123.456"

    migrar("upgrade", "head")
    despues = catalogo()
    assert set(anteriores).issubset(set(despues))
    assert len(despues) >= 250
    assert len({fila.codigo_iso for fila in despues}) == len(despues)
    assert len({fila.nombre.casefold() for fila in despues}) == len(despues)
    comprobar_historia()
    with motor.begin() as conexion:
        assert conexion.scalar(text("""
            SELECT pais_aliado_propuesto_id IS NULL AND solicitante_tipo_documento IS NULL
                AND solicitante_digito_verificacion IS NULL
                AND digito_verificacion_aliado_propuesto IS NULL
            FROM solicitud_convenio
        """))
        # Una referencia creada después del upgrade tampoco permite borrar el país.
        conexion.execute(text("""
            UPDATE solicitud_convenio SET pais_aliado_propuesto_id =
                (SELECT id FROM pais WHERE codigo_iso = 'BR')
        """))
    for sentencia in (
        "DELETE FROM pais WHERE codigo_iso = 'BR'",
        "DELETE FROM pais WHERE codigo_iso = 'ES'",
        "UPDATE solicitud_convenio SET pais_aliado_propuesto_id = -1",
        "UPDATE solicitud_convenio SET solicitante_tipo_documento = 'INVALIDO'",
        "UPDATE aliado SET digito_verificacion = 'x'",
        "INSERT INTO pais (codigo_iso, nombre) VALUES ('CO', 'Duplicado')",
    ):
        with pytest.raises(IntegrityError), motor.begin() as conexion:
            conexion.execute(text(sentencia))

    migrar("downgrade", "417e8d1cf636")
    assert catalogo() == despues  # También conserva CO preexistente y sin referencias.
    comprobar_historia()
    migrar("upgrade", "head")
    assert catalogo() == despues
    # Se prueba además la reversión de columnas, exclusivamente con datos sintéticos.
    migrar("downgrade", "a109c8f2b10b")
    assert catalogo() == despues
    comprobar_historia()
    migrar("upgrade", "head")
    assert catalogo() == despues
    comprobar_historia()
    columnas = {columna["name"] for columna in inspect(motor).get_columns("solicitud_convenio")}
    assert "pais_aliado_propuesto_id" in columnas
    with motor.connect() as conexion:
        assert conexion.scalar(text("SELECT version_num FROM alembic_version")) == "0b2fb1bed5b2"
