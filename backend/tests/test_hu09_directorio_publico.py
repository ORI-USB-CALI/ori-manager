"""HU-09: directorio público de convenios vigentes."""

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.api.routers import directorio_publico
from backend.main import app
from backend.models.aliado import Aliado
from backend.models.enums import EstadoConvenio, TipoAliado, TipoIdentificacion
from backend.models.tipo_convenio import TipoConvenio
from backend.schemas.convenio import ConvenioCrearManual
from backend.services.convenios import ServicioConvenios

URL = "/api/public/directorio-convenios"
HOY = date(2027, 3, 15)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(directorio_publico, "fecha_actual_dominio", lambda: HOY)


@pytest.fixture(params=["SOLICITUD", "MANUAL_ORI"])
def crear_formalizado(db, gestor, crear_convenio, request):
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
        if request.param == "MANUAL_ORI":
            convenio = ServicioConvenios(db).crear_manual(
                ConvenioCrearManual(
                    objeto="Movilidad académica", tipo_convenio_id=tipo_id
                ),
                gestor,
            )
        else:
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
    respuesta = client.get(URL, params={"limite": 50}, follow_redirects=False)
    assert respuesta.status_code == 200, respuesta.text
    assert not respuesta.history
    assert "location" not in respuesta.headers
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


@pytest.mark.parametrize(
    "estado",
    [e.value for e in EstadoConvenio if e.value != "VIGENTE"],
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
        (None, date(2027, 12, 31), False),
        (date(2027, 1, 1), None, False),
        (HOY, HOY, True),
        (None, None, False),
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


@pytest.mark.parametrize(
    "params",
    [{"limite": 51}, {"limite": 0}, {"desplazamiento": -1}, {"limite": "abc"}],
)
def test_parametros_invalidos(client, params):
    assert client.get(URL, params=params).status_code == 422


@pytest.mark.parametrize("codigo", [None, "", "   "])
def test_excluye_sin_codigo_sin_asignarlo(db, client, crear_formalizado, codigo):
    convenio = crear_formalizado()
    convenio.codigo = codigo
    db.commit()
    assert client.get(URL).json() == {"items": [], "total": 0}
    db.refresh(convenio)
    assert convenio.codigo == codigo


@pytest.mark.parametrize("nombre", [None, "", "   "])
def test_excluye_sin_aliado_identificable(db, client, crear_formalizado, nombre):
    convenio = crear_formalizado()
    if nombre is None:
        convenio.aliado = None
    else:
        convenio.aliado.nombre = nombre
    db.commit()
    # Una solicitud puede contener nombre propuesto: no es identidad pública.
    assert client.get(URL).json() == {"items": [], "total": 0}


def test_paginacion_total_y_orden_estable(client, crear_formalizado):
    convenios = [crear_formalizado() for _ in range(3)]
    crear_formalizado(estado="POR_VENCER")
    client.cookies.clear()
    paginas = [
        client.get(URL, params={"limite": 1, "desplazamiento": n}).json()
        for n in range(4)
    ]
    assert [p["total"] for p in paginas] == [3, 3, 3, 3]
    assert [p["items"][0]["codigo"] for p in paginas[:3]] == [
        c.codigo for c in convenios
    ]
    assert paginas[3]["items"] == []


def test_error_interno_no_expone_datos(db, client, monkeypatch):
    def fallar(*args, **kwargs):
        raise SQLAlchemyError("SQL privado, credenciales y observaciones jurídicas")

    monkeypatch.setattr(db, "scalar", fallar)
    with TestClient(app, raise_server_exceptions=False) as anonimo:
        respuesta = anonimo.get(URL, follow_redirects=False)
    assert respuesta.status_code == 500
    assert respuesta.text == "Internal Server Error"
    assert "location" not in respuesta.headers
