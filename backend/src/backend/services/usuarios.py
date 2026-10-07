from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.security import hash_contrasena, verificar_contrasena
from backend.models.rol import Rol
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.usuario import Usuario
from backend.schemas.usuario import UsuarioActualizar, UsuarioCrear
from backend.services.sesiones import RepositorioSesiones


class ErrorGestionUsuarios(Exception):
    pass


class UsuarioNoEncontradoError(ErrorGestionUsuarios):
    pass


class CorreoDuplicadoError(ErrorGestionUsuarios):
    pass


class ReferenciaUsuarioInvalidaError(ErrorGestionUsuarios):
    pass


class ConflictoUsuarioError(ErrorGestionUsuarios):
    pass


ROLES_VISIBLES_ADMIN = frozenset(
    {
        CodigoRol.ADMINISTRADOR_ORI,
        CodigoRol.GESTOR_ORI,
        CodigoRol.REVISOR_ORI,
        CodigoRol.SOLICITANTE_INTERNO,
        CodigoRol.SOLICITANTE_EXTERNO,
    }
)
ROLES_ASIGNABLES_ADMIN = frozenset(
    {
        CodigoRol.ADMINISTRADOR_ORI,
        CodigoRol.GESTOR_ORI,
        CodigoRol.REVISOR_ORI,
    }
)
ROLES_SOLICITANTES = frozenset(
    {
        CodigoRol.SOLICITANTE_INTERNO,
        CodigoRol.SOLICITANTE_EXTERNO,
    }
)
CODIGOS_ROLES_VISIBLES_ADMIN = tuple(rol.value for rol in ROLES_VISIBLES_ADMIN)


class ServicioUsuarios:
    def __init__(self, db: Session, sesiones: RepositorioSesiones) -> None:
        self.db = db
        self.sesiones = sesiones

    def listar(self) -> list[Usuario]:
        return list(
            self.db.scalars(
                select(Usuario)
                .options(joinedload(Usuario.rol))
                .where(Usuario.rol.has(Rol.codigo.in_(CODIGOS_ROLES_VISIBLES_ADMIN)))
                .order_by(Usuario.correo)
            )
        )

    def obtener(self, usuario_id: int) -> Usuario:
        usuario = self.db.scalar(
            select(Usuario)
            .options(joinedload(Usuario.rol))
            .where(
                Usuario.id == usuario_id,
                Usuario.rol.has(Rol.codigo.in_(CODIGOS_ROLES_VISIBLES_ADMIN)),
            )
        )
        if usuario is None:
            raise UsuarioNoEncontradoError
        return usuario

    def crear(self, datos: UsuarioCrear) -> Usuario:
        if datos.tipo_usuario is not TipoUsuario.INTERNO:
            raise ReferenciaUsuarioInvalidaError(
                "El módulo administrativo solo permite crear usuarios internos"
            )
        self._validar_correo_disponible(str(datos.correo))
        rol = self._obtener_rol(datos.rol)
        self._validar_rol_asignable(datos.rol)
        self._validar_compatibilidad(rol, datos.tipo_usuario)
        unidad = self._obtener_unidad(datos.unidad_organizacional_id)
        usuario = Usuario(
            correo=str(datos.correo).lower(),
            hash_contrasena=hash_contrasena(datos.contrasena),
            nombre_completo=datos.nombre_completo,
            documento_identidad=datos.documento_identidad,
            telefono=datos.telefono,
            cargo=datos.cargo,
            rol_id=rol.id,
            tipo_usuario=datos.tipo_usuario.value,
            unidad_organizacional_id=unidad.id if unidad is not None else None,
            entidad_externa=datos.entidad_externa,
            activo=True,
            correo_verificado_en=datetime.now(UTC),
        )
        return self._guardar(usuario)

    def actualizar(self, usuario_id: int, datos: UsuarioActualizar) -> Usuario:
        usuario = self.obtener(usuario_id)
        cambios = datos.model_dump(exclude_unset=True)
        if self._es_solicitante(usuario):
            if "correo" in cambios:
                raise ReferenciaUsuarioInvalidaError(
                    "El correo de los solicitantes no se administra desde este módulo"
                )
            if "contrasena" in cambios:
                raise ReferenciaUsuarioInvalidaError(
                    "La contraseña de los solicitantes se gestiona mediante recuperación de acceso"
                )
            tipo_usuario = TipoUsuario(usuario.tipo_usuario)
            if tipo_usuario is TipoUsuario.INTERNO:
                campos_incompatibles = {
                    "documento_identidad",
                    "entidad_externa",
                }.intersection(cambios)
            else:
                campos_incompatibles = {"unidad_organizacional_id"}.intersection(
                    cambios
                )
            if campos_incompatibles:
                campos = ", ".join(sorted(campos_incompatibles))
                raise ReferenciaUsuarioInvalidaError(
                    f"Campos incompatibles con el tipo de solicitante: {campos}"
                )
        contrasena = cambios.pop("contrasena", None)
        if contrasena is not None and verificar_contrasena(
            contrasena, usuario.hash_contrasena
        ):
            raise ConflictoUsuarioError(
                "La nueva contraseña debe ser diferente a la actual"
            )

        correo = cambios.pop("correo", None)
        if correo is not None:
            self._validar_correo_disponible(str(correo), usuario.id)
            usuario.correo = str(correo).lower()

        if contrasena is not None:
            usuario.hash_contrasena = hash_contrasena(contrasena)

        if "unidad_organizacional_id" in cambios:
            unidad_id = cambios.pop("unidad_organizacional_id")
            usuario.unidad_organizacional = self._obtener_unidad(unidad_id)

        for campo, valor in cambios.items():
            setattr(usuario, campo, valor)
        usuario = self._guardar(usuario)
        if contrasena is not None:
            self.sesiones.invalidar_usuario(usuario.id)
        return usuario

    def cambiar_rol(
        self,
        usuario_id: int,
        codigo_rol: CodigoRol,
        actor: Usuario,
    ) -> Usuario:
        usuario = self.obtener(usuario_id)
        if usuario.id == actor.id:
            raise ConflictoUsuarioError("No puede cambiar su propio rol")
        if self._es_solicitante(usuario):
            raise ReferenciaUsuarioInvalidaError(
                "El rol de los solicitantes no se administra desde este módulo"
            )
        self._validar_rol_asignable(codigo_rol)
        rol = self._obtener_rol(codigo_rol)
        self._validar_compatibilidad(rol, TipoUsuario(usuario.tipo_usuario))
        usuario.rol = rol
        return self._guardar(usuario)

    def cambiar_estado(
        self,
        usuario_id: int,
        activo: bool,
        actor: Usuario,
    ) -> Usuario:
        usuario = self.obtener(usuario_id)
        if usuario.id == actor.id and not activo:
            raise ConflictoUsuarioError("No puede desactivar su propio usuario")
        if not usuario.activo and not activo:
            raise ConflictoUsuarioError("El usuario ya se encuentra inactivo")
        usuario.activo = activo
        usuario = self._guardar(usuario)
        if not activo:
            self.sesiones.invalidar_usuario(usuario.id)
        return usuario

    def _obtener_rol(self, codigo: CodigoRol) -> Rol:
        rol = self.db.scalar(select(Rol).where(Rol.codigo == codigo.value))
        if rol is None or not rol.activo:
            raise ReferenciaUsuarioInvalidaError("Rol inexistente o inactivo")
        return rol

    @staticmethod
    def _validar_rol_asignable(codigo: CodigoRol) -> None:
        if codigo not in ROLES_ASIGNABLES_ADMIN:
            raise ReferenciaUsuarioInvalidaError(
                "El módulo administrativo solo permite roles operativos ORI"
            )

    @staticmethod
    def _es_solicitante(usuario: Usuario) -> bool:
        return CodigoRol(usuario.rol.codigo) in ROLES_SOLICITANTES

    def _obtener_unidad(self, unidad_id: int | None) -> UnidadOrganizacional | None:
        if unidad_id is None:
            return None
        unidad = self.db.get(UnidadOrganizacional, unidad_id)
        if unidad is None:
            raise ReferenciaUsuarioInvalidaError("Unidad organizacional inexistente")
        return unidad

    def _validar_compatibilidad(self, rol: Rol, tipo: TipoUsuario) -> None:
        compatible = (tipo is TipoUsuario.INTERNO and rol.es_interno) or (
            tipo is TipoUsuario.EXTERNO and not rol.es_interno
        )
        if not compatible:
            raise ReferenciaUsuarioInvalidaError(
                "El rol no es compatible con el tipo de usuario"
            )

    def _validar_correo_disponible(
        self,
        correo: str,
        usuario_id: int | None = None,
    ) -> None:
        consulta = select(Usuario.id).where(
            func.lower(Usuario.correo) == correo.lower()
        )
        if usuario_id is not None:
            consulta = consulta.where(Usuario.id != usuario_id)
        if self.db.scalar(consulta) is not None:
            raise CorreoDuplicadoError

    def _guardar(self, usuario: Usuario) -> Usuario:
        try:
            with self.db.begin_nested():
                self.db.add(usuario)
                self.db.flush()
        except IntegrityError as exc:
            raise CorreoDuplicadoError from exc
        self.db.commit()
        self.db.refresh(usuario)
        return usuario
