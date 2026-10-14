from collections.abc import Callable
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_convenio import RevisionConvenio
from backend.models.usuario import Usuario
from backend.services.convenios import ServicioConvenios

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
        convenio = crear_convenio(autor, **cambios)
        convenio.fecha_firma = fecha_firma
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


@pytest.mark.parametrize("tipo_fecha", ["FORMALIZACION", "VIGENCIA"])
@pytest.mark.parametrize("identificador", ["codigo", "id", "consecutivo", "identificacion"])
def test_fechas_se_combinan_con_identificadores_hu26(
    db, client, administrador, autor, formalizar, tipo_fecha, identificador
) -> None:
    convenio = formalizar(
        autor,
        fecha_firma=date(2026, 6, 15),
        fecha_inicio=date(2026, 1, 1),
        fecha_vencimiento=date(2026, 12, 31),
    )
    convenio.codigo = f"HU27-{uuid4().hex[:10]}"
    convenio.solicitud.identificacion_aliado_propuesto = uuid4().hex[:12]
    db.commit()
    termino = {
        "codigo": convenio.codigo,
        "id": f"#{convenio.id}",
        "consecutivo": convenio.solicitud.consecutivo,
        "identificacion": convenio.solicitud.identificacion_aliado_propuesto,
    }[identificador]

    respuesta = client.get(URL_CONVENIOS, params={
        "buscar": termino, "tipo_fecha": tipo_fecha,
        "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
    })

    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1
    assert respuesta.json()["items"][0]["id"] == convenio.id
    assert respuesta.json()["items"][0]["puede_ver_detalle"] is True


@pytest.mark.parametrize("tipo_fecha", ["FORMALIZACION", "VIGENCIA"])
@pytest.mark.parametrize("participacion", ["resuelta", "asignada", "observacion"])
def test_fechas_preservan_acceso_historico_sin_ampliar_permisos(
    db, client, crear_usuario, entrar_como, autor, formalizar,
    tipo_fecha, participacion,
) -> None:
    termino = f"historico-hu27-{uuid4().hex[:8]}"
    revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    tercero = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    convenio = formalizar(
        autor, fecha_firma=date(2026, 6, 15), objeto=termino,
        fecha_inicio=date(2026, 1, 1), fecha_vencimiento=None,
    )
    ajeno = formalizar(
        autor, fecha_firma=date(2026, 6, 15), objeto=termino,
        fecha_inicio=date(2026, 1, 1), fecha_vencimiento=None,
    )
    revision = RevisionConvenio(
        convenio_id=convenio.id, tipo="JURIDICA", estado="RESUELTA",
        resultado="APROBADA", creada_por_id=tercero.id,
        resuelta_por_id=revisor.id if participacion == "resuelta" else autor.id,
        responsable_id=revisor.id if participacion == "asignada" else None,
    )
    db.add(revision)
    db.flush()
    if participacion == "observacion":
        historial_id = db.scalar(select(HistorialEtapa.id).where(
            HistorialEtapa.convenio_id == convenio.id,
        ))
        db.add(ObservacionRevision(
            convenio_id=convenio.id, historial_etapa_id=historial_id,
            revision_convenio_id=revision.id, origen="REVISOR_ORI",
            registrada_por_id=revisor.id, descripcion="Participación histórica",
        ))
    db.commit()
    parametros = {
        "buscar": termino, "tipo_fecha": tipo_fecha,
        "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
        "limite": 1,
    }

    entrar_como(revisor)
    respuesta = client.get(URL_CONVENIOS, params=parametros)
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1
    assert [item["id"] for item in respuesta.json()["items"]] == [convenio.id]
    assert respuesta.json()["items"][0]["puede_ver_detalle"] is False
    assert ajeno.id != convenio.id
    assert client.get(f"{URL_CONVENIOS}/{convenio.id}/revisiones").status_code == 200
    assert client.get(f"{URL_CONVENIOS}/{convenio.id}").status_code == 404

    entrar_como(tercero)
    respuesta = client.get(URL_CONVENIOS, params=parametros)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"items": [], "total": 0}
    assert client.get(f"{URL_CONVENIOS}/{convenio.id}/revisiones").status_code == 404


def test_vigencia_preserva_acceso_operativo_del_revisor(
    db, client, crear_usuario, entrar_como, gestor, convenio_listo
) -> None:
    convenio = convenio_listo
    ServicioConvenios(db).finalizar_elaboracion(convenio.id, gestor)
    revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    entrar_como(revisor)
    respuesta = client.get(URL_CONVENIOS, params={
        "buscar": f"#{convenio.id}", "tipo_fecha": "VIGENCIA",
        "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
    })
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1
    assert respuesta.json()["items"][0]["puede_ver_detalle"] is True
    assert client.get(f"{URL_CONVENIOS}/{convenio.id}").status_code == 200


@pytest.mark.parametrize("tipo_fecha", ["FORMALIZACION", "VIGENCIA"])
def test_fechas_y_busqueda_paginan_sobre_el_mismo_total(
    client, administrador, autor, formalizar, tipo_fecha
) -> None:
    termino = f"pagina-hu27-{uuid4().hex[:8]}"
    convenios = [formalizar(
        autor, fecha_firma=date(2026, 6, 15), objeto=termino,
        fecha_inicio=date(2026, 1, 1), fecha_vencimiento=date(2026, 12, 31),
    ) for _ in range(3)]
    formalizar(
        autor, fecha_firma=date(2025, 1, 1), objeto=termino,
        fecha_inicio=date(2025, 1, 1), fecha_vencimiento=date(2025, 12, 31),
    )
    for desplazamiento, convenio in enumerate(reversed(convenios)):
        respuesta = client.get(URL_CONVENIOS, params={
            "buscar": termino, "tipo_fecha": tipo_fecha,
            "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
            "limite": 1, "desplazamiento": desplazamiento,
        })
        assert respuesta.status_code == 200
        assert respuesta.json()["total"] == 3
        assert [item["id"] for item in respuesta.json()["items"]] == [convenio.id]


@pytest.mark.parametrize("tipo_fecha", ["FORMALIZACION", "VIGENCIA"])
@pytest.mark.parametrize("extremos", [
    {"fecha_desde": "2026-06-15"},
    {"fecha_hasta": "2026-06-15"},
    {"fecha_desde": "2026-06-15", "fecha_hasta": "2026-06-15"},
])
def test_extremos_inclusivos_y_rangos_abiertos(
    client, administrador, autor, formalizar, tipo_fecha, extremos
) -> None:
    convenio = formalizar(
        autor, fecha_firma=date(2026, 6, 15),
        fecha_inicio=date(2026, 6, 15), fecha_vencimiento=date(2026, 6, 15),
    )
    respuesta = client.get(URL_CONVENIOS, params={
        "buscar": f"#{convenio.id}", "tipo_fecha": tipo_fecha, **extremos,
    })
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1


@pytest.mark.parametrize("parametros", [
    {"tipo_fecha": "OTRA"}, {"fecha_desde": "2026-02-30"},
    {"fecha_desde": "2026-12-31", "fecha_hasta": "2026-01-01"},
])
def test_parametros_de_fecha_invalidos_devuelven_422(client, administrador, parametros) -> None:
    assert client.get(URL_CONVENIOS, params=parametros).status_code == 422


@pytest.mark.parametrize("estado", list(EstadoConvenio))
def test_fecha_mostrada_respeta_el_estado_de_formalizacion(
    client, administrador, autor, formalizar, estado
) -> None:
    convenio = formalizar(autor, fecha_firma=date(2026, 6, 15), estado=estado)
    respuesta = client.get(URL_CONVENIOS, params={"buscar": f"#{convenio.id}"})
    assert respuesta.status_code == 200
    esperado = None if estado in (EstadoConvenio.EN_TRAMITE, EstadoConvenio.CANCELADO) else "2026-06-15"
    assert respuesta.json()["items"][0]["fecha_formalizacion"] == esperado


def test_filtrar_y_limpiar_no_ejecuta_escrituras(
    db, client, administrador, autor, formalizar
) -> None:
    convenio = formalizar(
        autor, fecha_firma=date(2026, 6, 15), fecha_inicio=date(2026, 1, 1),
    )
    sentencias = []

    def registrar(conn, cursor, statement, parameters, context, executemany):
        sentencias.append(statement.strip().split()[0].upper())

    conexion = db.connection()
    event.listen(conexion, "before_cursor_execute", registrar)
    try:
        for parametros in (
            {"tipo_fecha": "FORMALIZACION", "fecha_desde": "2026-01-01"},
            {"tipo_fecha": "VIGENCIA", "fecha_hasta": "2026-12-31"},
            {},
        ):
            respuesta = client.get(URL_CONVENIOS, params={
                "buscar": f"#{convenio.id}", **parametros,
            })
            assert respuesta.status_code == 200
            assert respuesta.json()["total"] == 1
    finally:
        event.remove(conexion, "before_cursor_execute", registrar)
    assert "SELECT" in sentencias
    assert not {"INSERT", "UPDATE", "DELETE"}.intersection(sentencias)
