"""HT-06 CA-08: control de argumentos, entorno y errores del procedimiento.

El comportamiento de la asignación se prueba en
test_ht06_regularizacion_codigos.py. Aquí se aísla el CLI con dobles, salvo en
las pruebas que comprueban que un rechazo no toca la base.
"""

from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from backend.cli import regularizar_codigos_convenio as cli
from backend.core.roles import CodigoRol
from backend.models.contador_codigo_convenio import ContadorCodigoConvenio
from backend.models.convenio import Convenio
from backend.services.regularizacion_codigos import ResultadoRegularizacion


@pytest.fixture
def entorno(monkeypatch):
    sesiones = []

    @contextmanager
    def nueva_sesion():
        sesion = Mock()
        sesiones.append(sesion)
        yield sesion

    regularizar = Mock(return_value=ResultadoRegularizacion((), (), False))
    pausa = Mock()
    monkeypatch.setattr(cli, "SessionLocal", nueva_sesion)
    monkeypatch.setattr(cli, "regularizar_codigos", regularizar)
    monkeypatch.setattr(cli, "sleep", pausa)
    monkeypatch.setattr(cli, "_originador", lambda *_: None)
    return regularizar, sesiones, pausa


def error_sql(estado):
    class ErrorPostgres(Exception):
        sqlstate = estado

    return OperationalError(
        "SQL confidencial", {"password": "secreto"}, ErrorPostgres()
    )


# --- Argumentos -----------------------------------------------------------


def test_simulacion_por_defecto_sin_politica_de_anio(entorno):
    regularizar, sesiones, _ = entorno

    assert cli.main(["--simular"]) == 0

    regularizar.assert_called_once_with(
        sesiones[0], anio_politica=None, originador=None, simular=True
    )


def test_inyecta_la_politica_de_anio(entorno):
    regularizar, sesiones, _ = entorno

    assert cli.main(["--simular", "--anio-politica", "2024"]) == 0

    regularizar.assert_called_once_with(
        sesiones[0], anio_politica=2024, originador=None, simular=True
    )


@pytest.mark.parametrize("valor", ["24", "20240", "abc", "-2024"])
def test_rechaza_un_anio_que_no_tiene_cuatro_digitos(entorno, valor, capsys):
    with pytest.raises(SystemExit) as salida:
        cli.main(["--simular", "--anio-politica", valor])

    assert salida.value.code == 2
    assert capsys.readouterr().err


# --- Guarda de entorno ----------------------------------------------------


@pytest.mark.parametrize(
    "app_env",
    ["development", "test", "staging", "production", "otro", "", "Development"],
)
@pytest.mark.parametrize("simular", [False, True])
def test_la_ejecucion_real_solo_se_permite_en_desarrollo_y_pruebas(
    entorno, monkeypatch, capsys, app_env, simular
):
    regularizar, sesiones, _ = entorno
    monkeypatch.setattr(cli.settings, "app_env", app_env)
    argumentos = ["--simular"] if simular else []

    permitida = simular or app_env in {"development", "test"}
    if permitida:
        assert cli.main(argumentos) == 0
        assert regularizar.call_count == 1
    else:
        with pytest.raises(SystemExit) as salida:
            cli.main(argumentos)
        assert salida.value.code == 2
        error = capsys.readouterr().err
        assert error
        # El rechazo no abre sesión ni filtra la contraseña de la base.
        assert sesiones == []
        assert regularizar.call_count == 0
        assert cli.settings.database_password.get_secret_value() not in error


def test_un_rechazo_de_entorno_no_toca_la_base(
    db, gestor, crear_convenio, monkeypatch, capsys
):
    convenio = crear_convenio(gestor)
    antes = {c.name: getattr(convenio, c.name) for c in Convenio.__table__.columns}
    # Relativo, no absoluto: el contador es global y otras pruebas de la suite
    # confirman consecutivos de verdad.
    contadores_antes = db.scalar(
        select(func.count()).select_from(ContadorCodigoConvenio)
    )
    monkeypatch.setattr(cli.settings, "app_env", "production")
    monkeypatch.setattr(
        cli,
        "SessionLocal",
        Mock(side_effect=AssertionError("Un rechazo no debe abrir sesión")),
    )

    with pytest.raises(SystemExit) as salida:
        cli.main([])

    assert salida.value.code == 2
    capsys.readouterr()
    db.refresh(convenio)
    assert {
        c.name: getattr(convenio, c.name) for c in Convenio.__table__.columns
    } == antes
    assert (
        db.scalar(select(func.count()).select_from(ContadorCodigoConvenio))
        == contadores_antes
    )


# --- Autorización ---------------------------------------------------------


def test_exige_que_el_autorizante_exista(db, monkeypatch, capsys):
    monkeypatch.setattr(cli.settings, "app_env", "test")

    with pytest.raises(SystemExit) as salida:
        cli._originador(db, 999999, cli.argparse.ArgumentParser())

    assert salida.value.code == 2
    assert "999999" in capsys.readouterr().err


def test_solo_un_administrador_puede_autorizar(db, gestor, capsys):
    with pytest.raises(SystemExit) as salida:
        cli._originador(db, gestor.id, cli.argparse.ArgumentParser())

    assert salida.value.code == 2
    assert "ADMINISTRADOR_ORI" in capsys.readouterr().err


def test_un_administrador_queda_como_originador(db, crear_usuario):
    administrador = crear_usuario(codigo_rol=CodigoRol.ADMINISTRADOR_ORI)

    originador = cli._originador(db, administrador.id, cli.argparse.ArgumentParser())

    assert originador is not None
    assert originador.id == administrador.id


def test_sin_autorizante_no_se_inventa_uno(db):
    assert cli._originador(db, None, cli.argparse.ArgumentParser()) is None


# --- Errores y reintentos -------------------------------------------------


def test_reintenta_un_error_transitorio(entorno, monkeypatch):
    regularizar, _, pausa = entorno
    monkeypatch.setattr(cli.settings, "app_env", "test")
    regularizar.side_effect = [
        error_sql("40P01"),
        ResultadoRegularizacion((), (), False),
    ]

    assert cli.main([]) == 0
    assert [llamada.args[0] for llamada in pausa.call_args_list] == [2]


def test_no_reintenta_un_error_permanente(entorno, monkeypatch):
    regularizar, _, pausa = entorno
    monkeypatch.setattr(cli.settings, "app_env", "test")
    regularizar.side_effect = error_sql("42P01")

    assert cli.main([]) == 1
    assert pausa.call_count == 0


def test_agota_los_reintentos_y_no_expone_secretos(entorno, monkeypatch, caplog):
    regularizar, _, pausa = entorno
    monkeypatch.setattr(cli.settings, "app_env", "test")
    regularizar.side_effect = error_sql("40P01")

    with caplog.at_level("ERROR"):
        assert cli.main([]) == 1

    assert [llamada.args[0] for llamada in pausa.call_args_list] == [2, 4]
    assert "secreto" not in caplog.text
    assert "SQL confidencial" not in caplog.text
    assert cli.settings.database_password.get_secret_value() not in caplog.text
