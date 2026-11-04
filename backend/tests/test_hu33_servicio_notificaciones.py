"""HU-33 tarea 7: permisos, lectura, resolución y duplicados a nivel de servicio."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.enums import EntidadNotificacion, TipoNotificacion
from backend.models.notificacion import Notificacion
from backend.services.convenios import ServicioConvenios
from backend.services.notificaciones import ServicioNotificaciones


def test_crear_no_duplica_mientras_este_pendiente(db, gestor):
    servicio = ServicioNotificaciones(db)

    primera = servicio.crear(
        gestor.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        1,
        "Primer mensaje",
    )
    segunda = servicio.crear(
        gestor.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        1,
        "Segundo mensaje, no debe crear fila nueva",
    )

    assert primera.id == segunda.id
    assert segunda.mensaje == "Primer mensaje"
    total = db.scalar(
        select(Notificacion)
        .where(
            Notificacion.usuario_id == gestor.id,
            Notificacion.tipo == TipoNotificacion.REVISION_JURIDICA_PENDIENTE.value,
            Notificacion.entidad_id == 1,
        )
    )
    assert total is not None
    filas = list(
        db.scalars(
            select(Notificacion).where(
                Notificacion.usuario_id == gestor.id,
                Notificacion.tipo
                == TipoNotificacion.REVISION_JURIDICA_PENDIENTE.value,
                Notificacion.entidad_id == 1,
            )
        )
    )
    assert len(filas) == 1


def test_crear_permite_una_nueva_tras_resolver_la_anterior(db, gestor):
    servicio = ServicioNotificaciones(db)
    primera = servicio.crear(
        gestor.id,
        TipoNotificacion.SOLICITUD_DEVUELTA,
        EntidadNotificacion.SOLICITUD,
        5,
        "Primera devolución",
    )

    servicio.resolver(
        TipoNotificacion.SOLICITUD_DEVUELTA, EntidadNotificacion.SOLICITUD, 5
    )
    segunda = servicio.crear(
        gestor.id,
        TipoNotificacion.SOLICITUD_DEVUELTA,
        EntidadNotificacion.SOLICITUD,
        5,
        "Segunda devolución",
    )

    assert segunda.id != primera.id
    filas = list(
        db.scalars(
            select(Notificacion).where(
                Notificacion.usuario_id == gestor.id,
                Notificacion.tipo == TipoNotificacion.SOLICITUD_DEVUELTA.value,
                Notificacion.entidad_id == 5,
            )
        )
    )
    assert len(filas) == 2
    assert sum(1 for f in filas if not f.resuelta) == 1


def test_crear_para_rol_excluye_usuarios_inactivos(db, revisor, crear_usuario):
    inactivo = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO, activo=False)

    creadas = ServicioNotificaciones(db).crear_para_rol(
        CodigoRol.REVISOR_ORI,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        7,
        "Convenio pendiente de revisión",
    )

    destinatarios = {n.usuario_id for n in creadas}
    assert revisor.id in destinatarios
    assert inactivo.id not in destinatarios


def test_crear_para_rol_no_notifica_a_otros_roles(db, revisor, gestor):
    creadas = ServicioNotificaciones(db).crear_para_rol(
        CodigoRol.REVISOR_ORI,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        8,
        "Convenio pendiente de revisión",
    )

    destinatarios = {n.usuario_id for n in creadas}
    assert gestor.id not in destinatarios


def test_marcar_leida_es_idempotente(db, gestor):
    servicio = ServicioNotificaciones(db)
    notificacion = servicio.crear(
        gestor.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        9,
        "Mensaje",
    )

    primera = servicio.marcar_leida(notificacion.id, gestor)
    leida_en_primera = primera.leida_en
    segunda = servicio.marcar_leida(notificacion.id, gestor)

    assert segunda.leida is True
    assert segunda.leida_en == leida_en_primera


def test_resolver_sin_pendientes_no_hace_nada(db):
    # No debe lanzar ni fallar aunque no exista ninguna fila para esa entidad.
    ServicioNotificaciones(db).resolver(
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        999999,
    )


def test_resolver_no_afecta_una_entidad_distinta(db, gestor):
    servicio = ServicioNotificaciones(db)
    de_otro_convenio = servicio.crear(
        gestor.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        10,
        "Convenio 10",
    )

    servicio.resolver(
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        11,
    )

    db.refresh(de_otro_convenio)
    assert de_otro_convenio.resuelta is False


# ---- Consistencia transaccional (code review HU-33 PR) --------------------


def test_crear_no_sobrevive_si_la_transaccion_del_llamador_revierte(db, gestor):
    """crear() nunca hace commit por su cuenta: si quien la llamó revierte
    su propia transacción, la notificación desaparece con ella.
    """
    servicio = ServicioNotificaciones(db)

    try:
        servicio.crear(
            gestor.id,
            TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
            EntidadNotificacion.CONVENIO,
            123,
            "mensaje",
        )
        raise RuntimeError("fallo simulado antes del commit del llamador")
    except RuntimeError:
        db.rollback()

    filas = list(
        db.scalars(select(Notificacion).where(Notificacion.entidad_id == 123))
    )
    assert filas == []


def test_fallo_real_de_persistencia_no_rompe_la_sesion_del_llamador(db):
    """Un fallo genuino (no de deduplicación, p. ej. una FK inválida) debe
    propagarse, pero sin dejar la sesión del llamador inutilizable: el
    SAVEPOINT de crear() se revierte solo, no toda la transacción.
    """
    servicio = ServicioNotificaciones(db)

    with pytest.raises(IntegrityError):
        servicio.crear(
            999_999_999,  # usuario_id inexistente: viola la FK, no es duplicado
            TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
            EntidadNotificacion.CONVENIO,
            1,
            "mensaje",
        )

    # La sesión sigue utilizable tras el fallo: una consulta normal no rompe.
    assert (
        db.scalar(
            select(Notificacion).where(Notificacion.entidad_id == 1)
        )
        is None
    )


def test_crear_para_rol_es_todo_o_nada_si_la_transaccion_revierte(
    db, revisor, crear_usuario
):
    """Si la transacción del llamador revierte después de crear_para_rol(),
    ningún destinatario queda notificado (no hay entregas parciales).
    """
    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    servicio = ServicioNotificaciones(db)

    try:
        servicio.crear_para_rol(
            CodigoRol.REVISOR_ORI,
            TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
            EntidadNotificacion.CONVENIO,
            55,
            "mensaje",
        )
        raise RuntimeError("fallo simulado antes del commit del llamador")
    except RuntimeError:
        db.rollback()

    for destinatario in (revisor, otro_revisor):
        filas = list(
            db.scalars(
                select(Notificacion).where(
                    Notificacion.usuario_id == destinatario.id,
                    Notificacion.entidad_id == 55,
                )
            )
        )
        assert filas == []


def test_finalizar_elaboracion_revierte_notificaciones_si_falla_antes_del_commit(
    db, gestor, revisor, convenio_listo, monkeypatch
):
    """Prueba de extremo a extremo: si algo falla dentro de la transacción
    de negocio después de generar las notificaciones pero antes del
    commit, ni el cambio de etapa ni las notificaciones quedan.
    """

    def _resolver_que_falla(self, *args, **kwargs):
        raise RuntimeError("fallo simulado de persistencia")

    monkeypatch.setattr(ServicioNotificaciones, "resolver", _resolver_que_falla)

    with pytest.raises(RuntimeError):
        ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    db.rollback()

    assert not list(
        db.scalars(
            select(Notificacion).where(
                Notificacion.entidad_id == convenio_listo.id
            )
        )
    )
    db.refresh(convenio_listo)
    assert convenio_listo.etapa_actual.codigo == "ELABORACION"
