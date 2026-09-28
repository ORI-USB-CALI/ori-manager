import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from html import escape

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from backend.models.convenio import Convenio
from backend.models.enums import (
    EstadoFirmaConvenio,
    EstadoProcesoFirmasConvenio,
    ModalidadFirma,
)
from backend.models.firma_convenio import FirmaConvenio
from backend.models.invitacion_firma_convenio import InvitacionFirmaConvenio
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.usuario import Usuario
from backend.models.version_convenio import VersionConvenio
from backend.services.convenios import (
    ConvenioNoEncontrado,
    ReferenciaConvenioInvalida,
    RevisionNoDisponible,
)
from backend.services.correo import EnviadorCorreo, ErrorEnvioCorreo, MensajeCorreo
from backend.services.firma_png import FirmaPngInvalida, decodificar_firma_png
from backend.services.firmas import CODIGO_ETAPA_APROBACION_FIRMAS, ROLES_FIRMANTES

VIGENCIA_INVITACION_FIRMA = timedelta(hours=1)


class EnlaceFirmaConvenioError(Exception):
    def __init__(self, codigo: str = "ENLACE_INVALIDO") -> None:
        self.codigo = codigo
        super().__init__(codigo)


class FirmaElectronicaInvalida(Exception):
    pass


class EntregaInvitacionesFirmaError(ErrorEnvioCorreo):
    def __init__(self, firmas_fallidas: list[int]) -> None:
        self.firmas_fallidas = firmas_fallidas
        super().__init__("No fue posible entregar una o más invitaciones")


@dataclass(frozen=True)
class ContextoFirmaPublica:
    convenio: Convenio
    proceso: ProcesoFirmasConvenio
    firma: FirmaConvenio
    invitacion: InvitacionFirmaConvenio
    version: VersionConvenio


def hash_token_firma(token: str) -> str:
    return sha256(token.encode()).hexdigest()


class ServicioFirmaElectronica:
    def __init__(
        self,
        db: Session,
        enviador: EnviadorCorreo | None = None,
        frontend_url: str | None = None,
    ) -> None:
        self.db = db
        self.enviador = enviador
        self.frontend_url = frontend_url

    @staticmethod
    def _firma_configurada(firma: FirmaConvenio) -> bool:
        if not firma.nombre_firmante or not firma.cargo_firmante:
            return False
        if firma.modalidad == ModalidadFirma.FISICA.value:
            return True
        return (
            firma.modalidad == ModalidadFirma.ELECTRONICA.value
            and bool(firma.correo_firmante)
        )

    def _convenio(self, convenio_id: int, *, bloquear: bool) -> Convenio:
        consulta = select(Convenio).where(Convenio.id == convenio_id)
        if bloquear:
            consulta = consulta.execution_options(
                populate_existing=True
            ).with_for_update()
        convenio = self.db.scalar(consulta)
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        if (
            convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_APROBACION_FIRMAS
        ):
            raise RevisionNoDisponible(
                "El convenio no está en aprobación de firmas"
            )
        return convenio

    def _proceso_activo(
        self, convenio_id: int, *, bloquear: bool
    ) -> ProcesoFirmasConvenio:
        consulta = (
            select(ProcesoFirmasConvenio)
            .options(
                selectinload(ProcesoFirmasConvenio.version_convenio),
                selectinload(ProcesoFirmasConvenio.firmas).selectinload(
                    FirmaConvenio.invitaciones
                )
            )
            .where(
                ProcesoFirmasConvenio.convenio_id == convenio_id,
                ProcesoFirmasConvenio.estado.in_(
                    (
                        EstadoProcesoFirmasConvenio.CONFIGURACION.value,
                        EstadoProcesoFirmasConvenio.EN_CURSO.value,
                    )
                ),
            )
        )
        if bloquear:
            consulta = consulta.execution_options(
                populate_existing=True
            ).with_for_update()
        proceso = self.db.scalar(consulta)
        if proceso is None:
            raise RevisionNoDisponible("No existe un proceso de firmas activo")
        return proceso

    def obtener_seguimiento(self, convenio_id: int) -> ProcesoFirmasConvenio:
        self._convenio(convenio_id, bloquear=False)
        return self._proceso_activo(convenio_id, bloquear=False)

    def _firmas_bloqueadas(self, proceso_id: int) -> list[FirmaConvenio]:
        return list(
            self.db.scalars(
                select(FirmaConvenio)
                .where(FirmaConvenio.proceso_firmas_id == proceso_id)
                .order_by(FirmaConvenio.orden)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        )

    @staticmethod
    def _validar_siete_firmas(firmas: list[FirmaConvenio]) -> None:
        esperado = [
            (orden, rol.value) for orden, rol in enumerate(ROLES_FIRMANTES, start=1)
        ]
        if len(firmas) != 7 or [
            (firma.orden, firma.rol_firmante) for firma in firmas
        ] != esperado:
            raise RevisionNoDisponible("El proceso debe contener los siete slots")
        if any(not ServicioFirmaElectronica._firma_configurada(firma) for firma in firmas):
            raise RevisionNoDisponible("Las siete firmas deben estar configuradas")

    def _crear_invitacion(
        self, firma: FirmaConvenio, generada_por_id: int
    ) -> tuple[InvitacionFirmaConvenio, str]:
        token = secrets.token_urlsafe(48)
        ahora = datetime.now(UTC)
        invitacion = InvitacionFirmaConvenio(
            firma_convenio_id=firma.id,
            token_hash=hash_token_firma(token),
            expira_en=ahora + VIGENCIA_INVITACION_FIRMA,
            generada_por_id=generada_por_id,
        )
        self.db.add(invitacion)
        return invitacion, token

    def _enviar(
        self,
        invitacion: InvitacionFirmaConvenio,
        token: str,
        firma: FirmaConvenio,
        convenio: Convenio,
    ) -> None:
        if self.enviador is None or self.frontend_url is None:
            raise RuntimeError("El servicio de correo no está configurado")
        if not firma.correo_firmante:
            raise ReferenciaConvenioInvalida(
                "La firma electrónica no tiene correo configurado"
            )
        enlace = f"{self.frontend_url.rstrip('/')}/firma-convenio#token={token}"
        identificador = convenio.codigo or f"#{convenio.id}"
        rol = firma.rol_firmante.replace("_", " ").title()
        cargo = firma.cargo_firmante or rol
        self.enviador.enviar(
            MensajeCorreo(
                destinatario=firma.correo_firmante,
                asunto=f"Firma electrónica - elaboración de convenio {identificador}",
                texto=(
                    "La ORI de la Universidad de San Buenaventura Cali solicita su "
                    f"firma electrónica para la elaboración de convenio {identificador}. "
                    f"Rol esperado: {rol}. Cargo: {cargo}.\n"
                    f"Acceda mediante este enlace individual: {enlace}\n"
                    "El enlace vence en 1 hora."
                ),
                html=(
                    "<h1>Firma electrónica de elaboración de convenio</h1>"
                    "<p>La ORI solicita su firma electrónica para la elaboración "
                    f"de convenio {escape(identificador)}.</p>"
                    f"<p><strong>Rol esperado:</strong> {escape(rol)}<br>"
                    f"<strong>Cargo:</strong> {escape(cargo)}</p>"
                    f'<p><a href="{escape(enlace)}">Revisar y firmar elaboración '
                    "de convenio</a></p>"
                    "<p>El enlace vence en 1 hora.</p>"
                ),
            )
        )
        invitacion.enviado_en = datetime.now(UTC)
        self.db.commit()

    def enviar_invitaciones(
        self, convenio_id: int, usuario: Usuario
    ) -> ProcesoFirmasConvenio:
        convenio = self._convenio(convenio_id, bloquear=True)
        proceso = self._proceso_activo(convenio_id, bloquear=True)
        if proceso.estado != EstadoProcesoFirmasConvenio.EN_CURSO.value:
            raise RevisionNoDisponible("El proceso de firmas no está en curso")
        firmas = self._firmas_bloqueadas(proceso.id)
        self._validar_siete_firmas(firmas)
        electronicas = [
            firma
            for firma in firmas
            if firma.modalidad == ModalidadFirma.ELECTRONICA.value
        ]
        if any(firma.estado != EstadoFirmaConvenio.PENDIENTE.value for firma in electronicas):
            raise RevisionNoDisponible(
                "Solo pueden invitarse firmas electrónicas pendientes"
            )
        ids = [firma.id for firma in electronicas]
        existente = self.db.scalar(
            select(InvitacionFirmaConvenio.id)
            .where(
                InvitacionFirmaConvenio.firma_convenio_id.in_(ids),
                InvitacionFirmaConvenio.utilizado_en.is_(None),
                InvitacionFirmaConvenio.revocado_en.is_(None),
            )
            .limit(1)
        ) if ids else None
        if existente is not None:
            raise RevisionNoDisponible(
                "Una o más firmas ya tienen una invitación activa"
            )
        generadas = [
            (firma, *self._crear_invitacion(firma, usuario.id))
            for firma in electronicas
        ]
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise RevisionNoDisponible(
                "Una o más firmas ya tienen una invitación activa"
            ) from exc
        except SQLAlchemyError:
            self.db.rollback()
            raise

        fallidas: list[int] = []
        for firma, invitacion, token in generadas:
            try:
                self._enviar(invitacion, token, firma, convenio)
            except ErrorEnvioCorreo:
                self.db.rollback()
                fallidas.append(firma.id)
        if fallidas:
            raise EntregaInvitacionesFirmaError(fallidas)
        return self.obtener_seguimiento(convenio_id)

    def reenviar(
        self, convenio_id: int, firma_id: int, usuario: Usuario
    ) -> InvitacionFirmaConvenio:
        convenio = self._convenio(convenio_id, bloquear=True)
        proceso = self._proceso_activo(convenio_id, bloquear=True)
        if proceso.estado != EstadoProcesoFirmasConvenio.EN_CURSO.value:
            raise RevisionNoDisponible("El proceso de firmas no está en curso")
        firma = self.db.scalar(
            select(FirmaConvenio)
            .where(
                FirmaConvenio.id == firma_id,
                FirmaConvenio.proceso_firmas_id == proceso.id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if firma is None:
            raise ConvenioNoEncontrado("Firma no encontrada para el proceso activo")
        if (
            firma.modalidad != ModalidadFirma.ELECTRONICA.value
            or firma.estado != EstadoFirmaConvenio.PENDIENTE.value
            or not self._firma_configurada(firma)
        ):
            raise RevisionNoDisponible(
                "La firma no admite una invitación electrónica"
            )
        ahora = datetime.now(UTC)
        self.db.execute(
            update(InvitacionFirmaConvenio)
            .where(
                InvitacionFirmaConvenio.firma_convenio_id == firma.id,
                InvitacionFirmaConvenio.utilizado_en.is_(None),
                InvitacionFirmaConvenio.revocado_en.is_(None),
            )
            .values(revocado_en=ahora)
        )
        invitacion, token = self._crear_invitacion(firma, usuario.id)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise RevisionNoDisponible(
                "La invitación fue reemplazada concurrentemente"
            ) from exc
        except SQLAlchemyError:
            self.db.rollback()
            raise
        self._enviar(invitacion, token, firma, convenio)
        return invitacion

    def _contexto_publico(
        self, token: str, *, bloquear: bool
    ) -> ContextoFirmaPublica:
        token_hash = hash_token_firma(token)
        referencia = self.db.execute(
            select(
                InvitacionFirmaConvenio.id,
                InvitacionFirmaConvenio.firma_convenio_id,
            ).where(InvitacionFirmaConvenio.token_hash == token_hash)
        ).one_or_none()
        if referencia is None:
            raise EnlaceFirmaConvenioError()
        invitacion_id, firma_id = referencia
        proceso_id = self.db.scalar(
            select(FirmaConvenio.proceso_firmas_id).where(
                FirmaConvenio.id == firma_id
            )
        )
        if proceso_id is None:
            raise EnlaceFirmaConvenioError()
        convenio_id = self.db.scalar(
            select(ProcesoFirmasConvenio.convenio_id).where(
                ProcesoFirmasConvenio.id == proceso_id
            )
        )
        if convenio_id is None:
            raise EnlaceFirmaConvenioError()

        consultas = [
            select(Convenio).where(Convenio.id == convenio_id),
            select(ProcesoFirmasConvenio).where(
                ProcesoFirmasConvenio.id == proceso_id,
                ProcesoFirmasConvenio.convenio_id == convenio_id,
            ),
            select(FirmaConvenio).where(
                FirmaConvenio.id == firma_id,
                FirmaConvenio.proceso_firmas_id == proceso_id,
            ),
            select(InvitacionFirmaConvenio).where(
                InvitacionFirmaConvenio.id == invitacion_id,
                InvitacionFirmaConvenio.firma_convenio_id == firma_id,
                InvitacionFirmaConvenio.token_hash == token_hash,
            ),
        ]
        if bloquear:
            consultas = [
                consulta.execution_options(populate_existing=True).with_for_update()
                for consulta in consultas
            ]
        convenio = self.db.scalar(consultas[0])
        proceso = self.db.scalar(consultas[1])
        firma = self.db.scalar(consultas[2])
        invitacion = self.db.scalar(consultas[3])
        if not all((convenio, proceso, firma, invitacion)):
            raise EnlaceFirmaConvenioError()
        assert convenio is not None
        assert proceso is not None
        assert firma is not None
        assert invitacion is not None

        if (
            firma.estado == EstadoFirmaConvenio.FIRMADA.value
            or invitacion.utilizado_en is not None
        ):
            raise EnlaceFirmaConvenioError("FIRMA_YA_REGISTRADA")
        ahora = datetime.now(UTC)
        if invitacion.revocado_en is not None:
            raise EnlaceFirmaConvenioError("ENLACE_NO_DISPONIBLE")
        if invitacion.expira_en <= ahora:
            raise EnlaceFirmaConvenioError("ENLACE_EXPIRADO")
        if (
            invitacion.enviado_en is None
            or proceso.estado != EstadoProcesoFirmasConvenio.EN_CURSO.value
            or firma.modalidad != ModalidadFirma.ELECTRONICA.value
            or firma.estado != EstadoFirmaConvenio.PENDIENTE.value
            or convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_APROBACION_FIRMAS
        ):
            raise EnlaceFirmaConvenioError("ENLACE_NO_DISPONIBLE")
        version = self.db.get(VersionConvenio, proceso.version_convenio_id)
        if version is None or version.convenio_id != convenio.id:
            raise EnlaceFirmaConvenioError("ENLACE_NO_DISPONIBLE")
        return ContextoFirmaPublica(
            convenio=convenio,
            proceso=proceso,
            firma=firma,
            invitacion=invitacion,
            version=version,
        )

    def acceder(self, token: str) -> ContextoFirmaPublica:
        return self._contexto_publico(token, bloquear=False)

    def firmar(self, token: str, firma_data_url: str, confirmacion: bool) -> FirmaConvenio:
        if not confirmacion:
            raise FirmaElectronicaInvalida(
                "Debe confirmar expresamente su conformidad antes de firmar"
            )
        try:
            firma_png, firma_hash = decodificar_firma_png(firma_data_url)
        except FirmaPngInvalida as exc:
            raise FirmaElectronicaInvalida(str(exc)) from exc
        contexto = self._contexto_publico(token, bloquear=True)
        ahora = datetime.now(UTC)
        contexto.firma.firma_png = firma_png
        contexto.firma.firma_sha256 = firma_hash
        contexto.firma.estado = EstadoFirmaConvenio.FIRMADA.value
        contexto.firma.fecha_firma = ahora
        contexto.invitacion.utilizado_en = ahora
        self.db.execute(
            update(InvitacionFirmaConvenio)
            .where(
                InvitacionFirmaConvenio.firma_convenio_id == contexto.firma.id,
                InvitacionFirmaConvenio.id != contexto.invitacion.id,
                InvitacionFirmaConvenio.utilizado_en.is_(None),
                InvitacionFirmaConvenio.revocado_en.is_(None),
            )
            .values(revocado_en=ahora)
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise EnlaceFirmaConvenioError("ENLACE_NO_DISPONIBLE") from exc
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return contexto.firma
