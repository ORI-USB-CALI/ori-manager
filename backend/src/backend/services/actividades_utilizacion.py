"""Registro y consulta de actividades de utilización de convenios (HU-35).

Las actividades se guardan en la entidad canónica `actividad_convenio`,
compartida con HU-34, siempre con estado REALIZADA.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.actividad_convenio import ActividadConvenio
from backend.models.convenio import Convenio
from backend.models.enums import EstadoActividadConvenio, EstadoConvenio
from backend.models.usuario import Usuario
from backend.schemas.actividad_utilizacion import ActividadUtilizacionCrear
from backend.services.convenios import (
    ConvenioNoEditable,
    ConvenioNoEncontrado,
    ReferenciaConvenioInvalida,
    ServicioConvenios,
)
from backend.services.renovaciones import fecha_actual_dominio

ESTADOS_REGISTRO_UTILIZACION = frozenset(
    (EstadoConvenio.VIGENTE.value, EstadoConvenio.POR_VENCER.value)
)


class FechaActividadInvalida(ReferenciaConvenioInvalida):
    pass


class ServicioActividadesUtilizacion:
    def __init__(self, db: Session):
        self.db = db

    def registrar(
        self,
        convenio_id: int,
        datos: ActividadUtilizacionCrear,
        usuario: Usuario,
    ) -> ActividadConvenio:
        ServicioConvenios(self.db).verificar_alcance_operativo(convenio_id, usuario)
        convenio = self.db.scalar(
            select(Convenio).where(Convenio.id == convenio_id).with_for_update()
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        if convenio.estado not in ESTADOS_REGISTRO_UTILIZACION:
            raise ConvenioNoEditable(
                "Solo se pueden registrar actividades de utilización en "
                "convenios vigentes o por vencer"
            )
        if convenio.fecha_inicio is None or convenio.fecha_vencimiento is None:
            raise ConvenioNoEditable(
                "El convenio no tiene un período de vigencia registrado"
            )
        _validar_fecha_ejecucion(convenio, datos)

        actividad = ActividadConvenio(
            convenio_id=convenio.id,
            estado=EstadoActividadConvenio.REALIZADA.value,
            registrado_por_id=usuario.id,
            **datos.model_dump(),
        )
        self.db.add(actividad)
        self.db.commit()
        self.db.refresh(actividad)
        return actividad

    def listar(self, convenio_id: int, usuario: Usuario) -> list[ActividadConvenio]:
        """Actividades realizadas del convenio en cualquier estado del
        convenio; lista vacía si no hay."""
        ServicioConvenios(self.db).verificar_alcance_operativo(convenio_id, usuario)
        return list(
            self.db.scalars(
                select(ActividadConvenio)
                .where(
                    ActividadConvenio.convenio_id == convenio_id,
                    ActividadConvenio.estado
                    == EstadoActividadConvenio.REALIZADA.value,
                )
                .order_by(
                    ActividadConvenio.fecha_ejecucion.desc(),
                    ActividadConvenio.id.desc(),
                )
            )
        )


def _validar_fecha_ejecucion(
    convenio: Convenio, datos: ActividadUtilizacionCrear
) -> None:
    fecha = datos.fecha_ejecucion
    if fecha > fecha_actual_dominio():
        raise FechaActividadInvalida(
            "La fecha de la actividad no puede ser futura"
        )
    if not convenio.fecha_inicio <= fecha <= convenio.fecha_vencimiento:
        raise FechaActividadInvalida(
            "La fecha de la actividad debe estar dentro del período de "
            "vigencia del convenio"
        )
