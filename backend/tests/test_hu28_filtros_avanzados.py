from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.enums import (
    AlcanceConvenio,
    EstadoConvenio,
    TipoAliado,
    TipoIdentificacion,
)
from backend.models.tipo_convenio import TipoConvenio
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.usuario import Usuario
from backend.services.convenios import ServicioConvenios

URL_CONVENIOS = "/api/convenios"
URL_CATALOGOS = "/api/convenios/catalogos/consulta"


@pytest.fixture
def autor(crear_usuario) -> Usuario:
    """Gestor que crea los convenios de prueba. No inicia sesión."""
    return crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)


@pytest.fixture
def administrador(client, crear_usuario, entrar_como) -> Usuario:
    usuario = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    entrar_como(usuario)
    return usuario


def _entregar_a_juridica(db, crear_convenio, autor, **cambios):
    """Mismo helper que test_hu17/test_hu26/test_hu27: lleva un convenio
    hasta REVISION_AVAL_JURIDICO con su primera ronda de revisión jurídica."""
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    datos = {
        "tipo_convenio_id": tipo.id,
        "implicacion_financiera": "Sin costo para la Universidad",
        "duracion_meses": 24,
        **cambios,
    }
    convenio = crear_convenio(autor, **datos)
    return ServicioConvenios(db).finalizar_elaboracion(convenio.id, autor)


def _crear_aliado(db: Session, nombre: str, tipo: TipoAliado = TipoAliado.UNIVERSIDAD) -> Aliado:
    aliado = Aliado(
        nombre=nombre,
        tipo=tipo.value,
        tipo_identificacion=TipoIdentificacion.NIT.value,
        identificacion=str(900000000 + uuid4().int % 99999999),
        activo=True,
    )
    db.add(aliado)
    db.commit()
    return aliado


def _crear_programa(db: Session, nombre: str, *, activa: bool = True) -> UnidadOrganizacional:
    unidad = UnidadOrganizacional(
        codigo=f"PROG-{uuid4().hex[:8]}",
        nombre=nombre,
        tipo="PROGRAMA",
        activa=activa,
    )
    db.add(unidad)
    db.commit()
    return unidad


# ---- CA-01: acceso y alcance -----------------------------------------------


@pytest.mark.parametrize(
    "rol",
    [CodigoRol.ADMINISTRADOR_ORI, CodigoRol.GESTOR_ORI, CodigoRol.REVISOR_ORI],
)
def test_ca01_los_tres_roles_pueden_aplicar_filtros(client, crear_usuario, entrar_como, rol) -> None:
    entrar_como(crear_usuario(rol, TipoUsuario.INTERNO))

    respuesta = client.get(URL_CONVENIOS, params={"estado": "VIGENTE"})

    assert respuesta.status_code == 200


def test_ca01_revisor_no_recibe_convenios_fuera_de_su_alcance(
    db, client, crear_usuario, entrar_como, autor, crear_convenio
) -> None:
    termino = f"alcance-revisor-{uuid4().hex[:6]}"
    en_elaboracion = crear_convenio(autor, objeto=f"Convenio {termino} en elaboración")
    en_juridica = _entregar_a_juridica(db, crear_convenio, autor, objeto=f"Convenio {termino} en jurídica")
    revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)

    entrar_como(revisor)
    respuesta = client.get(
        URL_CONVENIOS, params={"buscar": termino, "estado": "EN_TRAMITE"}
    )

    ids = {item["id"] for item in respuesta.json()["items"]}
    assert en_juridica.id in ids
    assert en_elaboracion.id not in ids


# ---- CA-02: filtro por estado -----------------------------------------------


def test_ca02_un_estado(client, administrador, autor, crear_convenio, db) -> None:
    termino = f"estado-{uuid4().hex[:6]}"
    vigente = crear_convenio(autor, objeto=f"Convenio {termino} vigente")
    vigente.estado = EstadoConvenio.VIGENTE.value
    finalizado = crear_convenio(autor, objeto=f"Convenio {termino} finalizado")
    finalizado.estado = EstadoConvenio.FINALIZADO.value
    db.commit()

    respuesta = client.get(URL_CONVENIOS, params={"buscar": termino, "estado": "VIGENTE"})

    ids = {item["id"] for item in respuesta.json()["items"]}
    assert ids == {vigente.id}


def test_ca02_varios_estados_se_combinan_con_o(client, administrador, autor, crear_convenio, db) -> None:
    termino = f"estados-or-{uuid4().hex[:6]}"
    vigente = crear_convenio(autor, objeto=f"Convenio {termino} vigente")
    vigente.estado = EstadoConvenio.VIGENTE.value
    por_vencer = crear_convenio(autor, objeto=f"Convenio {termino} por vencer")
    por_vencer.estado = EstadoConvenio.POR_VENCER.value
    cancelado = crear_convenio(autor, objeto=f"Convenio {termino} cancelado")
    cancelado.estado = EstadoConvenio.CANCELADO.value
    db.commit()

    respuesta = client.get(
        URL_CONVENIOS,
        params={"buscar": termino, "estado": ["VIGENTE", "POR_VENCER"]},
    )

    ids = {item["id"] for item in respuesta.json()["items"]}
    assert ids == {vigente.id, por_vencer.id}


def test_estado_invalido_devuelve_422(client, administrador) -> None:
    respuesta = client.get(URL_CONVENIOS, params={"estado": "NO_EXISTE"})

    assert respuesta.status_code == 422


# ---- CA-03: filtro por tipo de contraparte ---------------------------------


def test_ca03_tipo_contraparte_con_aliado_formal(
    db, client, administrador, autor, crear_convenio
) -> None:
    termino = f"contraparte-formal-{uuid4().hex[:6]}"
    convenio = crear_convenio(autor, objeto=f"Convenio {termino}")
    aliado = _crear_aliado(db, f"Universidad {uuid4().hex[:6]}", TipoAliado.UNIVERSIDAD)
    convenio.aliado_id = aliado.id
    db.commit()
    otro = crear_convenio(autor, objeto=f"Convenio {termino} sin match")

    respuesta = client.get(
        URL_CONVENIOS, params={"buscar": termino, "tipo_contraparte": "UNIVERSIDAD"}
    )

    ids = {item["id"] for item in respuesta.json()["items"]}
    assert convenio.id in ids
    assert otro.id not in ids


def test_ca03_tipo_contraparte_propuesta_sin_aliado_formal(
    db, client, administrador, autor, crear_convenio
) -> None:
    termino = f"contraparte-propuesta-{uuid4().hex[:6]}"
    convenio = crear_convenio(autor, objeto=f"Convenio {termino}")
    convenio.solicitud.tipo_aliado_propuesto = TipoAliado.EMPRESA.value
    db.commit()

    respuesta = client.get(
        URL_CONVENIOS, params={"buscar": termino, "tipo_contraparte": "EMPRESA"}
    )

    cuerpo = respuesta.json()
    assert {item["id"] for item in cuerpo["items"]} == {convenio.id}
    assert cuerpo["items"][0]["contraparte"]["es_aliado_formal"] is False


def test_tipo_contraparte_invalido_devuelve_422(client, administrador) -> None:
    respuesta = client.get(URL_CONVENIOS, params={"tipo_contraparte": "NO_EXISTE"})

    assert respuesta.status_code == 422


# ---- CA-04: filtro por programa académico ----------------------------------


def test_ca04_filtra_por_programa_y_excluye_institucionales(
    db, client, administrador, autor, crear_convenio
) -> None:
    termino = f"programa-{uuid4().hex[:6]}"
    programa = _crear_programa(db, f"Programa {uuid4().hex[:6]}")
    del_programa = crear_convenio(
        autor,
        objeto=f"Convenio {termino} del programa",
        alcance=AlcanceConvenio.PROGRAMA,
        unidad_organizacional_id=programa.id,
    )
    institucional = crear_convenio(
        autor, objeto=f"Convenio {termino} institucional", alcance=AlcanceConvenio.INSTITUCIONAL
    )

    respuesta = client.get(
        URL_CONVENIOS, params={"buscar": termino, "programa_id": programa.id}
    )

    ids = {item["id"] for item in respuesta.json()["items"]}
    assert ids == {del_programa.id}
    assert institucional.id not in ids


def test_programa_id_inexistente_devuelve_lista_vacia_no_404(client, administrador) -> None:
    respuesta = client.get(URL_CONVENIOS, params={"programa_id": 999999})

    assert respuesta.status_code == 200
    assert respuesta.json() == {"items": [], "total": 0}


def test_catalogo_excluye_programas_inactivos_y_otros_tipos(db, client, administrador) -> None:
    activo = _crear_programa(db, f"Programa activo {uuid4().hex[:6]}")
    _crear_programa(db, f"Programa inactivo {uuid4().hex[:6]}", activa=False)
    facultad = UnidadOrganizacional(
        codigo=f"FAC-{uuid4().hex[:8]}", nombre="Facultad de prueba", tipo="FACULTAD", activa=True
    )
    db.add(facultad)
    db.commit()

    respuesta = client.get(URL_CATALOGOS)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    ids_programas = {p["id"] for p in cuerpo["programas"]}
    assert activo.id in ids_programas
    assert all(p["id"] != facultad.id for p in cuerpo["programas"])
    assert set(cuerpo["estados"]) == {e.value for e in EstadoConvenio}
    assert set(cuerpo["tipos_contraparte"]) == {t.value for t in TipoAliado}


# ---- Combinación, alcance general y RN-04 ----------------------------------


def test_combinacion_estado_tipo_programa_buscar_es_y_logico(
    db, client, administrador, autor, crear_convenio
) -> None:
    termino = f"combinado-{uuid4().hex[:6]}"
    programa = _crear_programa(db, f"Programa combinado {uuid4().hex[:6]}")
    aliado = _crear_aliado(db, f"Universidad combinada {uuid4().hex[:6]}", TipoAliado.UNIVERSIDAD)

    coincide = crear_convenio(
        autor,
        objeto=f"Convenio {termino} completo",
        alcance=AlcanceConvenio.PROGRAMA,
        unidad_organizacional_id=programa.id,
    )
    coincide.aliado_id = aliado.id
    coincide.estado = EstadoConvenio.VIGENTE.value
    db.commit()

    # Mismo término y programa, pero otro estado: no debe coincidir (Y).
    otro_estado = crear_convenio(
        autor,
        objeto=f"Convenio {termino} completo otro estado",
        alcance=AlcanceConvenio.PROGRAMA,
        unidad_organizacional_id=programa.id,
    )
    otro_estado.aliado_id = aliado.id
    otro_estado.estado = EstadoConvenio.FINALIZADO.value
    db.commit()

    respuesta = client.get(
        URL_CONVENIOS,
        params={
            "buscar": termino,
            "estado": "VIGENTE",
            "tipo_contraparte": "UNIVERSIDAD",
            "programa_id": programa.id,
        },
    )

    ids = {item["id"] for item in respuesta.json()["items"]}
    assert ids == {coincide.id}


def test_sin_filtros_devuelve_todos_los_convenios_visibles(
    client, administrador, autor, crear_convenio
) -> None:
    creados = {crear_convenio(autor).id, crear_convenio(autor).id}

    respuesta = client.get(URL_CONVENIOS)

    cuerpo = respuesta.json()
    assert creados <= {item["id"] for item in cuerpo["items"]}


def test_rn04_filtrar_no_modifica_actualizado_en(
    db, client, administrador, autor, crear_convenio
) -> None:
    convenio = crear_convenio(autor)
    db.refresh(convenio)
    actualizado_antes = convenio.actualizado_en

    respuesta = client.get(URL_CONVENIOS, params={"estado": "EN_TRAMITE"})
    assert respuesta.status_code == 200

    db.refresh(convenio)
    assert convenio.actualizado_en == actualizado_antes
