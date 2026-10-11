from contextlib import contextmanager
from datetime import date
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from backend.cli import conciliar_convenios as cli
from backend.models.convenio import Convenio
from backend.models.transicion_estado_convenio import TransicionEstadoConvenio
from backend.services.ciclo_vida_convenios import ResultadoConciliacion


@pytest.fixture
def entorno(monkeypatch):
    sesiones = []

    @contextmanager
    def nueva_sesion():
        sesion = Mock()
        sesiones.append(sesion)
        yield sesion

    conciliar = Mock(
        return_value=ResultadoConciliacion(date(2026, 10, 8), (), (), (), False)
    )
    pausa = Mock()
    monkeypatch.setattr(cli, "SessionLocal", nueva_sesion)
    monkeypatch.setattr(cli, "conciliar_estados", conciliar)
    monkeypatch.setattr(cli, "sleep", pausa)
    monkeypatch.setattr(cli, "fecha_actual_dominio", lambda: date(2026, 10, 8))
    return conciliar, sesiones, pausa


def error_sql(estado):
    class ErrorPostgres(Exception):
        sqlstate = estado

    return OperationalError(
        "SQL confidencial", {"password": "secreto"}, ErrorPostgres()
    )


def test_cli_inyecta_fecha_y_simulacion(entorno):
    conciliar, sesiones, _ = entorno
    assert cli.main(["--simular", "--fecha-referencia", "2026-10-07"]) == 0
    conciliar.assert_called_once_with(sesiones[0], date(2026, 10, 7), simular=True)


@pytest.mark.parametrize(
    "app_env",
    ["development", "test", "staging", "production", "otro", "", "Development"],
)
@pytest.mark.parametrize("personalizada", [False, True])
@pytest.mark.parametrize("simular", [False, True])
def test_combinaciones_de_entorno_fecha_y_simulacion(
    entorno, monkeypatch, capsys, app_env, personalizada, simular
):
    conciliar, sesiones, pausa = entorno
    monkeypatch.setattr(cli.settings, "app_env", app_env)
    argumentos = ["--fecha-referencia", "2026-10-07"] if personalizada else []
    if simular:
        argumentos.append("--simular")

    if personalizada and not simular and app_env not in {"development", "test"}:
        with pytest.raises(SystemExit) as rechazo:
            cli.main(argumentos)
        assert rechazo.value.code == 2
        assert not sesiones
        conciliar.assert_not_called()
        pausa.assert_not_called()
        error = capsys.readouterr().err
        assert "error:" in error
        assert "development o test" in error
        assert "--simular" in error
        assert "America/Bogota" in error
        assert cli.settings.database_password.get_secret_value() not in error
    else:
        assert cli.main(argumentos) == 0
        assert len(sesiones) == 1
        conciliar.assert_called_once_with(
            sesiones[0], date(2026, 10, 7 if personalizada else 8), simular=simular
        )


@pytest.mark.parametrize("app_env", ["staging", "production", "otro"])
def test_rechazo_no_abre_sesion_ni_modifica_registros(
    db, crear_usuario, crear_convenio, monkeypatch, app_env
):
    convenio = crear_convenio(crear_usuario(), fecha_vencimiento=date(2026, 10, 7))
    convenio.estado = "VIGENTE"
    db.commit()
    antes = {
        columna.name: getattr(convenio, columna.name)
        for columna in Convenio.__table__.columns
    }
    transiciones = db.scalar(select(func.count()).select_from(TransicionEstadoConvenio))
    abrir_sesion = Mock(side_effect=AssertionError("Un rechazo no debe abrir sesión"))
    conciliar = Mock(side_effect=AssertionError("Un rechazo no debe conciliar"))
    fecha_actual = Mock(
        side_effect=AssertionError("Validar antes de resolver la fecha")
    )
    monkeypatch.setattr(cli.settings, "app_env", app_env)
    monkeypatch.setattr(cli, "SessionLocal", abrir_sesion)
    monkeypatch.setattr(cli, "conciliar_estados", conciliar)
    monkeypatch.setattr(cli, "fecha_actual_dominio", fecha_actual)

    with pytest.raises(SystemExit) as rechazo:
        cli.main(["--fecha-referencia", "2026-10-08"])

    assert rechazo.value.code == 2
    abrir_sesion.assert_not_called()
    conciliar.assert_not_called()
    fecha_actual.assert_not_called()
    db.refresh(convenio)
    assert {
        columna.name: getattr(convenio, columna.name)
        for columna in Convenio.__table__.columns
    } == antes
    assert (
        db.scalar(select(func.count()).select_from(TransicionEstadoConvenio))
        == transiciones
    )


def test_reintenta_con_sesion_nueva_y_fecha_fija(entorno):
    conciliar, sesiones, pausa = entorno
    resultado = conciliar.return_value
    conciliar.side_effect = [error_sql("40P01"), resultado]
    assert cli.main([]) == 0
    assert len(sesiones) == 2
    assert [llamada.args[1] for llamada in conciliar.call_args_list] == [
        date(2026, 10, 8)
    ] * 2
    pausa.assert_called_once_with(2)


def test_agota_reintentos_y_no_expone_secretos(entorno, caplog):
    conciliar, sesiones, pausa = entorno
    conciliar.side_effect = error_sql("55P03")
    assert cli.main([]) == 1
    assert len(sesiones) == 3
    assert [llamada.args[0] for llamada in pausa.call_args_list] == [2, 4]
    assert "secreto" not in caplog.text
    assert "SQL confidencial" not in caplog.text


def test_error_permanente_no_se_reintenta(entorno):
    conciliar, sesiones, pausa = entorno
    conciliar.side_effect = error_sql("42P01")
    assert cli.main([]) == 1
    assert len(sesiones) == 1
    pausa.assert_not_called()


def test_error_conexion_sin_sqlstate_tambien_reintenta(entorno):
    conciliar, sesiones, pausa = entorno
    resultado = conciliar.return_value
    conciliar.side_effect = [error_sql(None), resultado]
    assert cli.main([]) == 0
    assert len(sesiones) == 2
    pausa.assert_called_once_with(2)
