from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.enums import CodigoGuia, EstadoGuia
from backend.models.estado_guia_usuario import EstadoGuiaUsuario
from backend.models.usuario import Usuario
from backend.schemas.guia import EstadoGuiaLeer


def _leer(guia: CodigoGuia, registro: EstadoGuiaUsuario | None) -> EstadoGuiaLeer:
    if registro is None:
        return EstadoGuiaLeer(
            guia=guia, estado=EstadoGuia.PENDIENTE, version=None, actualizado_en=None
        )
    return EstadoGuiaLeer(
        guia=guia,
        estado=EstadoGuia(registro.estado),
        version=registro.version,
        actualizado_en=registro.actualizado_en,
    )


class ServicioGuias:
    """HU-38 BE-02. Estado de las guías del usuario autenticado.

    Todas las operaciones reciben el usuario de la sesión: no existe forma de
    consultar ni modificar el estado de otra cuenta (RN-07).
    """

    def __init__(self, db: Session):
        self.db = db

    def _registro(
        self, usuario: Usuario, guia: CodigoGuia, bloquear: bool = False
    ) -> EstadoGuiaUsuario | None:
        consulta = select(EstadoGuiaUsuario).where(
            EstadoGuiaUsuario.usuario_id == usuario.id,
            EstadoGuiaUsuario.guia == guia.value,
        )
        if bloquear:
            consulta = consulta.with_for_update()
        return self.db.scalar(consulta)

    def listar(self, usuario: Usuario) -> list[EstadoGuiaLeer]:
        registros = {
            registro.guia: registro
            for registro in self.db.scalars(
                select(EstadoGuiaUsuario).where(EstadoGuiaUsuario.usuario_id == usuario.id)
            )
        }
        return [_leer(guia, registros.get(guia.value)) for guia in CodigoGuia]

    def obtener(self, usuario: Usuario, guia: CodigoGuia) -> EstadoGuiaLeer:
        return _leer(guia, self._registro(usuario, guia))

    def registrar(
        self, usuario: Usuario, guia: CodigoGuia, estado: EstadoGuia, version: int
    ) -> EstadoGuiaLeer:
        """CA-07 y CA-08. El primer estado final se guarda tal cual; después,
        solo OMITIDO puede pasar a COMPLETADO. Cerrar una reproducción manual
        de una guía completada no la modifica."""
        registro = self._registro(usuario, guia, bloquear=True)
        if registro is None:
            registro = EstadoGuiaUsuario(
                usuario_id=usuario.id, guia=guia.value, estado=estado.value, version=version
            )
            try:
                with self.db.begin_nested():
                    self.db.add(registro)
            except IntegrityError:
                # Otra petición del mismo usuario registró la guía primero: se
                # aplica la transición sobre lo que ya quedó guardado.
                registro = self._registro(usuario, guia, bloquear=True)
                self._aplicar(registro, estado, version)
        else:
            self._aplicar(registro, estado, version)
        self.db.commit()
        self.db.refresh(registro)
        return _leer(guia, registro)

    @staticmethod
    def _aplicar(registro: EstadoGuiaUsuario, estado: EstadoGuia, version: int) -> None:
        if registro.estado == EstadoGuia.OMITIDO and estado == EstadoGuia.COMPLETADO:
            registro.estado = estado.value
            registro.version = version
