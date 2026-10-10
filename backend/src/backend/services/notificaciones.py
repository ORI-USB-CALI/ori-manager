from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol
from backend.models.enums import EntidadNotificacion, TipoNotificacion
from backend.models.notificacion import Notificacion
from backend.models.rol import Rol
from backend.models.usuario import Usuario
from backend.services.notificaciones_realtime import gestor_notificaciones_tiempo_real


class ErrorNotificacion(Exception):
    pass


class NotificacionNoEncontrada(ErrorNotificacion):
    pass


class ServicioNotificaciones:
    """Servicio central de HU-33.

    No sabe nada de convenios, solicitudes ni del resto del dominio: solo
    crea, lista, marca como leída y resuelve filas de `Notificacion`. Quien
    detecta que ocurrió un evento del flujo (tarea 3 de la HU) es quien
    decide el tipo, la entidad y el mensaje, y llama a este servicio.
    """

    def __init__(self, db: Session):
        self.db = db

    def crear(
        self,
        usuario_id: int,
        tipo: TipoNotificacion,
        entidad_tipo: EntidadNotificacion,
        entidad_id: int,
        mensaje: str,
    ) -> Notificacion:
        """CA-01/CA-09: crea la notificación, o devuelve la que ya existía
        sin resolver para ese mismo usuario+tipo+entidad (deduplicación).
        """
        notificacion = Notificacion(
            usuario_id=usuario_id,
            tipo=tipo.value,
            entidad_tipo=entidad_tipo.value,
            entidad_id=entidad_id,
            mensaje=mensaje,
        )
        self.db.add(notificacion)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existente = self.db.scalar(
                select(Notificacion).where(
                    Notificacion.usuario_id == usuario_id,
                    Notificacion.tipo == tipo.value,
                    Notificacion.entidad_tipo == entidad_tipo.value,
                    Notificacion.entidad_id == entidad_id,
                    Notificacion.resuelta.is_(False),
                )
            )
            if existente is None:
                raise
            return existente
        gestor_notificaciones_tiempo_real.marcar_cambio(usuario_id)
        return notificacion

    def crear_para_rol(
        self,
        codigo_rol: CodigoRol,
        tipo: TipoNotificacion,
        entidad_tipo: EntidadNotificacion,
        entidad_id: int,
        mensaje: str,
    ) -> list[Notificacion]:
        """CA-03/CA-06: estas revisiones no están asignadas a una persona
        específica (cualquier usuario con el rol puede atenderlas), así que
        se notifica a todos los usuarios activos de ese rol.
        """
        usuarios_ids = self.db.scalars(
            select(Usuario.id)
            .join(Usuario.rol)
            .where(Rol.codigo == codigo_rol.value, Usuario.activo.is_(True))
        ).all()
        return [
            self.crear(usuario_id, tipo, entidad_tipo, entidad_id, mensaje)
            for usuario_id in usuarios_ids
        ]

    def listar_para_usuario(self, usuario: Usuario) -> list[Notificacion]:
        """CA-02: únicamente las notificaciones del usuario autenticado.

        Se ordena por `id` (no por `creado_en`): Postgres resuelve
        `func.now()` una sola vez por transacción, así que varias
        notificaciones creadas dentro de la misma transacción quedan con el
        mismo `creado_en` y no alcanzaría para ordenar la más reciente
        primero.
        """
        return list(
            self.db.scalars(
                select(Notificacion)
                .where(Notificacion.usuario_id == usuario.id)
                .order_by(Notificacion.id.desc())
            )
        )

    def marcar_leida(self, notificacion_id: int, usuario: Usuario) -> Notificacion:
        """CA-08."""
        notificacion = self.db.get(Notificacion, notificacion_id)
        if notificacion is None or notificacion.usuario_id != usuario.id:
            raise NotificacionNoEncontrada(
                "No existe esa notificación para este usuario"
            )
        if not notificacion.leida:
            notificacion.leida = True
            notificacion.leida_en = datetime.now(UTC)
            self.db.commit()
        return notificacion

    def resolver(
        self,
        tipo: TipoNotificacion,
        entidad_tipo: EntidadNotificacion,
        entidad_id: int,
    ) -> None:
        """CA-09: cuando la acción pendiente ya se completó, deja de
        presentarse como pendiente a todos sus destinatarios (puede haber
        varios, si se generó por rol vía `crear_para_rol`).
        """
        pendientes = self.db.scalars(
            select(Notificacion).where(
                Notificacion.tipo == tipo.value,
                Notificacion.entidad_tipo == entidad_tipo.value,
                Notificacion.entidad_id == entidad_id,
                Notificacion.resuelta.is_(False),
            )
        )
        ahora = datetime.now(UTC)
        afectados: list[int] = []
        for notificacion in pendientes:
            notificacion.resuelta = True
            notificacion.resuelta_en = ahora
            afectados.append(notificacion.usuario_id)
        if afectados:
            self.db.commit()
            for usuario_id in afectados:
                gestor_notificaciones_tiempo_real.marcar_cambio(usuario_id)
