"""Registro y consulta de actividades de utilización de convenios (HU-35)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.actividad_utilizacion import ActividadUtilizacion
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.models.usuario import Usuario
from backend.schemas.actividad_utilizacion import ActividadUtilizacionCrear
from backend.services.convenios import (
    ConvenioNoEditable,
    ConvenioNoEncontrado,
    ServicioConvenios,
)

ESTADOS_REGISTRO_UTILIZACION = frozenset(
    (EstadoConvenio.VIGENTE.value, EstadoConvenio.POR_VENCER.value)
)


class ServicioActividadesUtilizacion:
    def __init__(self, db: Session):
        self.db = db

    def registrar(
        self,
        convenio_id: int,
        datos: ActividadUtilizacionCrear,
        usuario: Usuario,
    ) -> ActividadUtilizacion:
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
        actividad = ActividadUtilizacion(
            convenio_id=convenio.id,
            registrado_por_id=usuario.id,
            **datos.model_dump(),
        )
        self.db.add(actividad)
        self.db.commit()
        self.db.refresh(actividad)
        return actividad

    def listar(
        self, convenio_id: int, usuario: Usuario
    ) -> list[ActividadUtilizacion]:
        """Actividades del convenio en cualquier estado; lista vacía si no hay."""
        ServicioConvenios(self.db).verificar_alcance_operativo(convenio_id, usuario)
        return list(
            self.db.scalars(
                select(ActividadUtilizacion)
                .where(ActividadUtilizacion.convenio_id == convenio_id)
                .order_by(
                    ActividadUtilizacion.fecha.desc(),
                    ActividadUtilizacion.id.desc(),
                )
            )
        )
