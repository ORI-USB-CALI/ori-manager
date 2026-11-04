from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.enums import TipoAliado, TipoIdentificacion
from backend.models.revision_convenio import RevisionConvenio
from backend.models.tipo_convenio import TipoConvenio
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


def _entregar_a_juridica(db, crear_convenio, autor, **cambios):
    """Mismo helper que test_hu17_tablero.py: lleva un convenio hasta
    REVISION_AVAL_JURIDICO con su primera ronda de revisión jurídica."""
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    datos = {
        "tipo_convenio_id": tipo.id,
        "implicacion_financiera": "Sin costo para la Universidad",
        "duracion_meses": 24,
        **cambios,
    }
    convenio = crear_convenio(autor, **datos)
    return ServicioConvenios(db).finalizar_elaboracion(convenio.id, autor)


def _crear_aliado(db: Session, nombre: str) -> Aliado:
    aliado = Aliado(
        nombre=nombre,
        tipo=TipoAliado.UNIVERSIDAD.value,
        tipo_identificacion=TipoIdentificacion.NIT.value,
        identificacion=str(900000000 + uuid4().int % 99999999),
        activo=True,
    )
    db.add(aliado)
    db.commit()
    return aliado


def test_sin_sesion_no_accede(client) -> None:
    respuesta = client.get(URL_CONVENIOS)

    assert respuesta.status_code == 401


def test_solicitante_sin_convenios_ver_recibe_403(client, crear_usuario, entrar_como) -> None:
    entrar_como(crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO))

    respuesta = client.get(URL_CONVENIOS)

    assert respuesta.status_code == 403


def test_ca01_busca_por_codigo(client, administrador, autor, crear_convenio) -> None:
    objetivo = crear_convenio(autor, codigo=f"CONV-{uuid4().hex[:8]}", objeto="Movilidad académica")
    crear_convenio(autor, codigo=f"CONV-{uuid4().hex[:8]}", objeto="Otro convenio sin relación")

    respuesta = client.get(URL_CONVENIOS, params={"buscar": objetivo.codigo})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    assert [item["id"] for item in cuerpo["items"]] == [objetivo.id]
    assert cuerpo["items"][0]["puede_ver_detalle"] is True


def test_ca01_busca_por_palabra_del_objeto(client, administrador, autor, crear_convenio) -> None:
    objetivo = crear_convenio(autor, objeto="Cooperación en movilidad estudiantil")
    crear_convenio(autor, objeto="Convenio sin relación alguna")

    respuesta = client.get(URL_CONVENIOS, params={"buscar": "movilidad"})

    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["id"] == objetivo.id


def test_ca02_busca_por_aliado_formal_y_es_insensible_a_mayusculas(
    db, client, administrador, autor, crear_convenio
) -> None:
    convenio = crear_convenio(autor, objeto="Convenio con aliado formal")
    aliado = _crear_aliado(db, f"Universidad Insignia {uuid4().hex[:6]}")
    convenio.aliado = aliado
    db.commit()

    respuesta = client.get(URL_CONVENIOS, params={"buscar": aliado.nombre.upper()})

    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    item = cuerpo["items"][0]
    assert item["id"] == convenio.id
    assert item["contraparte"]["nombre"] == aliado.nombre
    assert item["contraparte"]["es_aliado_formal"] is True


def test_ca02_busca_por_contraparte_propuesta_sin_aliado_formal(
    db, client, administrador, autor, crear_convenio
) -> None:
    nombre_propuesto = f"Entidad Propuesta {uuid4().hex[:6]}"
    convenio = crear_convenio(autor)
    convenio.solicitud.nombre_aliado_propuesto = nombre_propuesto
    db.commit()

    respuesta = client.get(URL_CONVENIOS, params={"buscar": nombre_propuesto})

    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    item = cuerpo["items"][0]
    assert item["id"] == convenio.id
    assert item["contraparte"]["nombre"] == nombre_propuesto
    assert item["contraparte"]["es_aliado_formal"] is False


def test_ca03_sin_coincidencias_devuelve_vacio(client, administrador, autor, crear_convenio) -> None:
    crear_convenio(autor, objeto="Convenio existente")

    respuesta = client.get(URL_CONVENIOS, params={"buscar": f"sin-coincidencias-{uuid4().hex}"})

    cuerpo = respuesta.json()
    assert cuerpo["items"] == []
    assert cuerpo["total"] == 0


def test_termino_con_comodines_se_busca_literal(client, administrador, autor, crear_convenio) -> None:
    codigo = f"CONV-100%-{uuid4().hex[:4]}"
    objetivo = crear_convenio(autor, codigo=codigo)
    crear_convenio(autor, objeto="Otro convenio que no debe coincidir")

    respuesta = client.get(URL_CONVENIOS, params={"buscar": "100%"})

    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["id"] == objetivo.id


def test_ca04_revisor_no_ve_convenios_fuera_de_su_alcance(
    db, client, crear_usuario, entrar_como, autor, crear_convenio
) -> None:
    termino = f"palabra-compartida-{uuid4().hex[:6]}"
    en_elaboracion = crear_convenio(autor, objeto=f"Convenio {termino} en elaboración")
    en_juridica = _entregar_a_juridica(db, crear_convenio, autor, objeto=f"Convenio {termino} en jurídica")
    revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)

    entrar_como(revisor)
    respuesta = client.get(URL_CONVENIOS, params={"buscar": termino})

    cuerpo = respuesta.json()
    ids = {item["id"] for item in cuerpo["items"]}
    assert en_juridica.id in ids
    assert en_elaboracion.id not in ids

    autorizado = next(
        item for item in cuerpo["items"] if item["id"] == en_juridica.id
    )
    assert autorizado["puede_ver_detalle"] is True


def test_paginacion_respeta_limite_y_desplazamiento(
    client, administrador, autor, crear_convenio
) -> None:
    termino = f"paginacion-{uuid4().hex[:6]}"
    creados = [crear_convenio(autor, objeto=f"Convenio {termino} número {i}") for i in range(3)]

    primera_pagina = client.get(
        URL_CONVENIOS, params={"buscar": termino, "limite": 2, "desplazamiento": 0}
    ).json()
    segunda_pagina = client.get(
        URL_CONVENIOS, params={"buscar": termino, "limite": 2, "desplazamiento": 2}
    ).json()

    assert primera_pagina["total"] == 3
    assert segunda_pagina["total"] == 3
    assert len(primera_pagina["items"]) == 2
    assert len(segunda_pagina["items"]) == 1
    ids_primera = {item["id"] for item in primera_pagina["items"]}
    ids_segunda = {item["id"] for item in segunda_pagina["items"]}
    assert ids_primera.isdisjoint(ids_segunda)
    assert ids_primera | ids_segunda == {c.id for c in creados}


def test_sin_filtro_administrador_obtiene_todos_los_convenios_en_su_alcance(
    client, administrador, autor, crear_convenio
) -> None:
    creados = {crear_convenio(autor).id, crear_convenio(autor).id}

    respuesta = client.get(URL_CONVENIOS)

    cuerpo = respuesta.json()
    assert creados <= {item["id"] for item in cuerpo["items"]}
    assert cuerpo["total"] >= len(creados)


def test_ca01_busca_por_id_de_convenio_sin_codigo(
    client, administrador, autor, crear_convenio
) -> None:
    convenio = crear_convenio(autor)
    assert convenio.codigo is None

    respuesta = client.get(
        URL_CONVENIOS,
        params={"buscar": f"#{convenio.id}"},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["id"] == convenio.id


def test_ca01_busca_por_consecutivo_de_solicitud(
    client, administrador, autor, crear_convenio
) -> None:
    convenio = crear_convenio(autor)
    consecutivo = convenio.solicitud.consecutivo

    respuesta = client.get(
        URL_CONVENIOS,
        params={"buscar": consecutivo},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    assert cuerpo["items"][0]["id"] == convenio.id


def test_ca04_revisor_encuentra_convenio_historico_sin_acceso_operativo(
    db, client, crear_usuario, entrar_como, autor, crear_convenio
) -> None:
    termino = f"historico-hu26-{uuid4().hex[:6]}"
    convenio = _entregar_a_juridica(
        db, crear_convenio, autor, objeto=f"Convenio {termino}"
    )

    revisor1 = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    revisor2 = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)

    # Completar las dos revisiones juridicas.
    for actor in (revisor1, revisor2):
        pendiente = db.scalar(
            select(RevisionConvenio).where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == "JURIDICA",
                RevisionConvenio.estado == "PENDIENTE",
            )
        )
        assert pendiente is not None

        db.refresh(convenio)
        entrar_como(actor)
        respuesta = client.post(
            f"/api/convenios/{convenio.id}/revisiones/{pendiente.id}/aprobar",
            json={"expected_version": convenio.version_actual},
        )

        assert respuesta.status_code == 200, respuesta.text

    db.refresh(convenio)
    assert convenio.etapa_actual.codigo == "REVISION_CONTRAPARTE"

    # Puede consultar el historial, pero no el detalle operativo.
    entrar_como(revisor1)
    assert client.get(
        f"/api/convenios/{convenio.id}/revisiones"
    ).status_code == 200
    assert client.get(
        f"/api/convenios/{convenio.id}"
    ).status_code == 404

    # HU-26 debe mostrar el convenio en la busqueda historica.
    respuesta = client.get(URL_CONVENIOS, params={"buscar": termino})
    assert respuesta.status_code == 200
    assert convenio.id in {
        item["id"] for item in respuesta.json()["items"]
    }

        # HU-26 debe mostrar el convenio en la busqueda historica.
    respuesta = client.get(URL_CONVENIOS, params={"buscar": termino})
    assert respuesta.status_code == 200
    assert convenio.id in {
        item["id"] for item in respuesta.json()["items"]
    }

    historico = next(
        item for item in respuesta.json()["items"]
        if item["id"] == convenio.id
    )
    assert historico["puede_ver_detalle"] is False

    # Un revisor sin participacion no puede encontrarlo.

    # Un revisor sin participacion no puede encontrarlo.
    tercero = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    entrar_como(tercero)
    respuesta = client.get(URL_CONVENIOS, params={"buscar": termino})
    assert convenio.id not in {
        item["id"] for item in respuesta.json()["items"]
    }
