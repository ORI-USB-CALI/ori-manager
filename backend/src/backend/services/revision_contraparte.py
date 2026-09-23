from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models.convenio import Convenio
from backend.models.enums import (
    EstadoObservacion,
    EstadoRevisionPendiente,
    OrigenObservacion,
    ResultadoRevisionPendiente,
)
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_pendiente import RevisionPendiente
from backend.models.usuario import Usuario

CODIGO_REVISION_AVAL_JURIDICO = "REVISION_AVAL_JURIDICO"
CODIGO_REVISION_CONTRAPARTE = "REVISION_CONTRAPARTE"
CODIGO_REVISION_FINAL = "REVISION_FINAL"

# Etapas desde las que se puede registrar un envío a contraparte: el primer
# envío ocurre estando en REVISION_AVAL_JURIDICO (aval jurídico aprobado,
# HU-13 aún no define un estado explícito para esto) y los reenvíos ocurren
# estando ya en REVISION_CONTRAPARTE (ciclo de revisión en curso).
_ETAPAS_VALIDAS_PARA_ENVIO = {CODIGO_REVISION_AVAL_JURIDICO, CODIGO_REVISION_CONTRAPARTE}


class ErrorRevisionContraparte(Exception):
    pass


class ConvenioNoEncontrado(ErrorRevisionContraparte):
    pass


class RevisionJuridicaNoAprobada(ErrorRevisionContraparte):
    pass


class UsuarioNoAutorizado(ErrorRevisionContraparte):
    pass


class RevisionPendienteNoEncontrada(ErrorRevisionContraparte):
    pass


class ObservacionesRequeridas(ErrorRevisionContraparte):
    pass


class ServicioRevisionContraparte:
    def __init__(self, db: Session):
        self.db = db

    def _obtener_convenio(self, convenio_id: int) -> Convenio:
        convenio = self.db.get(Convenio, convenio_id)
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        return convenio

    def _etapa_por_codigo(self, codigo: str) -> Etapa:
        etapa = self.db.scalar(select(Etapa).where(Etapa.codigo == codigo))
        if etapa is None:
            raise ErrorRevisionContraparte(f"La etapa '{codigo}' no está configurada")
        return etapa

    def _siguiente_numero_ciclo(self, convenio_id: int) -> int:
        total = self.db.scalar(
            select(func.count()).select_from(HistorialEtapa).where(HistorialEtapa.convenio_id == convenio_id)
        )
        return (total or 0) + 1

    def _registrar_transicion(
        self, convenio: Convenio, etapa_destino: Etapa, usuario: Usuario
    ) -> HistorialEtapa:
        historial = HistorialEtapa(
            convenio_id=convenio.id,
            etapa_origen_id=convenio.etapa_actual_id,
            etapa_destino_id=etapa_destino.id,
            usuario_id=usuario.id,
            numero_ciclo=self._siguiente_numero_ciclo(convenio.id),
        )
        convenio.etapa_actual_id = etapa_destino.id
        self.db.add(historial)
        self.db.commit()
        self.db.refresh(historial)
        return historial

    def registrar_envio(self, convenio_id: int, usuario: Usuario) -> HistorialEtapa:
        convenio = self._obtener_convenio(convenio_id)
        etapa_actual = convenio.etapa_actual_id and self.db.get(Etapa, convenio.etapa_actual_id)
        if etapa_actual is None or etapa_actual.codigo not in _ETAPAS_VALIDAS_PARA_ENVIO:
            raise RevisionJuridicaNoAprobada(
                "El convenio debe tener aprobada la revisión jurídica antes de enviarse a la contraparte"
            )
        etapa_destino = self._etapa_por_codigo(CODIGO_REVISION_CONTRAPARTE)
        historial = self._registrar_transicion(convenio, etapa_destino, usuario)
        revision = RevisionPendiente(
            convenio_id=convenio.id,
            historial_etapa_id=historial.id,
            responsable_id=convenio.solicitud.solicitante_id,
            estado=EstadoRevisionPendiente.PENDIENTE.value,
        )
        self.db.add(revision)
        self.db.commit()
        return historial

    def _verificar_solicitante(self, convenio: Convenio, usuario: Usuario) -> None:
        if convenio.solicitud.solicitante_id != usuario.id:
            raise UsuarioNoAutorizado(
                "Solo el Solicitante asociado a este convenio puede revisar esta versión"
            )

    def _revision_pendiente_actual(self, convenio_id: int, usuario: Usuario) -> RevisionPendiente:
        revision = self.db.scalar(
            select(RevisionPendiente)
            .where(
                RevisionPendiente.convenio_id == convenio_id,
                RevisionPendiente.responsable_id == usuario.id,
                RevisionPendiente.estado == EstadoRevisionPendiente.PENDIENTE.value,
            )
            .order_by(RevisionPendiente.id.desc())
        )
        if revision is None:
            raise RevisionPendienteNoEncontrada(
                "No existe una revisión pendiente para este convenio y usuario"
            )
        return revision

    def aprobar(self, convenio_id: int, usuario: Usuario) -> RevisionPendiente:
        convenio = self._obtener_convenio(convenio_id)
        self._verificar_solicitante(convenio, usuario)
        revision = self._revision_pendiente_actual(convenio_id, usuario)

        etapa_destino = self._etapa_por_codigo(CODIGO_REVISION_FINAL)
        self._registrar_transicion(convenio, etapa_destino, usuario)

        revision.estado = EstadoRevisionPendiente.RESUELTA.value
        revision.resultado = ResultadoRevisionPendiente.APROBADA.value
        revision.resuelta_en = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(revision)
        return revision

    def devolver_con_observaciones(
        self, convenio_id: int, observaciones: list[str], usuario: Usuario
    ) -> RevisionPendiente:
        convenio = self._obtener_convenio(convenio_id)
        self._verificar_solicitante(convenio, usuario)
        revision = self._revision_pendiente_actual(convenio_id, usuario)

        textos = [texto.strip() for texto in observaciones if texto and texto.strip()]
        if not textos:
            raise ObservacionesRequeridas(
                "Debe registrar al menos una observación para devolver el convenio"
            )

        for texto in textos:
            self.db.add(
                ObservacionRevision(
                    convenio_id=convenio.id,
                    historial_etapa_id=revision.historial_etapa_id,
                    origen=OrigenObservacion.CONTRAPARTE.value,
                    registrada_por_id=usuario.id,
                    descripcion=texto,
                    estado=EstadoObservacion.PENDIENTE.value,
                )
            )

        revision.estado = EstadoRevisionPendiente.RESUELTA.value
        revision.resultado = ResultadoRevisionPendiente.DEVUELTA.value
        revision.resuelta_en = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(revision)
        return revision
