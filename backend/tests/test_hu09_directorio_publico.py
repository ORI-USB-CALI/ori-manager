"""HU-09: directorio público de convenios vigentes."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.api.routers import directorio_publico
from backend.models.aliado import Aliado
from backend.models.enums import EstadoConvenio, TipoAliado, TipoIdentificacion
from backend.models.tipo_convenio import TipoConvenio

URL = "/api/public/directorio-convenios"
HOY = date(2027, 3, 15)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(directorio_publico, "fecha_actual_dominio", lambda: HOY)


@pytest.fixture
def crear_formalizado(db, gestor, crear_convenio):
    """Convenio formalizado con aliado, tipo y vigencia; el código lo identifica."""
    tipo_id = db.scalar(select(TipoConvenio.id).where(TipoConvenio.codigo == "MARCO"))

    def crear(
        estado="VIGENTE",
        inicio=date(2027, 1, 1),
        vencimiento=date(2027, 12, 31),
        firma=date(2026, 12, 1),
    ):
        aliado = Aliado(
            nombre="Universidad Pública Aliada",
            tipo=TipoAliado.UNIVERSIDAD.value,
            tipo_identificacion=TipoIdentificacion.NIT.value,
            identificacion=f"8{uuid4().int % 10**8:08d}",
        )
        db.add(aliado)
        db.flush()
        convenio = crear_convenio(
            gestor,
            objeto="Movilidad académica",
            tipo_convenio_id=tipo_id,
        )
        convenio.aliado = aliado
        convenio.implicacion_financiera = "Dato interno"
        convenio.codigo = f"PUB-{uuid4().hex[:10]}"
        convenio.estado = estado
        convenio.fecha_firma = firma
        convenio.fecha_inicio = inicio
        convenio.fecha_vencimiento = vencimiento
        db.commit()
        return convenio

    return crear


def publicados(client):
    client.cookies.clear()  # CA-01/CA-07: sin sesión
    respuesta = client.get(URL, params={"limite": 50})
    assert respuesta.status_code == 200, respuesta.text
    return {item["codigo"]: item for item in respuesta.json()["items"]}


def test_sin_sesion_muestra_solo_campos_publicos(client, crear_formalizado):
    convenio = crear_formalizado()
    item = publicados(client)[convenio.codigo]
    assert item == {
        "codigo": convenio.codigo,
        "aliado": "Universidad Pública Aliada",
        "tipo_convenio": item["tipo_convenio"],
        "objeto": "Movilidad académica",
        "fecha_inicio": "2027-01-01",
        "fecha_vencimiento": "2027-12-31",
        "estado": "VIGENTE",
    }
    assert item["tipo_convenio"]


def test_por_vencer_se_publica_como_vigente(client, crear_formalizado):
    convenio = crear_formalizado(estado="POR_VENCER")
    assert publicados(client)[convenio.codigo]["estado"] == "VIGENTE"


@pytest.mark.parametrize(
    "estado",
    [e.value for e in EstadoConvenio if e.value not in ("VIGENTE", "POR_VENCER")],
)
def test_excluye_estados_no_vigentes(client, crear_formalizado, estado):
    convenio = crear_formalizado(estado=estado)
    assert convenio.codigo not in publicados(client)


def test_excluye_no_formalizado(client, crear_formalizado):
    convenio = crear_formalizado(firma=None)
    assert convenio.codigo not in publicados(client)


@pytest.mark.parametrize(
    ("inicio", "vencimiento", "visible"),
    [
        (date(2027, 1, 1), HOY, True),  # vence hoy: inclusivo
        (HOY, date(2027, 12, 31), True),  # empieza hoy: inclusivo
        (
            date(2026, 1, 1),
            date(2027, 3, 14),
            False,
        ),  # venció ayer y sigue VIGENTE (CA-04)
        (date(2027, 3, 16), date(2027, 12, 31), False),  # aún no empieza
        (None, date(2027, 12, 31), True),
        (date(2027, 1, 1), None, False),
    ],
)
def test_periodo_de_vigencia(client, crear_formalizado, inicio, vencimiento, visible):
    convenio = crear_formalizado(inicio=inicio, vencimiento=vencimiento)
    assert (convenio.codigo in publicados(client)) is visible


def test_sin_vigentes_devuelve_lista_vacia(client, monkeypatch):
    monkeypatch.setattr(
        directorio_publico, "fecha_actual_dominio", lambda: date(9999, 12, 31)
    )
    client.cookies.clear()
    respuesta = client.get(URL)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"items": [], "total": 0}


def test_limite_tiene_tope(client):
    assert client.get(URL, params={"limite": 51}).status_code == 422
