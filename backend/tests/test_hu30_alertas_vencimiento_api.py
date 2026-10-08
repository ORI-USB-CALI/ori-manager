from collections.abc import Callable
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.decision_no_renovacion import DecisionNoRenovacion
from backend.models.enums import EstadoConvenio, EstadoSeguimientoRenovacion
from backend.models.usuario import Usuario
from backend.services import alertas_vencimiento, renovaciones

URL_ALERTAS = "/api/convenios/alertas-vencimiento"
FECHA_REFERENCIA = date(2026, 10, 7)


@pytest.fixture(autouse=True)
def fecha_dominio_fija(monkeypatch) -> None:
    monkeypatch.setattr(
        alertas_vencimiento,
        "_fecha_actual_dominio",
        lambda: FECHA_REFERENCIA,
    )
    monkeypatch.setattr(renovaciones, "fecha_actual_dominio", lambda: FECHA_REFERENCIA)


@pytest.fixture
def autor_convenios(crear_usuario) -> Usuario:
    return crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)


@pytest.fixture
def crear_alerta(
    db: Session, autor_convenios: Usuario, crear_convenio
) -> Callable[..., Convenio]:
    def _crear(
        *,
        dias: int,
        estado: EstadoConvenio = EstadoConvenio.VIGENTE,
        codigo: str | None = None,
        objeto: str = "Convenio de cooperación HU-30",
    ) -> Convenio:
        convenio = crear_convenio(
            autor_convenios,
            codigo=codigo,
            objeto=objeto,
            fecha_vencimiento=FECHA_REFERENCIA + timedelta(days=dias),
        )
        convenio.estado = estado.value
        db.commit()
        db.refresh(convenio)
        return convenio

    return _crear


def test_gestor_puede_consultar_alertas(client, gestor) -> None:
    respuesta = client.get(URL_ALERTAS)

    assert respuesta.status_code == 200


def test_administrador_puede_consultar_alertas(
    client, crear_usuario, entrar_como
) -> None:
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI))

    respuesta = client.get(URL_ALERTAS)

    assert respuesta.status_code == 200


def test_revisor_no_puede_consultar_alertas(client, crear_usuario, entrar_como) -> None:
    entrar_como(crear_usuario(CodigoRol.REVISOR_ORI))

    respuesta = client.get(URL_ALERTAS)

    assert respuesta.status_code == 403


@pytest.mark.parametrize(
    ("rol", "tipo"),
    [
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_solicitantes_no_pueden_consultar_alertas(
    client, crear_usuario, entrar_como, rol: CodigoRol, tipo: TipoUsuario
) -> None:
    entrar_como(crear_usuario(rol, tipo))

    respuesta = client.get(URL_ALERTAS)

    assert respuesta.status_code == 403


def test_sin_autenticacion_responde_401(client) -> None:
    respuesta = client.get(URL_ALERTAS)

    assert respuesta.status_code == 401


def test_respuesta_expone_contrato_y_codigo_nullable(
    client, gestor, crear_alerta
) -> None:
    convenio = crear_alerta(dias=12, codigo=None, objeto="Convenio identificable")

    respuesta = client.get(URL_ALERTAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == [
        {
            "convenio_id": convenio.id,
            "codigo": None,
            "objeto": "Convenio identificable",
            "fecha_vencimiento": "2026-10-19",
            "dias_restantes": 12,
            "rango_vencimiento": "0_30",
        }
    ]


def test_sin_convenios_proximos_devuelve_lista_vacia(
    client, gestor, crear_alerta
) -> None:
    crear_alerta(dias=121)
    crear_alerta(dias=-1, estado=EstadoConvenio.VENCIDO)

    respuesta = client.get(URL_ALERTAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_serializa_los_cuatro_rangos(client, gestor, crear_alerta) -> None:
    for dias in (15, 45, 75, 105):
        crear_alerta(dias=dias)

    respuesta = client.get(URL_ALERTAS)

    assert respuesta.status_code == 200
    assert [item["rango_vencimiento"] for item in respuesta.json()] == [
        "0_30",
        "31_60",
        "61_90",
        "91_120",
    ]


def test_mantiene_orden_por_fecha_e_id(client, gestor, crear_alerta) -> None:
    mas_tarde = crear_alerta(dias=60)
    primero = crear_alerta(dias=30)
    segundo = crear_alerta(dias=30)

    respuesta = client.get(URL_ALERTAS)

    assert [item["convenio_id"] for item in respuesta.json()] == [
        primero.id,
        segundo.id,
        mas_tarde.id,
    ]


def test_endpoint_no_modifica_convenio_ni_genera_auditoria(
    db, client, gestor, crear_alerta
) -> None:
    convenio = crear_alerta(dias=20, estado=EstadoConvenio.POR_VENCER)
    estado_inicial = convenio.estado
    fecha_inicial = convenio.fecha_vencimiento
    actualizado_inicial = convenio.actualizado_en
    auditorias_iniciales = db.scalar(select(func.count()).select_from(Auditoria))

    assert client.get(URL_ALERTAS).status_code == 200

    db.refresh(convenio)
    assert convenio.estado == estado_inicial
    assert convenio.fecha_vencimiento == fecha_inicial
    assert convenio.actualizado_en == actualizado_inicial
    assert (
        db.scalar(select(func.count()).select_from(Auditoria)) == auditorias_iniciales
    )


def test_consulta_posterior_refleja_cambio_de_fecha(
    db, client, gestor, crear_alerta
) -> None:
    convenio = crear_alerta(dias=20)

    primera = client.get(URL_ALERTAS)
    assert primera.json()[0]["rango_vencimiento"] == "0_30"

    convenio.fecha_vencimiento = FECHA_REFERENCIA + timedelta(days=75)
    db.commit()

    segunda = client.get(URL_ALERTAS)
    assert segunda.json() == [
        {
            "convenio_id": convenio.id,
            "codigo": None,
            "objeto": "Convenio de cooperación HU-30",
            "fecha_vencimiento": "2026-12-21",
            "dias_restantes": 75,
            "rango_vencimiento": "61_90",
        }
    ]


@pytest.mark.parametrize(
    ("accion", "seguimiento"),
    [
        ("no-renovar", EstadoSeguimientoRenovacion.NO_SE_RENOVARA),
        ("renovaciones", EstadoSeguimientoRenovacion.RENOVACION_INICIADA),
    ],
)
@pytest.mark.parametrize("estado", [EstadoConvenio.VIGENTE, EstadoConvenio.POR_VENCER])
def test_decision_oculta_alerta_sin_modificar_original(
    db, client, gestor, crear_alerta, accion, seguimiento, estado
) -> None:
    convenio = crear_alerta(dias=30, estado=estado)
    original = {
        columna.name: getattr(convenio, columna.name)
        for columna in Convenio.__table__.columns
    }
    assert convenio.id in {
        item["convenio_id"] for item in client.get(URL_ALERTAS).json()
    }

    respuesta = client.post(f"/api/convenios/{convenio.id}/{accion}")

    assert respuesta.status_code == 201
    assert convenio.id not in {
        item["convenio_id"] for item in client.get(URL_ALERTAS).json()
    }
    panel = client.get("/api/convenios/renovaciones")
    assert panel.status_code == 200
    assert next(
        item["estado_seguimiento"]
        for item in panel.json() if item["convenio_id"] == convenio.id
    ) == seguimiento.value
    db.refresh(convenio)
    assert {
        columna.name: getattr(convenio, columna.name)
        for columna in Convenio.__table__.columns
    } == original
    if accion == "no-renovar":
        decision = db.scalar(select(DecisionNoRenovacion).where(
            DecisionNoRenovacion.convenio_id == convenio.id
        ))
        assert decision.fecha_vencimiento_origen == convenio.fecha_vencimiento
        assert decision.decidida_por_id == gestor.id


@pytest.mark.parametrize("decision_negativa", [False, True])
def test_cancelacion_reabre_alerta_solo_sin_decision_vigente(
    db, client, gestor, crear_alerta, decision_negativa
) -> None:
    convenio = crear_alerta(dias=30)
    if decision_negativa:
        assert client.post(f"/api/convenios/{convenio.id}/no-renovar").status_code == 201
    respuesta = client.post(f"/api/convenios/{convenio.id}/renovaciones")
    assert respuesta.status_code == 201
    hijo = db.get(Convenio, respuesta.json()["convenio_renovacion_id"])
    assert convenio.id not in {
        item["convenio_id"] for item in client.get(URL_ALERTAS).json()
    }

    hijo.estado = EstadoConvenio.CANCELADO.value
    db.commit()

    assert (convenio.id in {
        item["convenio_id"] for item in client.get(URL_ALERTAS).json()
    }) is (not decision_negativa)
    if decision_negativa:
        assert db.scalar(select(DecisionNoRenovacion.id).where(
            DecisionNoRenovacion.convenio_id == convenio.id,
            DecisionNoRenovacion.fecha_vencimiento_origen == convenio.fecha_vencimiento,
        )) is not None


def test_decision_de_periodo_anterior_no_silencia_nuevo_vencimiento(
    db, client, gestor, crear_alerta
) -> None:
    convenio = crear_alerta(dias=30)
    assert client.post(f"/api/convenios/{convenio.id}/no-renovar").status_code == 201
    decision = db.scalar(select(DecisionNoRenovacion).where(
        DecisionNoRenovacion.convenio_id == convenio.id
    ))
    historica = {
        columna.name: getattr(decision, columna.name)
        for columna in DecisionNoRenovacion.__table__.columns
    }
    assert convenio.id not in {
        item["convenio_id"] for item in client.get(URL_ALERTAS).json()
    }

    convenio.fecha_vencimiento = FECHA_REFERENCIA + timedelta(days=75)
    db.commit()

    alerta = next(
        item for item in client.get(URL_ALERTAS).json()
        if item["convenio_id"] == convenio.id
    )
    assert alerta["dias_restantes"] == 75
    assert alerta["rango_vencimiento"] == "61_90"
    db.refresh(decision)
    assert {
        columna.name: getattr(decision, columna.name)
        for columna in DecisionNoRenovacion.__table__.columns
    } == historica
