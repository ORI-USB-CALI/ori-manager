from collections.abc import Callable
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.enums import (
    EstadoConvenio,
    EstadoRevisionConvenio,
    TipoAliado,
    TipoIdentificacion,
)
from backend.models.etapa import Etapa
from backend.models.revision_convenio import RevisionConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.services.convenios import ServicioConvenios

URL_TABLERO = "/api/convenios/tablero"

AREAS_POR_ETAPA = {
    "SOLICITUD": "Solicitante",
    "ELABORACION": "Gestor ORI",
    "REVISION_AVAL_JURIDICO": "Oficina Jurídica",
    "REVISION_CONTRAPARTE": "Contraparte",
    "REVISION_FINAL": "ORI",
    "APROBACION_FIRMAS": "ORI",
    "FIRMA_ARCHIVO_SEGUIMIENTO": "ORI",
}


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
def crear_aliado(db: Session) -> Callable[[], Aliado]:
    def _crear() -> Aliado:
        aliado = Aliado(
            nombre=f"Universidad Aliada {uuid4().hex[:6]}",
            tipo=TipoAliado.UNIVERSIDAD.value,
            tipo_identificacion=TipoIdentificacion.NIT.value,
            identificacion=str(900000000 + uuid4().int % 99999999),
            activo=True,
        )
        db.add(aliado)
        db.commit()
        return aliado

    return _crear


def _mover_a_etapa(db: Session, convenio: Convenio, codigo_etapa: str) -> None:
    """Simula una transición del flujo (HU-14 a HU-16) sin pasar por sus endpoints."""
    # Se asigna la relación, no solo el FK, para que la sesión compartida con la
    # app no siga viendo la etapa anterior.
    convenio.etapa_actual = db.scalar(select(Etapa).where(Etapa.codigo == codigo_etapa))
    db.commit()


def _entregar_a_juridica(
    db: Session, crear_convenio: Callable[..., Convenio], autor: Usuario
) -> Convenio:
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    convenio = crear_convenio(
        autor,
        tipo_convenio_id=tipo.id,
        implicacion_financiera="Sin costo para la Universidad",
        duracion_meses=24,
    )
    return ServicioConvenios(db).finalizar_elaboracion(convenio.id, autor)


def _convenios_por_id(cuerpo: dict) -> dict[int, dict]:
    return {convenio["id"]: convenio for convenio in cuerpo["convenios"]}


def test_sin_sesion_no_accede_al_tablero(client) -> None:
    respuesta = client.get(URL_TABLERO)

    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    ("codigo_rol", "tipo_usuario"),
    [
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_solicitantes_no_acceden_al_tablero(
    client, crear_usuario, entrar_como, codigo_rol, tipo_usuario
) -> None:
    entrar_como(crear_usuario(codigo_rol, tipo_usuario))

    respuesta = client.get(URL_TABLERO)

    assert respuesta.status_code == 403


def test_administrador_ve_todos_los_convenios_en_tramite(
    client, administrador, crear_usuario, crear_convenio
) -> None:
    gestor_a = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    gestor_b = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    convenios = {crear_convenio(gestor_a).id, crear_convenio(gestor_b).id}

    respuesta = client.get(URL_TABLERO)

    assert respuesta.status_code == 200
    assert convenios <= set(_convenios_por_id(respuesta.json()))


def test_cada_gestor_ve_unicamente_los_convenios_que_gestiona(
    client, crear_usuario, entrar_como, crear_convenio
) -> None:
    gestor_a = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    gestor_b = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    convenio_a = crear_convenio(gestor_a)
    convenio_b = crear_convenio(gestor_b)

    entrar_como(gestor_a)
    ids_a = set(_convenios_por_id(client.get(URL_TABLERO).json()))
    assert convenio_a.id in ids_a
    assert convenio_b.id not in ids_a

    entrar_como(gestor_b)
    ids_b = set(_convenios_por_id(client.get(URL_TABLERO).json()))
    assert convenio_b.id in ids_b
    assert convenio_a.id not in ids_b


def test_revisor_solo_ve_revision_juridica_pendiente_que_puede_resolver(
    db, client, crear_usuario, entrar_como, autor, crear_convenio
) -> None:
    revisor_primero = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    elaboracion = crear_convenio(autor)
    juridica = _entregar_a_juridica(db, crear_convenio, autor)

    entrar_como(revisor_primero)
    primera_consulta = _convenios_por_id(client.get(URL_TABLERO).json())
    assert juridica.id in primera_consulta
    assert elaboracion.id not in primera_consulta

    primera = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == juridica.id,
            RevisionConvenio.estado == EstadoRevisionConvenio.PENDIENTE.value,
        )
    )
    ServicioConvenios(db).aprobar(
        juridica.id,
        primera.id,
        juridica.version_actual,
        revisor_primero,
    )

    assert juridica.id not in _convenios_por_id(client.get(URL_TABLERO).json())
    entrar_como(otro_revisor)
    assert juridica.id in _convenios_por_id(client.get(URL_TABLERO).json())


def test_detalle_no_permite_saltarse_el_scope_del_tablero_por_url(
    db, client, crear_usuario, entrar_como, autor, crear_convenio
) -> None:
    gestor_a = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    gestor_b = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    propio = crear_convenio(gestor_a)
    ajeno = crear_convenio(gestor_b)

    entrar_como(gestor_a)
    assert client.get(f"/api/convenios/{propio.id}").status_code == 200
    assert client.get(f"/api/convenios/{ajeno.id}").status_code == 404

    juridica = _entregar_a_juridica(db, crear_convenio, autor)
    primer_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    segundo_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    entrar_como(primer_revisor)
    assert client.get(f"/api/convenios/{ajeno.id}").status_code == 404
    assert client.get(f"/api/convenios/{juridica.id}").status_code == 200
    revision = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == juridica.id,
            RevisionConvenio.estado == EstadoRevisionConvenio.PENDIENTE.value,
        )
    )
    ServicioConvenios(db).aprobar(
        juridica.id, revision.id, juridica.version_actual, primer_revisor
    )
    assert client.get(f"/api/convenios/{juridica.id}").status_code == 404
    assert client.get(f"/api/convenios/{juridica.id}/revision").status_code == 404
    entrar_como(segundo_revisor)
    assert client.get(f"/api/convenios/{juridica.id}").status_code == 200
    assert client.get(f"/api/convenios/{juridica.id}/revision").status_code == 200


def test_tablero_expone_las_siete_etapas_con_su_area_responsable(
    client, administrador
) -> None:
    respuesta = client.get(URL_TABLERO)

    assert respuesta.status_code == 200
    etapas = respuesta.json()["etapas"]
    assert [etapa["codigo"] for etapa in etapas] == list(AREAS_POR_ETAPA)
    assert [etapa["orden"] for etapa in etapas] == list(range(1, 8))
    assert all(etapa["nombre"] for etapa in etapas)
    assert {
        etapa["codigo"]: etapa["area_responsable"] for etapa in etapas
    } == AREAS_POR_ETAPA


def test_muestra_informacion_operativa_de_cada_convenio(
    db, client, administrador, autor, crear_aliado, crear_convenio
) -> None:
    aliado = crear_aliado()
    con_aliado = crear_convenio(autor, codigo=f"CONV-{uuid4().hex[:8]}")
    con_aliado.aliado = aliado
    db.commit()
    sin_aliado = crear_convenio(autor)
    _mover_a_etapa(db, sin_aliado, "REVISION_CONTRAPARTE")

    respuesta = client.get(URL_TABLERO)

    assert respuesta.status_code == 200
    convenios = _convenios_por_id(respuesta.json())

    primero = convenios[con_aliado.id]
    assert primero["codigo"] == con_aliado.codigo
    assert primero["estado"] == EstadoConvenio.EN_TRAMITE
    assert primero["etapa_actual"]["codigo"] == "ELABORACION"
    assert primero["aliado"]["id"] == aliado.id
    assert primero["aliado"]["nombre"] == aliado.nombre

    segundo = convenios[sin_aliado.id]
    assert segundo["etapa_actual"]["codigo"] == "REVISION_CONTRAPARTE"
    assert segundo["aliado"] is None
    assert segundo["aliado_propuesto"] == sin_aliado.solicitud.nombre_aliado_propuesto
    assert segundo["responsable"] is None


def test_en_elaboracion_el_responsable_es_el_gestor(
    client, administrador, autor, crear_convenio
) -> None:
    convenio = crear_convenio(autor)

    respuesta = client.get(URL_TABLERO)

    responsable = _convenios_por_id(respuesta.json())[convenio.id]["responsable"]
    assert responsable["id"] == autor.id
    assert responsable["nombre_completo"] == autor.nombre_completo


def test_en_revision_juridica_sin_revisor_asignado_se_informa_el_area(
    db, client, administrador, autor, crear_convenio
) -> None:
    convenio = _entregar_a_juridica(db, crear_convenio, autor)

    respuesta = client.get(URL_TABLERO)

    tarjeta = _convenios_por_id(respuesta.json())[convenio.id]
    assert tarjeta["etapa_actual"]["codigo"] == "REVISION_AVAL_JURIDICO"
    assert tarjeta["responsable"] is None
    assert tarjeta["etapa_actual"]["area_responsable"] == "Oficina Jurídica"


def test_en_revision_juridica_muestra_responsable_explicito(
    db, client, administrador, autor, revisor, crear_convenio
) -> None:
    convenio = _entregar_a_juridica(db, crear_convenio, autor)
    revision = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.estado == EstadoRevisionConvenio.PENDIENTE.value,
        )
    )
    revision.responsable_id = revisor.id
    db.commit()

    tarjeta = _convenios_por_id(client.get(URL_TABLERO).json())[convenio.id]

    assert tarjeta["responsable"]["id"] == revisor.id
    assert tarjeta["responsable"]["nombre_completo"] == revisor.nombre_completo


def test_la_devolucion_de_juridica_devuelve_la_gestion_al_gestor(
    db, client, administrador, autor, revisor, crear_convenio
) -> None:
    convenio = _entregar_a_juridica(db, crear_convenio, autor)
    revision = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.estado == EstadoRevisionConvenio.PENDIENTE.value,
        )
    )
    ServicioConvenios(db).devolver(
        convenio.id,
        revision.id,
        ["Ajustar la cláusula de vigencia"],
        convenio.version_actual,
        revisor,
    )

    respuesta = client.get(URL_TABLERO)

    tarjeta = _convenios_por_id(respuesta.json())[convenio.id]
    assert tarjeta["etapa_actual"]["codigo"] == "ELABORACION"
    assert tarjeta["responsable"]["id"] == autor.id


def test_excluye_convenios_que_no_estan_en_tramite(
    db, client, administrador, autor, crear_convenio
) -> None:
    en_tramite = crear_convenio(autor)
    vigente = crear_convenio(autor)
    cancelado = crear_convenio(autor)
    vigente.estado = EstadoConvenio.VIGENTE.value
    cancelado.estado = EstadoConvenio.CANCELADO.value
    db.commit()

    respuesta = client.get(URL_TABLERO)

    assert respuesta.status_code == 200
    ids = set(_convenios_por_id(respuesta.json()))
    assert en_tramite.id in ids
    assert vigente.id not in ids
    assert cancelado.id not in ids


def test_refleja_el_cambio_de_etapa_en_una_consulta_posterior(
    db, client, administrador, autor, crear_convenio
) -> None:
    convenio = crear_convenio(autor)

    antes = _convenios_por_id(client.get(URL_TABLERO).json())
    assert antes[convenio.id]["etapa_actual"]["codigo"] == "ELABORACION"

    _mover_a_etapa(db, convenio, "REVISION_CONTRAPARTE")

    despues = _convenios_por_id(client.get(URL_TABLERO).json())
    assert despues[convenio.id]["etapa_actual"]["codigo"] == "REVISION_CONTRAPARTE"


def test_consultar_el_tablero_no_modifica_los_convenios(
    db, client, administrador, autor, crear_convenio
) -> None:
    convenio = crear_convenio(autor)
    etapa_inicial = convenio.etapa_actual_id
    estado_inicial = convenio.estado
    actualizado_inicial = convenio.actualizado_en

    for _ in range(2):
        assert client.get(URL_TABLERO).status_code == 200

    db.refresh(convenio)
    assert convenio.etapa_actual_id == etapa_inicial
    assert convenio.estado == estado_inicial
    assert convenio.actualizado_en == actualizado_inicial


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_tablero_no_ofrece_operaciones_de_escritura(
    db, client, administrador, autor, crear_convenio, metodo
) -> None:
    convenio = crear_convenio(autor)
    etapa_inicial = convenio.etapa_actual_id

    respuesta = client.request(metodo.upper(), URL_TABLERO)

    # PATCH coincide con la ruta PATCH /convenios/{convenio_id} y falla al validar
    # "tablero" como entero (422); el resto no tiene ruta (405).
    assert respuesta.status_code in (405, 422)
    db.refresh(convenio)
    assert convenio.etapa_actual_id == etapa_inicial


def test_sin_convenios_en_tramite_muestra_tablero_vacio(
    db, client, administrador
) -> None:
    db.execute(
        update(Convenio)
        .where(Convenio.estado == EstadoConvenio.EN_TRAMITE.value)
        .values(estado=EstadoConvenio.CANCELADO.value)
    )
    db.commit()

    respuesta = client.get(URL_TABLERO)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["convenios"] == []
    assert len(cuerpo["etapas"]) == 7
