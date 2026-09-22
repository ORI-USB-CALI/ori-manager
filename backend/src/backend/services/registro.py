from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.security import hash_contrasena
from backend.core.unidades_organizacionales import TipoUnidad
from backend.models.rol import Rol
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.usuario import Usuario
from backend.schemas.auth import RegistroSolicitante

DOMINIOS_INSTITUCIONALES = frozenset({"correo.usbcali.edu.co", "usbcali.edu.co"})


class ErrorRegistro(Exception):
    pass


class CorreoRegistradoError(ErrorRegistro):
    def __init__(self, correo_verificado: bool):
        super().__init__("Ya existe una cuenta con ese correo")
        self.correo_verificado = correo_verificado


class ReferenciaRegistroInvalidaError(ErrorRegistro):
    pass


def clasificar_correo(correo: str) -> TipoUsuario:
    dominio = correo.rsplit("@", 1)[1].lower()
    if dominio in DOMINIOS_INSTITUCIONALES:
        return TipoUsuario.INTERNO
    return TipoUsuario.EXTERNO


class ServicioRegistro:
    def __init__(self, db: Session):
        self.db = db

    def listar_unidades(self) -> list[UnidadOrganizacional]:
        return list(
            self.db.scalars(
                select(UnidadOrganizacional)
                .where(UnidadOrganizacional.activa.is_(True))
                .order_by(UnidadOrganizacional.nombre, UnidadOrganizacional.id)
            )
        )

    def registrar(self, datos: RegistroSolicitante) -> Usuario:
        correo = str(datos.correo).lower()
        existente = self.db.scalar(
            select(Usuario).where(func.lower(Usuario.correo) == correo)
        )
        if existente is not None:
            raise CorreoRegistradoError(existente.correo_verificado_en is not None)

        tipo = clasificar_correo(correo)
        codigo_rol = (
            CodigoRol.SOLICITANTE_INTERNO
            if tipo is TipoUsuario.INTERNO
            else CodigoRol.SOLICITANTE_EXTERNO
        )
        rol = self.db.scalar(
            select(Rol).where(Rol.codigo == codigo_rol.value, Rol.activo.is_(True))
        )
        if rol is None:
            raise ReferenciaRegistroInvalidaError(
                "El rol de solicitante requerido no está disponible"
            )

        unidad = None
        if tipo is TipoUsuario.INTERNO:
            unidad = self._obtener_unidad_activa(datos.unidad_organizacional_id)

        usuario = Usuario(
            correo=correo,
            hash_contrasena=hash_contrasena(datos.contrasena),
            nombre_completo=datos.nombre_completo,
            documento_identidad=(
                datos.documento_identidad if tipo is TipoUsuario.EXTERNO else None
            ),
            cargo=datos.cargo,
            rol_id=rol.id,
            tipo_usuario=tipo.value,
            unidad_organizacional_id=unidad.id if unidad is not None else None,
            entidad_externa=(
                datos.entidad_externa if tipo is TipoUsuario.EXTERNO else None
            ),
            activo=True,
            correo_verificado_en=None,
        )
        try:
            with self.db.begin_nested():
                self.db.add(usuario)
                self.db.flush()
        except IntegrityError as exc:
            existente = self.db.scalar(
                select(Usuario).where(func.lower(Usuario.correo) == correo)
            )
            raise CorreoRegistradoError(
                existente is not None and existente.correo_verificado_en is not None
            ) from exc
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def _obtener_unidad_activa(self, unidad_id: int | None) -> UnidadOrganizacional:
        unidad = self.db.get(UnidadOrganizacional, unidad_id)
        if (
            unidad is None
            or not unidad.activa
            or unidad.tipo not in {tipo.value for tipo in TipoUnidad}
        ):
            raise ReferenciaRegistroInvalidaError(
                "Unidad organizacional inexistente o inactiva"
            )
        return unidad
