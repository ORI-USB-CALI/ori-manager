from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models.convenio import Convenio
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
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


class ConvenioNoEnRevisionContraparte(ErrorRevisionContraparte):
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
        return self._registrar_transicion(convenio, etapa_destino, usuario)

    def registrar_aprobacion(self, convenio_id: int, usuario: Usuario) -> HistorialEtapa:
        convenio = self._obtener_convenio(convenio_id)
        etapa_actual = convenio.etapa_actual_id and self.db.get(Etapa, convenio.etapa_actual_id)
        if etapa_actual is None or etapa_actual.codigo != CODIGO_REVISION_CONTRAPARTE:
            raise ConvenioNoEnRevisionContraparte(
                "El convenio debe estar en revisión de contraparte para registrar su aprobación"
            )
        etapa_destino = self._etapa_por_codigo(CODIGO_REVISION_FINAL)
        return self._registrar_transicion(convenio, etapa_destino, usuario)
