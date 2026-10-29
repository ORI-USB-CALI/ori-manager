"""HU-39 BE01. La guía de radicación reutiliza el contrato de guías de HU-38.

Verifica que ``GUIA_RADICACION`` se guarda en la misma tabla y API que el
onboarding, pero con un estado independiente (RN-02), con las mismas reglas de
finalización y omisión (RN-04, RN-05) y aislado por usuario.
"""

import itertools

import pytest
from sqlalchemy import func, inspect, select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.enums import CodigoGuia
from backend.models.estado_guia_usuario import EstadoGuiaUsuario
from backend.models.solicitud_convenio import SolicitudConvenio

URL_GUIAS = "/api/guias"
URL_RADICACION = f"{URL_GUIAS}/GUIA_RADICACION"
URL_ONBOARDING = f"{URL_GUIAS}/ONBOARDING_INICIAL"

SOLICITANTES = [
    pytest.param((CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO), id="interno"),
    pytest.param((CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO), id="externo"),
]


@pytest.fixture(params=SOLICITANTES)
def solicitante(request, crear_usuario, entrar_como):
    usuario = crear_usuario(*request.param)
    entrar_como(usuario)
    return usuario


def _guardar(client, url, estado, version=1):
    respuesta = client.put(url, json={"estado": estado, "version": version})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _estados(client):
    return {guia["guia"]: guia["estado"] for guia in client.get(URL_GUIAS).json()}


def _registros(db, usuario):
    return {
        registro.guia: (registro.estado, registro.version)
        for registro in db.scalars(
            select(EstadoGuiaUsuario).where(EstadoGuiaUsuario.usuario_id == usuario.id)
        )
    }


# --- Identificador acordado (contrato con el motor del frontend) ---------------


def test_el_identificador_de_la_guia_es_guia_radicacion():
    # Mismo identificador que usa el TourProvider de HU-38 FE-01.
    assert CodigoGuia.GUIA_RADICACION.value == "GUIA_RADICACION"
    assert CodigoGuia("GUIA_RADICACION") is CodigoGuia.GUIA_RADICACION


@pytest.mark.parametrize("metodo", ["get", "put"])
def test_sin_sesion_responde_401(client, metodo):
    if metodo == "put":
        respuesta = client.put(
            URL_RADICACION, json={"estado": "COMPLETADO", "version": 1}
        )
    else:
        respuesta = client.get(URL_RADICACION)
    assert respuesta.status_code == 401


def test_guia_nueva_esta_pendiente(client, solicitante):
    assert client.get(URL_RADICACION).json() == {
        "guia": "GUIA_RADICACION",
        "estado": "PENDIENTE",
        "version": None,
        "actualizado_en": None,
    }


# --- Finalización y omisión (RN-04, RN-05) ---------------------------------------


@pytest.mark.parametrize("estado", ["COMPLETADO", "OMITIDO"])
def test_finalizar_u_omitir_desde_pendiente(client, db, solicitante, estado):
    cuerpo = _guardar(client, URL_RADICACION, estado, version=3)

    assert cuerpo["guia"] == "GUIA_RADICACION"
    assert cuerpo["estado"] == estado
    assert cuerpo["version"] == 3
    assert cuerpo["actualizado_en"] is not None
    assert _registros(db, solicitante) == {"GUIA_RADICACION": (estado, 3)}


def test_cerrar_una_reproduccion_no_modifica_la_guia_completada(
    client, db, solicitante
):
    _guardar(client, URL_RADICACION, "COMPLETADO")

    cuerpo = _guardar(client, URL_RADICACION, "OMITIDO", version=2)

    assert cuerpo["estado"] == "COMPLETADO"
    assert _registros(db, solicitante) == {"GUIA_RADICACION": ("COMPLETADO", 1)}


def test_completar_una_guia_omitida_la_marca_completada(client, db, solicitante):
    _guardar(client, URL_RADICACION, "OMITIDO")

    cuerpo = _guardar(client, URL_RADICACION, "COMPLETADO", version=2)

    assert cuerpo["estado"] == "COMPLETADO"
    assert _registros(db, solicitante) == {"GUIA_RADICACION": ("COMPLETADO", 2)}


def test_omitir_varias_veces_no_crea_registros(client, db, solicitante):
    primero = _guardar(client, URL_RADICACION, "OMITIDO")
    segundo = _guardar(client, URL_RADICACION, "OMITIDO")

    assert segundo == primero
    assert len(_registros(db, solicitante)) == 1


# --- Independencia del onboarding (RN-02) -----------------------------------------


@pytest.mark.parametrize(
    ("estado_onboarding", "estado_radicacion"),
    list(itertools.product(["PENDIENTE", "COMPLETADO", "OMITIDO"], repeat=2)),
)
def test_cada_guia_conserva_su_propio_estado(
    client, solicitante, estado_onboarding, estado_radicacion
):
    if estado_onboarding != "PENDIENTE":
        _guardar(client, URL_ONBOARDING, estado_onboarding)
    if estado_radicacion != "PENDIENTE":
        _guardar(client, URL_RADICACION, estado_radicacion)

    assert _estados(client) == {
        "ONBOARDING_INICIAL": estado_onboarding,
        "GUIA_RADICACION": estado_radicacion,
    }
    assert client.get(URL_ONBOARDING).json()["estado"] == estado_onboarding
    assert client.get(URL_RADICACION).json()["estado"] == estado_radicacion


def test_completar_la_guia_no_modifica_un_onboarding_omitido(client, db, solicitante):
    _guardar(client, URL_ONBOARDING, "OMITIDO", version=1)

    _guardar(client, URL_RADICACION, "COMPLETADO", version=4)

    assert _registros(db, solicitante) == {
        "ONBOARDING_INICIAL": ("OMITIDO", 1),
        "GUIA_RADICACION": ("COMPLETADO", 4),
    }


def test_omitir_el_onboarding_no_reabre_la_guia(client, solicitante):
    _guardar(client, URL_RADICACION, "COMPLETADO")

    _guardar(client, URL_ONBOARDING, "OMITIDO")
    _guardar(client, URL_ONBOARDING, "COMPLETADO")

    assert client.get(URL_RADICACION).json()["estado"] == "COMPLETADO"


# --- Aislamiento por usuario y persistencia ----------------------------------------


def test_un_usuario_no_ve_ni_modifica_la_guia_de_otro(
    client, db, crear_usuario, entrar_como
):
    interno = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)
    externo = crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)
    entrar_como(interno)
    _guardar(client, URL_RADICACION, "OMITIDO")

    entrar_como(externo)
    assert client.get(URL_RADICACION).json()["estado"] == "PENDIENTE"
    _guardar(client, URL_RADICACION, "COMPLETADO")

    entrar_como(interno)
    assert client.get(URL_RADICACION).json()["estado"] == "OMITIDO"
    assert _registros(db, interno) == {"GUIA_RADICACION": ("OMITIDO", 1)}
    assert _registros(db, externo) == {"GUIA_RADICACION": ("COMPLETADO", 1)}


def test_el_cuerpo_no_admite_elegir_otro_usuario(
    client, db, solicitante, crear_usuario
):
    otro = crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)

    respuesta = client.put(
        URL_RADICACION,
        json={"estado": "COMPLETADO", "version": 1, "usuario_id": otro.id},
    )

    assert respuesta.status_code == 422
    assert _registros(db, otro) == {}


def test_el_estado_se_conserva_en_una_nueva_sesion(client, solicitante, entrar_como):
    _guardar(client, URL_RADICACION, "COMPLETADO")

    entrar_como(solicitante)

    assert client.get(URL_RADICACION).json()["estado"] == "COMPLETADO"


# --- Sin un segundo sistema de persistencia ni efectos sobre la solicitud ----------


def test_usa_la_tabla_de_guias_de_hu38(db, solicitante, client):
    _guardar(client, URL_RADICACION, "OMITIDO")

    tablas = set(inspect(db.get_bind()).get_table_names())

    assert "estado_guia_usuario" in tablas
    # Ninguna tabla adicional para la guía de radicación.
    assert not {tabla for tabla in tablas if "radicacion" in tabla or "tour" in tabla}
    assert (
        db.scalar(
            select(func.count())
            .select_from(EstadoGuiaUsuario)
            .where(
                EstadoGuiaUsuario.usuario_id == solicitante.id,
                EstadoGuiaUsuario.guia == "GUIA_RADICACION",
            )
        )
        == 1
    )


@pytest.mark.parametrize("estado", ["COMPLETADO", "OMITIDO"])
def test_registrar_la_guia_no_modifica_la_solicitud_en_curso(
    client, db, solicitante, estado
):
    # CA-07: la guía es informativa; guardar su estado no toca el formulario.
    creada = client.post("/api/solicitudes", json={"objeto": "Borrador en curso"})
    assert creada.status_code == 201, creada.text
    antes = client.get(f"/api/solicitudes/{creada.json()['id']}").json()
    auditoria = db.scalar(select(func.count()).select_from(Auditoria))
    solicitudes = db.scalar(select(func.count()).select_from(SolicitudConvenio))

    _guardar(client, URL_RADICACION, estado)

    assert client.get(f"/api/solicitudes/{creada.json()['id']}").json() == antes
    assert db.scalar(select(func.count()).select_from(SolicitudConvenio)) == solicitudes
    assert db.scalar(select(func.count()).select_from(Auditoria)) == auditoria
