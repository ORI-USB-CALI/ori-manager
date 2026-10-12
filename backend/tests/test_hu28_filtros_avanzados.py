from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.enums import (
    AlcanceConvenio,
    EstadoConvenio,
    TipoAliado,
    TipoIdentificacion,
)
from backend.models.revision_convenio import RevisionConvenio
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
        sector_economico="Tecnología" if tipo == TipoAliado.EMPRESA else None,
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


@pytest.fixture
def crear_filtrable(db, crear_convenio, autor):
    def crear(*, estado=EstadoConvenio.VIGENTE, tipo=TipoAliado.EMPRESA,
              firma=date(2026, 6, 15), **datos):
        convenio = crear_convenio(
            autor, fecha_inicio=date(2026, 1, 1),
            fecha_vencimiento=date(2026, 12, 31), **datos,
        )
        convenio.estado = estado.value
        convenio.fecha_firma = firma
        convenio.solicitud.tipo_aliado_propuesto = tipo.value
        db.commit()
        return convenio
    return crear


def test_institucional_usa_alcance_explicito_y_no_cualquier_programa_nulo(
    db, client, administrador, autor, crear_convenio
) -> None:
    termino = f"institucional-{uuid4().hex}"
    institucional = crear_convenio(autor, objeto=termino)
    sin_definir = crear_convenio(autor, objeto=termino)
    sin_definir.alcance = None
    incompleto = crear_convenio(autor, objeto=termino)
    incompleto.alcance = AlcanceConvenio.PROGRAMA.value
    programa = _crear_programa(db, "Programa del filtro institucional")
    crear_convenio(
        autor, objeto=termino, alcance=AlcanceConvenio.PROGRAMA,
        unidad_organizacional_id=programa.id,
    )
    db.commit()
    respuesta = client.get(URL_CONVENIOS, params={
        "buscar": termino, "alcance": "INSTITUCIONAL",
    })
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1
    assert [item["id"] for item in respuesta.json()["items"]] == [institucional.id]


def test_programa_id_no_acepta_facultad_ni_unidad_de_convenio_institucional(
    db, client, administrador, autor, crear_convenio
) -> None:
    facultad = UnidadOrganizacional(
        codigo=f"FAC-{uuid4().hex}", nombre="Facultad del filtro",
        tipo="FACULTAD", activa=True,
    )
    db.add(facultad)
    db.commit()
    programa = _crear_programa(db, "Programa del filtro")
    termino = f"validar-programa-{uuid4().hex}"
    crear_convenio(
        autor, objeto=termino, alcance=AlcanceConvenio.PROGRAMA,
        unidad_organizacional_id=facultad.id,
    )
    crear_convenio(autor, objeto=termino, unidad_organizacional_id=programa.id)
    for unidad in (facultad, programa):
        respuesta = client.get(URL_CONVENIOS, params={
            "buscar": termino, "programa_id": unidad.id,
        })
        assert respuesta.status_code == 200
        assert respuesta.json() == {"items": [], "total": 0}


@pytest.mark.parametrize("parametros", [
    {"programa_id": 0}, {"programa_id": -1}, {"programa_id": "abc"},
    {"programa_id": ""}, {"programa_id": "1.5"}, {"alcance": "OTRO"},
])
def test_parametros_programa_alcance_invalidos(client, administrador, parametros):
    assert client.get(URL_CONVENIOS, params=parametros).status_code == 422


def test_institucional_con_programa_rechaza_combinacion_sin_ampliar_resultados(
    db, client, administrador, crear_filtrable
):
    programa = _crear_programa(db, "Programa incompatible")
    crear_filtrable()
    respuesta = client.get(URL_CONVENIOS, params={
        "alcance": "INSTITUCIONAL", "programa_id": programa.id,
    })
    assert respuesta.status_code == 422
    assert "No se puede combinar" in respuesta.json()["detail"]


@pytest.mark.parametrize("especifico", [False, True])
def test_alcance_programa_todos_o_un_programa_excluye_institucional_y_nulo(
    db, client, administrador, crear_filtrable, especifico
):
    termino = f"alcance-programa-{uuid4().hex}"
    programa = _crear_programa(db, "Programa específico")
    otro_programa = _crear_programa(db, "Otro programa")
    objetivo = crear_filtrable(
        objeto=termino, alcance=AlcanceConvenio.PROGRAMA,
        unidad_organizacional_id=programa.id,
    )
    otro = crear_filtrable(
        objeto=termino, alcance=AlcanceConvenio.PROGRAMA,
        unidad_organizacional_id=otro_programa.id,
    )
    crear_filtrable(objeto=termino)
    sin_definir = crear_filtrable(objeto=termino)
    sin_definir.alcance = None
    db.commit()
    parametros = {"buscar": termino, "alcance": "PROGRAMA"}
    if especifico:
        parametros["programa_id"] = programa.id
    respuesta = client.get(URL_CONVENIOS, params=parametros)
    assert respuesta.status_code == 200
    esperados = {objetivo.id} if especifico else {objetivo.id, otro.id}
    assert {item["id"] for item in respuesta.json()["items"]} == esperados
    assert respuesta.json()["total"] == len(esperados)


@pytest.mark.parametrize("tipo_fecha", ["FORMALIZACION", "VIGENCIA"])
@pytest.mark.parametrize("identificador", ["SOL", "ID", "CODIGO"])
def test_identificadores_hu26_combinados_con_fechas_estado_y_programa(
    db, client, administrador, crear_filtrable, tipo_fecha, identificador
) -> None:
    programa = _crear_programa(db, "Programa combinado HU-28")
    convenio = crear_filtrable(
        alcance=AlcanceConvenio.PROGRAMA, unidad_organizacional_id=programa.id,
    )
    convenio.codigo = f"HU28-{uuid4().hex}"
    db.commit()
    buscar = {"SOL": convenio.solicitud.consecutivo, "ID": f"#{convenio.id}", "CODIGO": convenio.codigo}[identificador]
    parametros = {
        "buscar": buscar, "estado": "VIGENTE", "programa_id": programa.id,
        "tipo_contraparte": "EMPRESA", "tipo_fecha": tipo_fecha,
        "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
    }
    respuesta = client.get(URL_CONVENIOS, params=parametros)
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1
    assert respuesta.json()["items"][0]["id"] == convenio.id
    assert respuesta.json()["items"][0]["puede_ver_detalle"] is True
    # Mismo identificador, pero cada categoría excluye por separado.
    for cambio in (
        {"estado": "CANCELADO"}, {"programa_id": programa.id + 100000},
        {"tipo_contraparte": "COLEGIO"}, {"fecha_desde": "2099-01-01", "fecha_hasta": "2099-12-31"},
    ):
        excluido = client.get(URL_CONVENIOS, params={**parametros, **cambio})
        assert excluido.status_code == 200
        assert excluido.json() == {"items": [], "total": 0}


@pytest.mark.parametrize("caracter", ["%", "_", "\\"])
def test_escape_busqueda_se_preserva_con_filtros_avanzados(
    client, administrador, crear_filtrable, caracter
):
    prefijo = uuid4().hex
    objetivo = crear_filtrable(objeto=f"{prefijo}{caracter}literal")
    crear_filtrable(objeto=f"{prefijo}Xliteral")
    respuesta = client.get(URL_CONVENIOS, params={
        "buscar": f"{prefijo}{caracter}", "estado": "VIGENTE",
        "tipo_contraparte": "EMPRESA",
    })
    assert respuesta.status_code == 200
    assert [item["id"] for item in respuesta.json()["items"]] == [objetivo.id]


@pytest.mark.parametrize("tipo_fecha", ["FORMALIZACION", "VIGENCIA"])
def test_and_entre_categorias_or_dentro_y_total_paginado(
    db, client, administrador, crear_filtrable, tipo_fecha
):
    termino = f"and-or-{uuid4().hex}"
    programa = _crear_programa(db, "Programa AND/OR")
    datos = {"objeto": termino, "alcance": AlcanceConvenio.PROGRAMA, "unidad_organizacional_id": programa.id}
    esperados = [
        crear_filtrable(**datos),
        crear_filtrable(**datos, estado=EstadoConvenio.POR_VENCER, tipo=TipoAliado.COLEGIO),
        crear_filtrable(**datos, tipo=TipoAliado.COLEGIO),
    ]
    crear_filtrable(**datos, estado=EstadoConvenio.CANCELADO)
    crear_filtrable(**datos, tipo=TipoAliado.UNIVERSIDAD)
    crear_filtrable(objeto=termino)
    crear_filtrable(**{**datos, "objeto": f"otro-{uuid4().hex}"})
    fuera = crear_filtrable(**datos, firma=date(2025, 1, 1))
    fuera.fecha_inicio = date(2025, 1, 1)
    fuera.fecha_vencimiento = date(2025, 12, 31)
    db.commit()
    parametros = {
        "buscar": termino, "estado": ["VIGENTE", "POR_VENCER"],
        "tipo_contraparte": ["EMPRESA", "COLEGIO"], "programa_id": programa.id,
        "tipo_fecha": tipo_fecha, "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
        "limite": 1,
    }
    for desplazamiento, convenio in enumerate(reversed(esperados)):
        respuesta = client.get(URL_CONVENIOS, params={**parametros, "desplazamiento": desplazamiento})
        assert respuesta.status_code == 200
        assert respuesta.json()["total"] == 3
        assert [item["id"] for item in respuesta.json()["items"]] == [convenio.id]


@pytest.mark.parametrize("tipo_fecha", ["FORMALIZACION", "VIGENCIA"])
def test_revisor_historico_filtra_sin_obtener_acceso_operativo(
    db, client, crear_usuario, entrar_como, crear_filtrable, tipo_fecha
):
    revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    tercero = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    programa = _crear_programa(db, "Programa del historial")
    termino = f"historico-{uuid4().hex}"
    datos = {"objeto": termino, "alcance": AlcanceConvenio.PROGRAMA, "unidad_organizacional_id": programa.id}
    convenio = crear_filtrable(**datos)
    crear_filtrable(**datos)  # Mismos filtros, sin participación autorizada.
    db.add(RevisionConvenio(
        convenio_id=convenio.id, tipo="JURIDICA", estado="RESUELTA",
        resultado="APROBADA", resuelta_por_id=revisor.id,
    ))
    db.commit()
    parametros = {
        "buscar": termino, "estado": "VIGENTE", "tipo_contraparte": "EMPRESA",
        "programa_id": programa.id, "tipo_fecha": tipo_fecha,
        "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
    }
    entrar_como(revisor)
    for filtros in (parametros, {"buscar": termino}):
        respuesta = client.get(URL_CONVENIOS, params=filtros)
        assert respuesta.status_code == 200
        assert respuesta.json()["total"] == 1
        assert respuesta.json()["items"][0]["id"] == convenio.id
        assert respuesta.json()["items"][0]["puede_ver_detalle"] is False
    assert client.get(f"{URL_CONVENIOS}/{convenio.id}/revisiones").status_code == 200
    assert client.get(f"{URL_CONVENIOS}/{convenio.id}").status_code == 404
    entrar_como(tercero)
    respuesta = client.get(URL_CONVENIOS, params=parametros)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"items": [], "total": 0}
    assert client.get(f"{URL_CONVENIOS}/{convenio.id}/revisiones").status_code == 404


@pytest.mark.parametrize("tipo", list(TipoAliado))
@pytest.mark.parametrize("formal", [False, True])
def test_cuatro_tipos_para_aliados_y_propuestas_con_precedencia_formal(
    db, client, administrador, crear_filtrable, tipo, formal
):
    convenio = crear_filtrable(tipo=tipo)
    if formal:
        convenio.aliado = _crear_aliado(db, f"Aliado-{uuid4().hex}", tipo)
        convenio.solicitud.tipo_aliado_propuesto = next(t.value for t in TipoAliado if t != tipo)
        db.commit()
    respuesta = client.get(URL_CONVENIOS, params={
        "buscar": f"#{convenio.id}", "tipo_contraparte": tipo.value,
    })
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1
    assert respuesta.json()["items"][0]["contraparte"]["tipo"] == tipo.value
    assert respuesta.json()["items"][0]["contraparte"]["es_aliado_formal"] is formal
    if formal:
        propuesta = client.get(URL_CONVENIOS, params={
            "buscar": f"#{convenio.id}",
            "tipo_contraparte": convenio.solicitud.tipo_aliado_propuesto,
        })
        assert propuesta.status_code == 200
        assert propuesta.json() == {"items": [], "total": 0}


def test_filtros_avanzados_paginacion_catalogo_y_limpieza_solo_lectura(
    db, client, administrador, crear_filtrable
):
    termino = f"solo-lectura-{uuid4().hex}"
    crear_filtrable(objeto=termino)
    crear_filtrable(objeto=termino)
    sentencias = []
    def registrar(conn, cursor, statement, parameters, context, executemany):
        sentencias.append(statement.strip().split()[0].upper())
    conexion = db.connection()
    event.listen(conexion, "before_cursor_execute", registrar)
    try:
        for parametros in (
            {"estado": "VIGENTE", "alcance": "INSTITUCIONAL", "tipo_contraparte": "EMPRESA", "limite": 1},
            {"estado": "VIGENTE", "alcance": "INSTITUCIONAL", "tipo_contraparte": "EMPRESA", "limite": 1, "desplazamiento": 1},
            {},
        ):
            respuesta = client.get(URL_CONVENIOS, params={"buscar": termino, **parametros})
            assert respuesta.status_code == 200
            assert respuesta.json()["total"] == 2
        assert client.get(URL_CATALOGOS).status_code == 200
    finally:
        event.remove(conexion, "before_cursor_execute", registrar)
    assert "SELECT" in sentencias
    assert not {"INSERT", "UPDATE", "DELETE"}.intersection(sentencias)
