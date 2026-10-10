"""Registro y consulta de la evaluación de convenios (HU-32)."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.enums import AccionAuditoria, EstadoConvenio
from backend.models.evaluacion_convenio import EvaluacionConvenio
from backend.models.usuario import Usuario
from backend.schemas.evaluacion import EvaluacionConvenioCrear
from backend.services.convenios import (
    ConvenioDuplicado,
    ConvenioNoEncontrado,
    ErrorConvenio,
)

ENTIDAD_EVALUACION = "evaluacion_convenio"

# Único punto donde vive la regla de elegibilidad. El ciclo de vida de convenios
# todavía no define cuándo se finaliza un convenio ni si la evaluación podrá
# apoyar la decisión de renovación: cuando eso se cierre, ampliar este frozenset
# es el único cambio necesario, y el frontend lo lee del backend.
ESTADOS_EVALUABLES = frozenset({EstadoConvenio.FINALIZADO})


def es_evaluable(convenio: Convenio) -> bool:
    return convenio.estado in ESTADOS_EVALUABLES


class ConvenioNoEvaluable(ErrorConvenio):
    pass


class ServicioEvaluaciones:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _bloquear(self, convenio_id: int) -> Convenio:
        convenio = self.db.scalar(
            select(Convenio)
            .where(Convenio.id == convenio_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        return convenio

    def obtener(self, convenio_id: int) -> EvaluacionConvenio | None:
        # La consulta no debe propagar escrituras pendientes de otros flujos.
        with self.db.no_autoflush:
            return self.db.scalar(
                select(EvaluacionConvenio)
                .options(joinedload(EvaluacionConvenio.evaluado_por))
                .where(EvaluacionConvenio.convenio_id == convenio_id)
            )

    def registrar(
        self, convenio_id: int, datos: EvaluacionConvenioCrear, usuario: Usuario
    ) -> EvaluacionConvenio:
        try:
            convenio = self._bloquear(convenio_id)
            if not es_evaluable(convenio):
                raise ConvenioNoEvaluable(
                    "Solo se puede evaluar un convenio finalizado. "
                    f"Estado actual: {convenio.estado}"
                )
            if self.obtener(convenio.id) is not None:
                raise ConvenioDuplicado(
                    "El convenio ya tiene una evaluación registrada"
                )
            evaluacion = EvaluacionConvenio(
                convenio_id=convenio.id,
                fue_funcional=datos.fue_funcional,
                calificacion=datos.calificacion,
                observaciones=datos.observaciones,
                # Se asigna la relación y no el id: deja el usuario cargado y
                # evita un lazy load al serializar después del commit.
                evaluado_por=usuario,
            )
            self.db.add(evaluacion)
            self.db.flush()
            self.db.add(
                Auditoria(
                    usuario_id=usuario.id,
                    entidad=ENTIDAD_EVALUACION,
                    registro_id=evaluacion.id,
                    accion=AccionAuditoria.INSERT.value,
                )
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConvenioDuplicado(
                "El convenio ya tiene una evaluación registrada"
            ) from exc
        except Exception:
            self.db.rollback()
            raise
        return evaluacion
