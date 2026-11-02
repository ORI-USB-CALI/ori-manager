"""HT-14. La identificación se guarda por su base: la búsqueda limpia el término
escrito (puntos, espacios y DV) solo al compararlo con la identificación."""

from uuid import uuid4

import pytest

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.validaciones import termino_busqueda_identificacion
from backend.models.aliado import Aliado
from backend.services.aliados import FiltrosAliado, ServicioAliados

URL_CONVENIOS = "/api/convenios"


@pytest.mark.parametrize(
    ("termino", "esperado"),
    [
        ("900123456", "900123456"),
        ("900.123.456", "900123456"),
        ("900 123 456", "900123456"),
        ("900.123.456-8", "900123456"),
        ("900123456 - 8", "900123456"),
        ("900.123", "900123"),  # búsqueda parcial
        ("Universidad", "Universidad"),
        ("CE-123", "CE-123"),
        ("SOL-00000026", "SOL-00000026"),
    ],
)
def test_limpia_el_termino_solo_cuando_parece_una_identificacion(termino, esperado):
    assert termino_busqueda_identificacion(termino) == esperado


@pytest.fixture
def base_unica() -> str:
    return f"9{uuid4().int % 10**8:08d}"


@pytest.fixture
def aliado(db, base_unica) -> Aliado:
    registro = Aliado(
        nombre=f"Universidad Búsqueda {uuid4().hex[:6]}",
        tipo="UNIVERSIDAD",
        tipo_identificacion="NIT",
        identificacion=base_unica,
        activo=True,
    )
    db.add(registro)
    db.commit()
    return registro


def _con_formato(base: str) -> str:
    return f"{base[:3]}.{base[3:6]}.{base[6:]}-7"


def test_busqueda_de_aliados_encuentra_el_nit_escrito_con_puntos_y_dv(db, aliado, base_unica):
    encontrados, total = ServicioAliados(db).listar(
        FiltrosAliado(buscar=_con_formato(base_unica))
    )

    assert total == 1
    assert encontrados[0].id == aliado.id


def test_busqueda_de_aliados_por_nombre_no_cambia(db, aliado):
    encontrados, total = ServicioAliados(db).listar(FiltrosAliado(buscar=aliado.nombre))

    assert total == 1
    assert encontrados[0].id == aliado.id


@pytest.fixture
def administrador(client, crear_usuario, entrar_como):
    usuario = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    entrar_como(usuario)
    return usuario


@pytest.fixture
def autor(crear_usuario):
    return crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)


def test_busqueda_de_convenios_por_nit_del_aliado_formal(
    db, client, administrador, autor, crear_convenio, aliado, base_unica
):
    convenio = crear_convenio(autor)
    convenio.aliado = aliado
    db.commit()

    cuerpo = client.get(URL_CONVENIOS, params={"buscar": _con_formato(base_unica)}).json()

    assert [item["id"] for item in cuerpo["items"]] == [convenio.id]


def test_busqueda_de_convenios_por_nit_propuesto_en_la_solicitud(
    db, client, administrador, autor, crear_convenio, base_unica
):
    convenio = crear_convenio(autor)
    convenio.solicitud.tipo_identificacion_aliado_propuesto = "NIT"
    convenio.solicitud.identificacion_aliado_propuesto = base_unica
    db.commit()

    cuerpo = client.get(URL_CONVENIOS, params={"buscar": _con_formato(base_unica)}).json()

    assert [item["id"] for item in cuerpo["items"]] == [convenio.id]
