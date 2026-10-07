from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.core.security import generar_token_sesion, verificar_contrasena
from backend.models.usuario import Usuario
from backend.services.sesiones import RepositorioSesiones

DURACION_SESION = timedelta(hours=6)


class ErrorAutenticacion(Exception):
    pass


class CredencialesInvalidasError(ErrorAutenticacion):
    pass


class UsuarioInactivoError(ErrorAutenticacion):
    pass


class CorreoNoVerificadoError(ErrorAutenticacion):
    pass


class ServicioAutenticacion:
    def __init__(self, db: Session, sesiones: RepositorioSesiones) -> None:
        self.db = db
        self.sesiones = sesiones

    def iniciar_sesion(self, correo: str, contrasena: str) -> tuple[Usuario, str]:
        usuario = self.db.scalar(
            select(Usuario)
            .options(joinedload(Usuario.rol))
            .where(func.lower(Usuario.correo) == correo.lower())
        )
        if usuario is None or not verificar_contrasena(
            contrasena, usuario.hash_contrasena
        ):
            raise CredencialesInvalidasError
        if not usuario.activo:
            raise UsuarioInactivoError
        if usuario.correo_verificado_en is None:
            raise CorreoNoVerificadoError

        token = generar_token_sesion()
        ahora = datetime.now(UTC)
        self.sesiones.crear(usuario.id, token, ahora + DURACION_SESION)
        usuario.ultimo_acceso = ahora
        try:
            self.db.commit()
            self.db.refresh(usuario)
        except Exception:
            self.sesiones.invalidar(token)
            raise
        return usuario, token

    def cerrar_sesion(self, token: str) -> bool:
        return self.sesiones.invalidar(token)
