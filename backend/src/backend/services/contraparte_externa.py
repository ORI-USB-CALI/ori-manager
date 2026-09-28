import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from html import escape

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.models.convenio import Convenio
from backend.models.enums import (
    EstadoObservacionRevision,
    EstadoRevisionConvenio,
    OrigenObservacionRevision,
    ResultadoRevisionConvenio,
    TipoRevisionConvenio,
)
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.invitacion_revision_contraparte import (
    InvitacionRevisionContraparte,
)
from backend.models.observacion_revision import ObservacionRevision
from backend.models.respuesta_revision_contraparte import (
    RespuestaRevisionContraparte,
)
from backend.models.revision_convenio import RevisionConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.correo import EnviadorCorreo, MensajeCorreo
from backend.services.firma_png import (
    MAX_FIRMA_PNG_BYTES,
    FirmaPngInvalida,
    decodificar_firma_png,
)

__all__ = ["MAX_FIRMA_PNG_BYTES", "ServicioContraparteExterna"]

VIGENCIA_INVITACION_CONTRAPARTE = timedelta(hours=1)
CODIGO_ETAPA_REVISION_CONTRAPARTE = "REVISION_CONTRAPARTE"
CODIGO_ETAPA_REVISION_FINAL = "REVISION_FINAL"
CODIGO_ETAPA_ELABORACION = "ELABORACION"


class EnlaceContraparteError(Exception):
    def __init__(self, codigo: str = "ENLACE_INVALIDO") -> None:
        self.codigo = codigo
        super().__init__(codigo)


class DecisionContraparteInvalida(Exception):
    pass


@dataclass(frozen=True)
class ContextoAccesoContraparte:
    convenio: Convenio
    revision: RevisionConvenio
    invitacion: InvitacionRevisionContraparte
    version: VersionConvenio


def hash_token_contraparte(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def crear_invitacion_contraparte(
    db: Session,
    revision: RevisionConvenio,
    correo_destino: str,
    correo_cc: str | None,
    generada_por_id: int,
) -> tuple[InvitacionRevisionContraparte, str]:
    token_plano = secrets.token_urlsafe(48)
    ahora = datetime.now(UTC)
    invitacion = InvitacionRevisionContraparte(
        revision_convenio=revision,
        token_hash=hash_token_contraparte(token_plano),
        correo_destino=correo_destino,
        correo_cc=correo_cc,
        generada_por_id=generada_por_id,
        expira_en=ahora + VIGENCIA_INVITACION_CONTRAPARTE,
    )
    db.add(invitacion)
    return invitacion, token_plano


def enviar_invitacion_contraparte(
    db: Session,
    enviador: EnviadorCorreo,
    frontend_url: str,
    invitacion: InvitacionRevisionContraparte,
    token_plano: str,
    convenio: Convenio,
) -> None:
    enlace = f"{frontend_url.rstrip('/')}/revision-contraparte#token={token_plano}"
    identificador = convenio.codigo or f"#{convenio.id}"
    enviador.enviar(
        MensajeCorreo(
            destinatario=invitacion.correo_destino,
            cc=(invitacion.correo_cc,) if invitacion.correo_cc else (),
            asunto=(
                "Revisión de contraparte - elaboración de convenio "
                f"{identificador}"
            ),
            texto=(
                "La ORI de la Universidad de San Buenaventura Cali solicita revisar la "
                f"elaboración de convenio {identificador}. "
                f"Acceda mediante este enlace: {enlace}\n"
                "El enlace vence en 1 hora."
            ),
            html=(
                "<h1>Revisión de elaboración de convenio</h1>"
                "<p>La ORI solicita revisar la elaboración de convenio "
                f"{escape(identificador)}.</p>"
                f'<p><a href="{escape(enlace)}">'
                "Revisar elaboración de convenio</a></p>"
                "<p>El enlace vence en 1 hora.</p>"
            ),
        )
    )
    invitacion.enviado_en = datetime.now(UTC)
    db.commit()


class ServicioContraparteExterna:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _contexto(
        self, token: str, *, bloquear: bool
    ) -> ContextoAccesoContraparte:
        token_hash = hash_token_contraparte(token)
        referencia = self.db.execute(
            select(
                InvitacionRevisionContraparte.id,
                InvitacionRevisionContraparte.revision_convenio_id,
            ).where(
                InvitacionRevisionContraparte.token_hash == token_hash
            )
        ).one_or_none()
        if referencia is None:
            raise EnlaceContraparteError()
        invitacion_id, revision_id = referencia
        convenio_id = self.db.scalar(
            select(RevisionConvenio.convenio_id).where(
                RevisionConvenio.id == revision_id
            )
        )
        if convenio_id is None:
            raise EnlaceContraparteError()

        consulta_convenio = select(Convenio).where(Convenio.id == convenio_id)
        consulta_revision = select(RevisionConvenio).where(
            RevisionConvenio.id == revision_id,
            RevisionConvenio.convenio_id == convenio_id,
        )
        consulta_invitacion = select(InvitacionRevisionContraparte).where(
            InvitacionRevisionContraparte.id == invitacion_id,
            InvitacionRevisionContraparte.revision_convenio_id == revision_id,
            InvitacionRevisionContraparte.token_hash == token_hash,
        )
        if bloquear:
            consulta_convenio = consulta_convenio.execution_options(
                populate_existing=True
            ).with_for_update()
            consulta_revision = consulta_revision.execution_options(
                populate_existing=True
            ).with_for_update()
            consulta_invitacion = consulta_invitacion.execution_options(
                populate_existing=True
            ).with_for_update()
        convenio = self.db.scalar(consulta_convenio)
        revision = self.db.scalar(consulta_revision)
        invitacion = self.db.scalar(consulta_invitacion)
        if convenio is None or revision is None or invitacion is None:
            raise EnlaceContraparteError()

        ahora = datetime.now(UTC)
        if invitacion.expira_en <= ahora:
            raise EnlaceContraparteError("ENLACE_EXPIRADO")
        if (
            invitacion.revocado_en is not None
            or invitacion.utilizado_en is not None
            or revision.tipo != TipoRevisionConvenio.CONTRAPARTE.value
            or revision.estado != EstadoRevisionConvenio.PENDIENTE.value
            or revision.resultado is not None
            or convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_REVISION_CONTRAPARTE
        ):
            raise EnlaceContraparteError("ENLACE_NO_DISPONIBLE")
        version = self.db.get(VersionConvenio, revision.version_convenio_id)
        if version is None or version.convenio_id != convenio.id:
            raise EnlaceContraparteError("ENLACE_NO_DISPONIBLE")
        return ContextoAccesoContraparte(
            convenio=convenio,
            revision=revision,
            invitacion=invitacion,
            version=version,
        )

    def acceder(self, token: str) -> ContextoAccesoContraparte:
        return self._contexto(token, bloquear=False)

    @staticmethod
    def decodificar_firma(firma: str) -> tuple[bytes, str]:
        try:
            return decodificar_firma_png(firma)
        except FirmaPngInvalida as exc:
            raise DecisionContraparteInvalida(str(exc)) from exc

    def _revocar_otras(
        self, revision_id: int, invitacion_id: int, ahora: datetime
    ) -> None:
        self.db.execute(
            update(InvitacionRevisionContraparte)
            .where(
                InvitacionRevisionContraparte.revision_convenio_id == revision_id,
                InvitacionRevisionContraparte.id != invitacion_id,
                InvitacionRevisionContraparte.utilizado_en.is_(None),
                InvitacionRevisionContraparte.revocado_en.is_(None),
            )
            .values(revocado_en=ahora)
        )

    def aprobar(
        self,
        token: str,
        nombre_firmante: str,
        cargo_firmante: str,
        firma: str,
    ) -> RevisionConvenio:
        firma_png, firma_hash = self.decodificar_firma(firma)
        contexto = self._contexto(token, bloquear=True)
        etapa_final = self.db.scalar(
            select(Etapa).where(Etapa.codigo == CODIGO_ETAPA_REVISION_FINAL)
        )
        if etapa_final is None:
            raise RuntimeError("No existe la etapa obligatoria REVISION_FINAL")
        ahora = datetime.now(UTC)
        revision = contexto.revision
        revision.estado = EstadoRevisionConvenio.RESUELTA.value
        revision.resultado = ResultadoRevisionConvenio.APROBADA.value
        revision.resuelta_por_id = None
        revision.resuelta_en = ahora
        revision.version_resultado_id = contexto.version.id
        contexto.invitacion.utilizado_en = ahora
        self._revocar_otras(revision.id, contexto.invitacion.id, ahora)
        self.db.add(
            RespuestaRevisionContraparte(
                revision_convenio_id=revision.id,
                nombre_firmante=nombre_firmante,
                cargo_firmante=cargo_firmante,
                correo_actor=contexto.invitacion.correo_destino,
                firma_png=firma_png,
                firma_sha256=firma_hash,
            )
        )
        usuario_interno_id = revision.creada_por_id or contexto.convenio.creado_por_id
        historial = HistorialEtapa(
            convenio_id=contexto.convenio.id,
            etapa_origen_id=contexto.convenio.etapa_actual_id,
            etapa_destino_id=etapa_final.id,
            usuario_id=usuario_interno_id,
            responsable_id=usuario_interno_id,
            observacion="Aprobación externa de la contraparte",
        )
        self.db.add(historial)
        contexto.convenio.etapa_actual = etapa_final
        try:
            self.db.flush()
            self.db.add(
                RevisionConvenio(
                    convenio_id=contexto.convenio.id,
                    tipo=TipoRevisionConvenio.FINAL.value,
                    historial_etapa_id=historial.id,
                    version_convenio_id=contexto.version.id,
                    version_resultado_id=None,
                    responsable_id=usuario_interno_id,
                    creada_por_id=usuario_interno_id,
                    estado=EstadoRevisionConvenio.PENDIENTE.value,
                    resultado=None,
                )
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise EnlaceContraparteError("ENLACE_NO_DISPONIBLE") from exc
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return revision

    def devolver(
        self,
        token: str,
        nombre_firmante: str,
        cargo_firmante: str,
        observaciones: list[str],
    ) -> RevisionConvenio:
        if not observaciones or any(not texto.strip() for texto in observaciones):
            raise DecisionContraparteInvalida(
                "Debe incluir al menos una observación con contenido"
            )
        contexto = self._contexto(token, bloquear=True)
        elaboracion = self.db.scalar(
            select(Etapa).where(Etapa.codigo == CODIGO_ETAPA_ELABORACION)
        )
        if elaboracion is None:
            raise RuntimeError("No existe la etapa ELABORACION")
        ahora = datetime.now(UTC)
        revision = contexto.revision
        responsable_ori_id = revision.creada_por_id or contexto.convenio.creado_por_id
        historial = HistorialEtapa(
            convenio_id=contexto.convenio.id,
            etapa_origen_id=contexto.convenio.etapa_actual_id,
            etapa_destino_id=elaboracion.id,
            usuario_id=responsable_ori_id,
            responsable_id=responsable_ori_id,
            observacion="Devolución externa de revisión de contraparte",
        )
        self.db.add(historial)
        try:
            self.db.flush()
            for texto in observaciones:
                self.db.add(
                    ObservacionRevision(
                        convenio_id=contexto.convenio.id,
                        historial_etapa_id=historial.id,
                        revision_convenio_id=revision.id,
                        origen=OrigenObservacionRevision.CONTRAPARTE.value,
                        registrada_por_id=None,
                        responsable_id=responsable_ori_id,
                        descripcion=texto.strip(),
                        estado=EstadoObservacionRevision.PENDIENTE.value,
                    )
                )
            self.db.add(
                RespuestaRevisionContraparte(
                    revision_convenio_id=revision.id,
                    nombre_firmante=nombre_firmante,
                    cargo_firmante=cargo_firmante,
                    correo_actor=contexto.invitacion.correo_destino,
                )
            )
            revision.estado = EstadoRevisionConvenio.RESUELTA.value
            revision.resultado = ResultadoRevisionConvenio.DEVUELTA.value
            revision.resuelta_por_id = None
            revision.resuelta_en = ahora
            revision.version_resultado_id = contexto.version.id
            contexto.invitacion.utilizado_en = ahora
            self._revocar_otras(revision.id, contexto.invitacion.id, ahora)
            contexto.convenio.etapa_actual = elaboracion
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise EnlaceContraparteError("ENLACE_NO_DISPONIBLE") from exc
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return revision
