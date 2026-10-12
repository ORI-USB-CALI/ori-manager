from collections.abc import Callable
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.models.usuario import Usuario

URL_CONVENIOS = "/api/convenios"


@pytest.fixture
def autor(crear_usuario) -> Usuario:
    """Gestor que crea los convenios de prueba. No inicia sesión."""
    return crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)


@pytest.fixture
def administrador(client, crear_usuario, entrar_como) -> Usuario:
    usuario = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    entrar_como(usuario)
    return usuario


@pytest.fixture
def formalizar(db: Session, crear_convenio) -> Callable[..., Convenio]:
    """Crea un convenio y lo lleva al estado dado con una fecha_firma,
    simulando el resultado de ServicioFirmas al completar el proceso de
    firmas (HU-15), sin pasar por el flujo completo."""

    def _crear(
        autor: Usuario,
        *,
        fecha_firma: date | None,
        estado: EstadoConvenio = EstadoConvenio.VIGENTE,
        **cambios,
    ) -> Convenio:
        convenio = crear_convenio(autor, fecha_firma=fecha_firma, **cambios)
        convenio.estado = estado.value
        db.commit()
        db.refresh(convenio)
        return convenio

    return _crear


def test_ca01_administrador_puede_filtrar_por_fecha(client, administrador, autor, crear_convenio) -> None:
    crear_convenio(autor)

    respuesta = client.get(
        URL_CONVENIOS,
        params={
            "tipo_fecha": "FORMALIZACION",
            "fecha_desde": "2026-01-01",
            "fecha_hasta": "2026-12-31",
        },
    )

    assert respuesta.status_code == 200


def test_ca02_filtra_por_fecha_de_formalizacion(client, administrador, autor, formalizar) -> None:
    termino = f"form-{uuid4().hex[:6]}"
    dentro = formalizar(
        autor, fecha_firma=date(2026, 6, 15), objeto=f"Convenio {termino} dentro del rango"
    )
    fuera = formalizar(
        autor, fecha_firma=date(2025, 1, 1), objeto=f"Convenio {termino} fuera del rango"
    )

    respuesta = client.get(
        URL_CONVENIOS,
        params={
            "buscar": termino,
            "tipo_fecha": "FORMALIZACION",
            "fecha_desde": "2026-01-01",
            "fecha_hasta": "2026-12-31",
        },
    )

    cuerpo = respuesta.json()
    ids = {item["id"] for item in cuerpo["items"]}
    assert dentro.id in ids
    assert fuera.id not in ids


def test_ca02_excluye_en_tramite_y_cancelado_aunque_tengan_fecha_firma(
    client, administrador, autor, formalizar
) -> None:
    termino = f"notform-{uuid4().hex[:6]}"
    en_tramite = formalizar(
        autor,
        fecha_firma=date(2026, 6, 15),
        estado=EstadoConvenio.EN_TRAMITE,
        objeto=f"Convenio {termino} en trámite con fecha diligenciada a mano",
    )
    cancelado = formalizar(
        autor,
        fecha_firma=date(2026, 6, 15),
        estado=EstadoConvenio.CANCELADO,
        objeto=f"Convenio {termino} cancelado",
    )

    respuesta = client.get(
        URL_CONVENIOS,
        params={
            "buscar": termino,
            "tipo_fecha": "FORMALIZACION",
            "fecha_desde": "2026-01-01",
            "fecha_hasta": "2026-12-31",
        },
    )

    cuerpo = respuesta.json()
    ids = {item["id"] for item in cuerpo["items"]}
    assert en_tramite.id not in ids
    assert cancelado.id not in ids


def test_ca03_filtra_por_vigencia_con_solapamiento(
    client, administrador, autor, crear_convenio
) -> None:
    termino = f"vig-{uuid4().hex[:6]}"
    contenido = crear_convenio(
        autor,
        objeto=f"Convenio {termino} contenido en el rango",
        fecha_inicio=date(2026, 6, 15),
        fecha_vencimiento=date(2026, 6, 20),
    )
    borde_inicio = crear_convenio(
        autor,
        objeto=f"Convenio {termino} inicia en el último día del rango",
        fecha_inicio=date(2026, 6, 30),
        fecha_vencimiento=date(2027, 12, 31),
    )
    vigencia_indefinida = crear_convenio(
        autor,
        objeto=f"Convenio {termino} sin fecha de vencimiento",
        fecha_inicio=date(2026, 1, 1),
        fecha_vencimiento=None,
    )
    vencio_antes = crear_convenio(
        autor,
        objeto=f"Convenio {termino} venció antes del rango",
        fecha_inicio=date(2026, 1, 1),
        fecha_vencimiento=date(2026, 5, 31),
    )
    inicia_despues = crear_convenio(
        autor,
        objeto=f"Convenio {termino} inicia después del rango",
        fecha_inicio=date(2026, 7, 1),
        fecha_vencimiento=date(2026, 12, 31),
    )
    sin_fecha_inicio = crear_convenio(
        autor, objeto=f"Convenio {termino} sin fecha de inicio", fecha_inicio=None
    )

    respuesta = client.get(
        URL_CONVENIOS,
        params={
            "buscar": termino,
            "tipo_fecha": "VIGENCIA",
            "fecha_desde": "2026-06-01",
            "fecha_hasta": "2026-06-30",
        },
    )

    cuerpo = respuesta.json()
    ids = {item["id"] for item in cuerpo["items"]}
    assert contenido.id in ids
    assert borde_inicio.id in ids
    assert vigencia_indefinida.id in ids
    assert vencio_antes.id not in ids
    assert inicia_despues.id not in ids
    assert sin_fecha_inicio.id not in ids


def test_ca04_tipo_fecha_aplica_el_rango_solo_a_ese_criterio(
    client, administrador, autor, formalizar
) -> None:
    """Un convenio formalizado en el rango pero con vigencia fuera de rango
    solo debe aparecer al filtrar por FORMALIZACION, no por VIGENCIA."""
    termino = f"tipo-{uuid4().hex[:6]}"
    convenio = formalizar(
        autor,
        fecha_firma=date(2026, 6, 15),
        objeto=f"Convenio {termino} formalizado en junio, vigente desde enero de 2020",
        fecha_inicio=date(2020, 1, 1),
        fecha_vencimiento=date(2020, 12, 31),
    )

    por_formalizacion = client.get(
        URL_CONVENIOS,
        params={
            "buscar": termino,
            "tipo_fecha": "FORMALIZACION",
            "fecha_desde": "2026-01-01",
            "fecha_hasta": "2026-12-31",
        },
    ).json()
    por_vigencia = client.get(
        URL_CONVENIOS,
        params={
            "buscar": termino,
            "tipo_fecha": "VIGENCIA",
            "fecha_desde": "2026-01-01",
            "fecha_hasta": "2026-12-31",
        },
    ).json()

    assert convenio.id in {item["id"] for item in por_formalizacion["items"]}
    assert convenio.id not in {item["id"] for item in por_vigencia["items"]}


def test_ca05_rango_invalido_devuelve_422(client, administrador) -> None:
    respuesta = client.get(
        URL_CONVENIOS,
        params={
            "tipo_fecha": "FORMALIZACION",
            "fecha_desde": "2026-12-31",
            "fecha_hasta": "2026-01-01",
        },
    )

    assert respuesta.status_code == 422


def test_ca06_limpiar_el_filtro_vuelve_a_mostrar_los_convenios_en_alcance(
    client, administrador, autor, crear_convenio
) -> None:
    termino = f"limpiar-{uuid4().hex[:6]}"
    convenio = crear_convenio(autor, objeto=f"Convenio {termino}")

    con_filtro = client.get(
        URL_CONVENIOS,
        params={
            "buscar": termino,
            "tipo_fecha": "VIGENCIA",
            "fecha_desde": "2099-01-01",
            "fecha_hasta": "2099-12-31",
        },
    ).json()
    sin_filtro = client.get(URL_CONVENIOS, params={"buscar": termino}).json()

    assert convenio.id not in {item["id"] for item in con_filtro["items"]}
    assert convenio.id in {item["id"] for item in sin_filtro["items"]}


def test_ca07_revisor_no_ve_formalizados_fuera_de_su_alcance(
    client, crear_usuario, entrar_como, autor, formalizar
) -> None:
    termino = f"alcance-{uuid4().hex[:6]}"
    formalizado = formalizar(
        autor, fecha_firma=date(2026, 6, 15), objeto=f"Convenio {termino} vigente"
    )
    revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)

    entrar_como(revisor)
    respuesta = client.get(
        URL_CONVENIOS,
        params={
            "buscar": termino,
            "tipo_fecha": "FORMALIZACION",
            "fecha_desde": "2026-01-01",
            "fecha_hasta": "2026-12-31",
        },
    )

    cuerpo = respuesta.json()
    assert formalizado.id not in {item["id"] for item in cuerpo["items"]}
