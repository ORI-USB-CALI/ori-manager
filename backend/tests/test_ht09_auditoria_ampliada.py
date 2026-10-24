"""HT-09: completar la información y autoría de la bitácora de auditoría.

Cubre lo que agrega HT-09 sobre la bitácora de HU-18: evento, etapa, versión
y responsable estructurados, y la distinción entre ejecución humana y
automática sin usuarios ficticios.
"""

from collections.abc import Callable
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.enums import TipoAliado, TipoIdentificacion
from backend.models.usuario import Usuario
from backend.schemas.convenio import ConvenioElaboracionActualizar
from backend.services.bitacora import (
    asignar_actor,
    describir_accion,
    describir_accion_automatica,
)
from backend.services.convenios import ServicioConvenios

URL_AUDITORIA = "/api/auditoria"


@pytest.fixture
def administrador(crear_usuario, entrar_como) -> Usuario:
    usuario = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    entrar_como(usuario)
    return usuario


@pytest.fixture
def crear_aliado(db: Session) -> Callable[[], Aliado]:
    def _crear() -> Aliado:
        aliado = Aliado(
            nombre="Universidad aliada HT-09",
            tipo=TipoAliado.UNIVERSIDAD.value,
            tipo_identificacion=TipoIdentificacion.NIT.value,
            identificacion=uuid4().hex,
            activo=True,
        )
        db.add(aliado)
        db.commit()
        db.refresh(aliado)
        return aliado

    return _crear


def _ultima_fila(db: Session, entidad: str, registro_id: int) -> Auditoria:
    return db.scalars(
        select(Auditoria)
        .where(Auditoria.entidad == entidad, Auditoria.registro_id == registro_id)
        .order_by(Auditoria.id.desc())
    ).first()


# ---- CA-01: etapa y versión estructuradas ----------------------------------


def test_evento_etapa_y_version_quedan_estructurados(
    db: Session, gestor: Usuario, crear_aliado
) -> None:
    aliado = crear_aliado()
    describir_accion(
        db,
        gestor,
        "Actualizó el aliado",
        evento="ALIADO_EDITADO",
        etapa="ELABORACION",
        version=3,
    )
    aliado.nombre = "Nuevo nombre"
    db.commit()

    fila = _ultima_fila(db, "aliado", aliado.id)
    assert fila.evento == "ALIADO_EDITADO"
    assert fila.etapa == "ELABORACION"
    assert fila.version == 3
    # No depende solamente del texto libre de contexto.
    assert fila.contexto == "Actualizó el aliado"


# ---- CA-02/CA-03: originador humano vs. ejecución automática --------------


def test_accion_humana_conserva_usuario_y_rol(
    db: Session, gestor: Usuario, crear_aliado
) -> None:
    aliado = crear_aliado()
    describir_accion(db, gestor, "Actualizó el aliado", evento="ALIADO_EDITADO")
    aliado.nombre = "Otro nombre"
    db.commit()

    fila = _ultima_fila(db, "aliado", aliado.id)
    assert fila.usuario_id == gestor.id
    assert fila.rol == gestor.rol.codigo
    assert fila.ejecucion == "HUMANA"


def test_proceso_automatico_no_usa_usuario_ficticio(
    db: Session, crear_aliado
) -> None:
    total_usuarios_antes = db.scalar(select(func.count()).select_from(Usuario))
    aliado = crear_aliado()
    describir_accion_automatica(
        db, "Concilió el estado del aliado", evento="ALIADO_CONCILIADO"
    )
    aliado.activo = False
    db.commit()

    fila = _ultima_fila(db, "aliado", aliado.id)
    assert fila.usuario_id is None
    assert fila.rol is None
    assert fila.ejecucion == "AUTOMATICA"
    assert fila.evento == "ALIADO_CONCILIADO"
    # El proceso automático no creó ningún usuario para representarse.
    total_usuarios_despues = db.scalar(select(func.count()).select_from(Usuario))
    assert total_usuarios_despues == total_usuarios_antes


def test_sin_describir_accion_la_ejecucion_queda_sin_declarar(
    db: Session, gestor: Usuario, crear_aliado
) -> None:
    """RN-02: la ejecución no se deduce solo porque el backend procesó el
    cambio; si nadie la declara, queda nula, no HUMANA por defecto."""
    aliado = crear_aliado()
    asignar_actor(db, gestor)
    aliado.nombre = "Cambio sin describir_accion"
    db.commit()

    fila = _ultima_fila(db, "aliado", aliado.id)
    assert fila.usuario_id == gestor.id
    assert fila.ejecucion is None
    assert fila.evento is None


# ---- CA-04: responsable de negocio distinto del originador -----------------


def test_responsable_de_negocio_es_distinto_del_originador(
    db: Session, gestor: Usuario, crear_usuario, crear_aliado
) -> None:
    otro = crear_usuario()
    aliado = crear_aliado()
    describir_accion(
        db,
        gestor,
        "Actualizó el aliado en nombre de otro responsable",
        evento="ALIADO_EDITADO",
        responsable_id=otro.id,
    )
    aliado.nombre = "Nombre con responsable distinto"
    db.commit()

    fila = _ultima_fila(db, "aliado", aliado.id)
    assert fila.usuario_id == gestor.id
    assert fila.responsable_id == otro.id
    assert fila.usuario_id != fila.responsable_id


# ---- CA-05: contexto funcional de acciones ya existentes -------------------


def test_editar_convenio_registra_evento_etapa_version_y_responsable(
    db: Session, gestor: Usuario, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)
    etapa_esperada = convenio.etapa_actual.codigo
    version_esperada = convenio.version_actual

    ServicioConvenios(db).actualizar(
        convenio.id,
        ConvenioElaboracionActualizar(objeto="Objeto editado por HT-09"),
        gestor,
    )

    fila = _ultima_fila(db, "convenio", convenio.id)
    assert fila.evento == "CONVENIO_EDITADO"
    assert fila.etapa == etapa_esperada
    assert fila.version == version_esperada
    assert fila.responsable_id == convenio.creado_por_id
    assert fila.ejecucion == "HUMANA"


# ---- CA-06: la API expone los campos nuevos --------------------------------


def test_api_auditoria_expone_los_campos_de_ht09(
    client, gestor, administrador, crear_aliado, db
) -> None:
    aliado = crear_aliado()
    describir_accion(
        db,
        gestor,
        "Actualizó el aliado",
        evento="ALIADO_EDITADO",
        etapa="ELABORACION",
        version=1,
    )
    aliado.nombre = "Visible por la API"
    db.commit()

    respuesta = client.get(
        URL_AUDITORIA, params={"entidad": "aliado", "registro_id": aliado.id}
    )
    assert respuesta.status_code == 200
    (item,) = respuesta.json()["items"]
    assert item["evento"] == "ALIADO_EDITADO"
    assert item["etapa"] == "ELABORACION"
    assert item["version"] == 1
    assert item["ejecucion"] == "HUMANA"
    assert item["usuario"]["id"] == gestor.id


def test_api_auditoria_muestra_null_para_proceso_automatico(
    client, administrador, crear_aliado, db
) -> None:
    aliado = crear_aliado()
    describir_accion_automatica(db, "Concilió el aliado", evento="ALIADO_CONCILIADO")
    aliado.activo = False
    db.commit()

    respuesta = client.get(
        URL_AUDITORIA, params={"entidad": "aliado", "registro_id": aliado.id}
    )
    assert respuesta.status_code == 200
    (item,) = respuesta.json()["items"]
    assert item["usuario"] is None
    assert item["ejecucion"] == "AUTOMATICA"
    assert item["evento"] == "ALIADO_CONCILIADO"


# ---- CA-07: compatibilidad con registros históricos ------------------------


def test_registro_historico_sin_campos_nuevos_se_lee_sin_error(
    client, gestor, administrador, db
) -> None:
    """Simula un registro insertado antes de HT-09: evento/etapa/version/
    ejecucion/responsable_id nulos. No se completan retroactivamente."""
    fila = Auditoria(
        usuario_id=gestor.id,
        rol=gestor.rol.codigo,
        entidad="convenio",
        registro_id=999999,
        accion="UPDATE",
        campo="objeto",
        valor_anterior="antes",
        valor_nuevo="después",
        contexto="Editó el convenio (histórico, previo a HT-09)",
    )
    db.add(fila)
    db.commit()

    respuesta = client.get(
        URL_AUDITORIA, params={"entidad": "convenio", "registro_id": 999999}
    )
    assert respuesta.status_code == 200
    (item,) = respuesta.json()["items"]
    assert item["evento"] is None
    assert item["etapa"] is None
    assert item["version"] is None
    assert item["ejecucion"] is None
    assert item["responsable"] is None


# ---- CA-08: integridad de la base ------------------------------------------


def test_bd_rechaza_ejecucion_automatica_sin_usuario_ni_marca(
    db: Session, gestor: Usuario
) -> None:
    """ck_auditoria_usuario_o_automatica: toda fila sin usuario_id debe
    declararse explícitamente AUTOMATICA; no puede quedar sin ninguno."""
    db.add(
        Auditoria(
            usuario_id=None,
            entidad="convenio",
            registro_id=1,
            accion="UPDATE",
            contexto="Fila inválida: sin usuario y sin ejecución automática",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_bd_rechaza_valor_de_ejecucion_invalido(db: Session, gestor: Usuario) -> None:
    db.add(
        Auditoria(
            usuario_id=gestor.id,
            rol=gestor.rol.codigo,
            entidad="convenio",
            registro_id=1,
            accion="UPDATE",
            ejecucion="NO_EXISTE",
            contexto="Fila inválida: ejecución fuera de catálogo",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_automatica_con_usuario_no_viola_la_restriccion(
    db: Session, gestor: Usuario
) -> None:
    """El CHECK solo exige usuario_id o AUTOMATICA; un proceso automático
    que sí conoce el usuario originador (por ejemplo, uno disparado por una
    acción suya) no está prohibido."""
    db.add(
        Auditoria(
            usuario_id=gestor.id,
            rol=gestor.rol.codigo,
            entidad="convenio",
            registro_id=1,
            accion="UPDATE",
            ejecucion="AUTOMATICA",
            contexto="Proceso automático que conserva el usuario originador",
        )
    )
    db.commit()
