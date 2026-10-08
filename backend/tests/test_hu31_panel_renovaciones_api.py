from collections.abc import Callable
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.decision_no_renovacion import DecisionNoRenovacion
from backend.models.enums import (
    EstadoConvenio,
    EstadoSeguimientoRenovacion,
    TipoAliado,
    TipoIdentificacion,
)
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.services import renovaciones

URL_RENOVACIONES = "/api/convenios/renovaciones"
FECHA_REFERENCIA = date(2026, 10, 7)


@pytest.fixture(autouse=True)
def fecha_dominio_fija(monkeypatch) -> None:
    monkeypatch.setattr(
        renovaciones,
        "fecha_actual_dominio",
        lambda: FECHA_REFERENCIA,
    )


@pytest.fixture
def autor_convenios(crear_usuario) -> Usuario:
    return crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)


@pytest.fixture
def aliado_panel(db: Session) -> Aliado:
    aliado = Aliado(
        nombre="Universidad aliada HU-31",
        tipo=TipoAliado.UNIVERSIDAD.value,
        tipo_identificacion=TipoIdentificacion.NIT.value,
        identificacion=uuid4().hex,
    )
    db.add(aliado)
    db.commit()
    db.refresh(aliado)
    return aliado


@pytest.fixture
def crear_seguimiento(
    db: Session,
    autor_convenios: Usuario,
    aliado_panel: Aliado,
    crear_convenio,
) -> Callable[..., Convenio]:
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    assert tipo is not None

    def _crear(
        *,
        dias: int | None,
        estado: EstadoConvenio = EstadoConvenio.VIGENTE,
        codigo: str | None = None,
    ) -> Convenio:
        convenio = crear_convenio(
            autor_convenios,
            codigo=codigo,
            objeto="Convenio para seguimiento HU-31",
            tipo_convenio_id=tipo.id,
            fecha_inicio=date(2025, 1, 15),
            fecha_vencimiento=(
                FECHA_REFERENCIA + timedelta(days=dias) if dias is not None else None
            ),
        )
        convenio.aliado_id = aliado_panel.id
        convenio.estado = estado.value
        db.commit()
        db.refresh(convenio)
        return convenio

    return _crear


@pytest.fixture
def crear_hijo(
    db: Session, autor_convenios: Usuario, crear_convenio
) -> Callable[..., Convenio]:
    def _crear(
        origen: Convenio,
        estado: EstadoConvenio = EstadoConvenio.EN_TRAMITE,
    ) -> Convenio:
        hijo = crear_convenio(
            autor_convenios,
            codigo=f"REN-{uuid4().hex[:12]}",
            numero_renovacion=1,
        )
        hijo.convenio_origen_id = origen.id
        hijo.estado = estado.value
        db.commit()
        db.refresh(hijo)
        return hijo

    return _crear


def decidir_no_renovar(
    db: Session, convenio: Convenio, usuario: Usuario
) -> DecisionNoRenovacion:
    assert convenio.fecha_vencimiento is not None
    decision = DecisionNoRenovacion(
        convenio_id=convenio.id,
        fecha_vencimiento_origen=convenio.fecha_vencimiento,
        decidida_por_id=usuario.id,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


def consultar(client, estado: EstadoSeguimientoRenovacion | None = None):
    params = {"estado": estado.value} if estado is not None else None
    return client.get(URL_RENOVACIONES, params=params)


def test_pendientes_aplican_ventana_estados_y_fecha(
    client, gestor, crear_seguimiento
) -> None:
    limite = crear_seguimiento(dias=120)
    por_vencer = crear_seguimiento(dias=30, estado=EstadoConvenio.POR_VENCER)
    fuera = crear_seguimiento(dias=121)
    vencido = crear_seguimiento(dias=-1, estado=EstadoConvenio.VENCIDO)
    sin_fecha = crear_seguimiento(dias=None)

    respuesta = consultar(client, EstadoSeguimientoRenovacion.PENDIENTE_DE_DECISION)

    assert respuesta.status_code == 200
    ids = {item["convenio_id"] for item in respuesta.json()}
    assert ids == {limite.id, por_vencer.id}
    assert fuera.id not in ids
    assert vencido.id not in ids
    assert sin_fecha.id not in ids


def test_renovacion_iniciada_expone_hijo_y_sigue_visible_tras_vencimiento(
    client, gestor, crear_seguimiento, crear_hijo
) -> None:
    original = crear_seguimiento(dias=-15, estado=EstadoConvenio.VENCIDO)
    hijo = crear_hijo(original)

    respuesta = consultar(client, EstadoSeguimientoRenovacion.RENOVACION_INICIADA)

    assert respuesta.status_code == 200
    assert respuesta.json() == [
        {
            "convenio_id": original.id,
            "codigo": None,
            "objeto": "Convenio para seguimiento HU-31",
            "aliado": "Universidad aliada HU-31",
            "fecha_inicio": "2025-01-15",
            "fecha_vencimiento": "2026-09-22",
            "estado_convenio": "VENCIDO",
            "estado_seguimiento": "RENOVACION_INICIADA",
            "tipo_convenio": "Marco",
            "convenio_renovacion_id": hijo.id,
            "codigo_renovacion": hijo.codigo,
            "numero_renovacion": 1,
            "etapa_renovacion": "Elaboración",
        }
    ]
    assert consultar(
        client, EstadoSeguimientoRenovacion.PENDIENTE_DE_DECISION
    ).json() == []


def test_hijo_cancelado_no_cuenta_como_iniciada(
    client, gestor, crear_seguimiento, crear_hijo
) -> None:
    original = crear_seguimiento(dias=40)
    crear_hijo(original, EstadoConvenio.CANCELADO)

    assert consultar(
        client, EstadoSeguimientoRenovacion.RENOVACION_INICIADA
    ).json() == []
    pendientes = consultar(
        client, EstadoSeguimientoRenovacion.PENDIENTE_DE_DECISION
    ).json()
    assert [item["convenio_id"] for item in pendientes] == [original.id]


def test_decision_negativa_expone_estado_y_fecha_del_convenio(
    db, client, gestor, crear_seguimiento, autor_convenios
) -> None:
    original = crear_seguimiento(dias=75)
    decidir_no_renovar(db, original, autor_convenios)

    respuesta = consultar(client, EstadoSeguimientoRenovacion.NO_SE_RENOVARA)

    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 1
    item = respuesta.json()[0]
    assert item["convenio_id"] == original.id
    assert item["fecha_vencimiento"] == "2026-12-21"
    assert item["estado_seguimiento"] == "NO_SE_RENOVARA"
    assert consultar(
        client, EstadoSeguimientoRenovacion.PENDIENTE_DE_DECISION
    ).json() == []


def test_no_se_renovara_sigue_visible_despues_del_vencimiento(
    db, client, gestor, crear_seguimiento, autor_convenios
) -> None:
    original = crear_seguimiento(dias=-20, estado=EstadoConvenio.VENCIDO)
    decidir_no_renovar(db, original, autor_convenios)

    respuesta = consultar(client, EstadoSeguimientoRenovacion.NO_SE_RENOVARA)

    assert respuesta.status_code == 200
    assert [item["convenio_id"] for item in respuesta.json()] == [original.id]
    assert respuesta.json()[0]["fecha_vencimiento"] == "2026-09-17"


def test_hijo_activo_tiene_prioridad_sobre_decision_negativa(
    db, client, gestor, crear_seguimiento, crear_hijo, autor_convenios
) -> None:
    original = crear_seguimiento(dias=50)
    decidir_no_renovar(db, original, autor_convenios)
    hijo = crear_hijo(original)

    iniciadas = consultar(
        client, EstadoSeguimientoRenovacion.RENOVACION_INICIADA
    ).json()

    assert [(item["convenio_id"], item["convenio_renovacion_id"]) for item in iniciadas] == [
        (original.id, hijo.id)
    ]
    assert consultar(
        client, EstadoSeguimientoRenovacion.NO_SE_RENOVARA
    ).json() == []


def test_sin_filtro_devuelve_los_tres_estados_relevantes(
    db, client, gestor, crear_seguimiento, crear_hijo, autor_convenios
) -> None:
    pendiente = crear_seguimiento(dias=10)
    no_renovable = crear_seguimiento(dias=20)
    decidir_no_renovar(db, no_renovable, autor_convenios)
    iniciada = crear_seguimiento(dias=30)
    crear_hijo(iniciada)

    respuesta = consultar(client)

    assert respuesta.status_code == 200
    assert {
        (item["convenio_id"], item["estado_seguimiento"])
        for item in respuesta.json()
    } == {
        (pendiente.id, "PENDIENTE_DE_DECISION"),
        (no_renovable.id, "NO_SE_RENOVARA"),
        (iniciada.id, "RENOVACION_INICIADA"),
    }


@pytest.mark.parametrize(
    "estado",
    list(EstadoSeguimientoRenovacion),
)
def test_filtro_devuelve_unicamente_estado_solicitado(
    db,
    client,
    gestor,
    crear_seguimiento,
    crear_hijo,
    autor_convenios,
    estado: EstadoSeguimientoRenovacion,
) -> None:
    pendiente = crear_seguimiento(dias=10)
    no_renovable = crear_seguimiento(dias=20)
    decidir_no_renovar(db, no_renovable, autor_convenios)
    iniciada = crear_seguimiento(dias=30)
    crear_hijo(iniciada)
    esperado = {
        EstadoSeguimientoRenovacion.PENDIENTE_DE_DECISION: pendiente.id,
        EstadoSeguimientoRenovacion.NO_SE_RENOVARA: no_renovable.id,
        EstadoSeguimientoRenovacion.RENOVACION_INICIADA: iniciada.id,
    }

    respuesta = consultar(client, estado)

    assert respuesta.status_code == 200
    assert [item["convenio_id"] for item in respuesta.json()] == [esperado[estado]]
    assert {item["estado_seguimiento"] for item in respuesta.json()} == {estado.value}


def test_filtro_invalido_responde_422(client, gestor) -> None:
    respuesta = client.get(URL_RENOVACIONES, params={"estado": "DESCONOCIDO"})

    assert respuesta.status_code == 422


def test_ordena_por_vencimiento_y_id(client, gestor, crear_seguimiento) -> None:
    posterior = crear_seguimiento(dias=80)
    primero = crear_seguimiento(dias=25)
    segundo = crear_seguimiento(dias=25)

    respuesta = consultar(client)

    assert [item["convenio_id"] for item in respuesta.json()] == [
        primero.id,
        segundo.id,
        posterior.id,
    ]


def test_sin_resultados_devuelve_200_y_lista_vacia(client, gestor) -> None:
    respuesta = consultar(client)

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_gestor_puede_consultar(client, gestor) -> None:
    assert consultar(client).status_code == 200


def test_administrador_puede_consultar(client, crear_usuario, entrar_como) -> None:
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI))

    assert consultar(client).status_code == 200


def test_revisor_no_puede_consultar(client, crear_usuario, entrar_como) -> None:
    entrar_como(crear_usuario(CodigoRol.REVISOR_ORI))

    assert consultar(client).status_code == 403


@pytest.mark.parametrize(
    ("rol", "tipo"),
    [
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_solicitantes_no_pueden_consultar(
    client, crear_usuario, entrar_como, rol: CodigoRol, tipo: TipoUsuario
) -> None:
    entrar_como(crear_usuario(rol, tipo))

    assert consultar(client).status_code == 403


def test_sin_autenticacion_responde_401(client) -> None:
    assert consultar(client).status_code == 401
