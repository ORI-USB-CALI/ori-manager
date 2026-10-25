from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.routers import auditoria
from backend.core.permisos import Permiso, permisos_para_rol
from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.enums import TipoAliado, TipoIdentificacion
from backend.models.usuario import Usuario

URL = "/api/auditoria"


def _fecha(dia: int, hora: int = 12) -> datetime:
    return datetime(2026, 3, dia, hora, tzinfo=UTC)


@pytest.fixture
def administrador(crear_usuario, entrar_como) -> Usuario:
    usuario = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    entrar_como(usuario)
    return usuario


@pytest.fixture
def actor(crear_usuario) -> Usuario:
    return crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)


@pytest.fixture
def registrar(db: Session) -> Callable[..., Auditoria]:
    def _registrar(
        usuario: Usuario,
        *,
        fecha_hora: datetime,
        entidad: str = "convenio",
        registro_id: int = 1,
        accion: str = "UPDATE",
        campo: str | None = "objeto",
        rol: str | None = None,
    ) -> Auditoria:
        fila = Auditoria(
            usuario_id=usuario.id,
            entidad=entidad,
            registro_id=registro_id,
            accion=accion,
            campo=campo,
            valor_anterior="antes",
            valor_nuevo="después",
            contexto="Editó el convenio",
            rol=rol,
            fecha_hora=fecha_hora,
        )
        db.add(fila)
        db.commit()
        db.refresh(fila)
        return fila

    return _registrar


def _consultar(client, **params) -> dict:
    respuesta = client.get(URL, params=params)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


# ---- CA-04: restringir el acceso --------------------------------------------


def test_consultar_bitacora_es_exclusivo_del_administrador_ori() -> None:
    assert {
        rol for rol in CodigoRol if Permiso.AUDITORIA_VER in permisos_para_rol(rol)
    } == {CodigoRol.ADMINISTRADOR_ORI}


@pytest.mark.parametrize(
    "codigo_rol",
    [
        CodigoRol.GESTOR_ORI,
        CodigoRol.REVISOR_ORI,
        CodigoRol.SOLICITANTE_INTERNO,
        CodigoRol.SOLICITANTE_EXTERNO,
    ],
)
def test_usuario_sin_permiso_no_puede_consultar_la_bitacora(
    client, crear_usuario, entrar_como, codigo_rol
) -> None:
    tipo = (
        TipoUsuario.EXTERNO
        if codigo_rol == CodigoRol.SOLICITANTE_EXTERNO
        else TipoUsuario.INTERNO
    )
    entrar_como(crear_usuario(codigo_rol, tipo))

    respuesta = client.get(URL)

    assert respuesta.status_code == 403


def test_sin_sesion_no_puede_consultar_la_bitacora(client) -> None:
    assert client.get(URL).status_code == 401


def test_la_bitacora_solo_expone_consulta() -> None:
    metodos = {metodo for ruta in auditoria.router.routes for metodo in ruta.methods}

    assert metodos == {"GET"}


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_no_se_pueden_crear_editar_ni_borrar_registros(
    db, client, administrador, actor, registrar, metodo
) -> None:
    fila = registrar(actor, fecha_hora=_fecha(1))

    coleccion = getattr(client, metodo)(URL)
    individual = getattr(client, metodo)(f"{URL}/{fila.id}")

    assert coleccion.status_code == 405
    assert individual.status_code in {404, 405}
    db.expire_all()
    assert db.get(Auditoria, fila.id).valor_nuevo == "después"


# ---- CA-01 y CA-02: registro automático con responsable y fecha -------------


def test_modificacion_por_api_aparece_con_usuario_y_fecha(
    client, gestor, crear_usuario, entrar_como, db
) -> None:
    aliado = Aliado(
        nombre="Universidad aliada",
        tipo=TipoAliado.UNIVERSIDAD.value,
        tipo_identificacion=TipoIdentificacion.NIT.value,
        identificacion=str(900000000 + uuid4().int % 99999999),
        correo="contacto@aliada.example",
        activo=True,
    )
    db.add(aliado)
    db.commit()
    assert client.patch(
        f"/api/aliados/{aliado.id}", json={"nombre": "Universidad renombrada"}
    ).status_code == 200
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO))

    datos = _consultar(client, entidad="aliado", registro_id=aliado.id)

    assert datos["total"] == 1
    registro = datos["items"][0]
    assert registro["accion"] == "UPDATE"
    assert registro["campo"] == "nombre"
    assert registro["valor_anterior"] == "Universidad aliada"
    assert registro["valor_nuevo"] == "Universidad renombrada"
    assert registro["rol"] == CodigoRol.GESTOR_ORI.value
    assert registro["usuario"] == {
        "id": gestor.id,
        "nombre_completo": gestor.nombre_completo,
        "correo": gestor.correo,
    }
    assert datetime.fromisoformat(registro["fecha_hora"]).tzinfo is not None


def test_el_registro_incluye_los_datos_de_la_accion(
    client, administrador, actor, registrar
) -> None:
    fila = registrar(actor, fecha_hora=_fecha(5, 9), entidad="convenio", registro_id=7)

    registro = _consultar(client, usuario_id=actor.id)["items"][0]

    assert registro == {
        "id": fila.id,
        "fecha_hora": registro["fecha_hora"],
        "usuario": {
            "id": actor.id,
            "nombre_completo": actor.nombre_completo,
            "correo": actor.correo,
        },
        "rol": CodigoRol.GESTOR_ORI.value,
        "entidad": "convenio",
        "registro_id": 7,
        "accion": "UPDATE",
        "campo": "objeto",
        "valor_anterior": "antes",
        "valor_nuevo": "después",
        "contexto": "Editó el convenio",
        "evento": None,
        "etapa": None,
        "version": None,
        "ejecucion": None,
        "responsable": None,
    }
    assert datetime.fromisoformat(registro["fecha_hora"]) == _fecha(5, 9)


# ---- CA-03: historial cronológico sin sobrescribir --------------------------


def test_registros_se_listan_en_orden_cronologico_por_defecto(
    client, administrador, actor, registrar
) -> None:
    tercero = registrar(actor, fecha_hora=_fecha(3))
    primero = registrar(actor, fecha_hora=_fecha(1))
    segundo = registrar(actor, fecha_hora=_fecha(2))

    datos = _consultar(client, usuario_id=actor.id)

    assert [r["id"] for r in datos["items"]] == [primero.id, segundo.id, tercero.id]


def test_orden_descendente_invierte_la_cronologia(
    client, administrador, actor, registrar
) -> None:
    primero = registrar(actor, fecha_hora=_fecha(1))
    tercero = registrar(actor, fecha_hora=_fecha(3))
    segundo = registrar(actor, fecha_hora=_fecha(2))

    datos = _consultar(client, usuario_id=actor.id, orden="desc")

    assert [r["id"] for r in datos["items"]] == [tercero.id, segundo.id, primero.id]


def test_registros_simultaneos_conservan_el_orden_de_insercion(
    client, administrador, actor, registrar
) -> None:
    filas = [registrar(actor, fecha_hora=_fecha(4)) for _ in range(3)]

    ascendente = _consultar(client, usuario_id=actor.id)
    descendente = _consultar(client, usuario_id=actor.id, orden="desc")

    ids = [fila.id for fila in filas]
    assert [r["id"] for r in ascendente["items"]] == ids
    assert [r["id"] for r in descendente["items"]] == ids[::-1]


def test_varias_acciones_sobre_un_convenio_se_conservan(
    client, administrador, actor, registrar
) -> None:
    registro_id = uuid4().int % 1_000_000_000
    for dia in (1, 2, 3):
        registrar(actor, fecha_hora=_fecha(dia), registro_id=registro_id)

    datos = _consultar(client, entidad="convenio", registro_id=registro_id)

    assert datos["total"] == 3
    assert len({r["id"] for r in datos["items"]}) == 3


def test_orden_invalido_es_rechazado(client, administrador) -> None:
    assert client.get(URL, params={"orden": "aleatorio"}).status_code == 422


# ---- Filtros -----------------------------------------------------------------


def test_filtra_por_entidad_y_registro(
    client, administrador, actor, registrar
) -> None:
    esperado = registrar(actor, fecha_hora=_fecha(1), entidad="convenio", registro_id=10)
    registrar(actor, fecha_hora=_fecha(1), entidad="convenio", registro_id=11)
    registrar(actor, fecha_hora=_fecha(1), entidad="aliado", registro_id=10)

    datos = _consultar(
        client, usuario_id=actor.id, entidad="convenio", registro_id=10
    )

    assert [r["id"] for r in datos["items"]] == [esperado.id]


def test_filtra_por_usuario(
    client, administrador, actor, crear_usuario, registrar
) -> None:
    otro = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    esperado = registrar(actor, fecha_hora=_fecha(1))
    registrar(otro, fecha_hora=_fecha(1))

    datos = _consultar(client, usuario_id=actor.id)

    assert [r["id"] for r in datos["items"]] == [esperado.id]


def test_filtra_por_rol_y_accion(
    client, administrador, actor, registrar
) -> None:
    esperado = registrar(
        actor, fecha_hora=_fecha(1), accion="INSERT", campo=None,
        rol=CodigoRol.REVISOR_ORI.value,
    )
    registrar(actor, fecha_hora=_fecha(1), accion="UPDATE", rol=CodigoRol.REVISOR_ORI.value)
    registrar(actor, fecha_hora=_fecha(1), accion="INSERT", campo=None)

    datos = _consultar(
        client, usuario_id=actor.id, rol=CodigoRol.REVISOR_ORI.value, accion="INSERT"
    )

    assert [r["id"] for r in datos["items"]] == [esperado.id]


def test_filtra_por_rango_de_fechas_inclusivo(
    client, administrador, actor, registrar
) -> None:
    registrar(actor, fecha_hora=_fecha(1))
    desde = registrar(actor, fecha_hora=_fecha(2))
    hasta = registrar(actor, fecha_hora=_fecha(3))
    registrar(actor, fecha_hora=_fecha(4))

    datos = _consultar(
        client,
        usuario_id=actor.id,
        desde=_fecha(2).isoformat(),
        hasta=_fecha(3).isoformat(),
    )

    assert [r["id"] for r in datos["items"]] == [desde.id, hasta.id]


def test_rango_de_fechas_invertido_es_rechazado(client, administrador) -> None:
    respuesta = client.get(
        URL, params={"desde": _fecha(3).isoformat(), "hasta": _fecha(1).isoformat()}
    )

    assert respuesta.status_code == 422


def test_accion_invalida_es_rechazada(client, administrador) -> None:
    assert client.get(URL, params={"accion": "BORRAR"}).status_code == 422


# ---- Paginación --------------------------------------------------------------


def test_pagina_con_limite_y_desplazamiento_e_informa_el_total(
    client, administrador, actor, registrar
) -> None:
    filas = [registrar(actor, fecha_hora=_fecha(dia)) for dia in range(1, 6)]

    datos = _consultar(client, usuario_id=actor.id, limite=2, desplazamiento=2)

    assert datos["total"] == 5
    assert [r["id"] for r in datos["items"]] == [filas[2].id, filas[3].id]


@pytest.mark.parametrize(
    "params",
    [{"limite": 0}, {"limite": 101}, {"desplazamiento": -1}],
)
def test_paginacion_fuera_de_rango_es_rechazada(
    client, administrador, params
) -> None:
    assert client.get(URL, params=params).status_code == 422


def test_consultar_no_genera_registros_en_la_bitacora(
    db, client, administrador
) -> None:
    _consultar(client)

    assert db.scalars(
        select(Auditoria).where(Auditoria.usuario_id == administrador.id)
    ).all() == []
