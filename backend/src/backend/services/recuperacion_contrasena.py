import logging
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import urlencode

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session, selectinload

from backend.core.security import hash_contrasena
from backend.models.token_credencial import TipoTokenCredencial, TokenCredencial
from backend.models.usuario import Usuario
from backend.services.correo import EnviadorCorreo, ErrorEnvioCorreo, MensajeCorreo
from backend.services.sesiones import RepositorioSesiones

VIGENCIA_TOKEN_RECUPERACION = timedelta(minutes=30)
ASUNTO_RECUPERACION = "Restablece tu contraseña de ORI USB Cali"
MENSAJE_RECUPERACION = (
    "Si existe una cuenta habilitada asociada a este correo, enviaremos "
    "instrucciones para restablecer la contraseña."
)
logger = logging.getLogger(__name__)


class TokenRecuperacionInvalidoError(Exception):
    def __init__(self, codigo: str = "ENLACE_INVALIDO") -> None:
        super().__init__("El enlace de recuperación no es válido")
        self.codigo = codigo


class ServicioRecuperacionContrasena:
    def __init__(
        self,
        db: Session,
        enviador: EnviadorCorreo,
        sesiones: RepositorioSesiones,
        frontend_url: str,
    ) -> None:
        self.db = db
        self.enviador = enviador
        self.sesiones = sesiones
        self.frontend_url = frontend_url.rstrip("/")

    @staticmethod
    def hash_token(token: str) -> str:
        return sha256(token.encode()).hexdigest()

    def solicitar(self, correo: str) -> None:
        usuario = self.db.scalar(
            select(Usuario)
            .where(func.lower(Usuario.correo) == correo.lower())
            .with_for_update()
        )
        if (
            usuario is None
            or not usuario.activo
            or usuario.correo_verificado_en is None
        ):
            return

        ahora = datetime.now(UTC)
        self.db.execute(
            update(TokenCredencial)
            .where(
                TokenCredencial.usuario_id == usuario.id,
                TokenCredencial.tipo
                == TipoTokenCredencial.RECUPERACION_CONTRASENA.value,
                TokenCredencial.utilizado_en.is_(None),
                TokenCredencial.invalidado_en.is_(None),
            )
            .values(invalidado_en=ahora)
        )
        token_plano = secrets.token_urlsafe(32)
        self.db.add(
            TokenCredencial(
                usuario=usuario,
                tipo=TipoTokenCredencial.RECUPERACION_CONTRASENA.value,
                token_hash=self.hash_token(token_plano),
                expira_en=ahora + VIGENCIA_TOKEN_RECUPERACION,
            )
        )
        self.db.commit()

        try:
            self._enviar(usuario, token_plano)
        except ErrorEnvioCorreo:
            logger.warning("Falló el envío de una recuperación solicitada")

    def restablecer(self, token_plano: str, nueva_contrasena: str) -> None:
        credencial = self._obtener_credencial_valida(token_plano, bloquear=True)
        ahora = datetime.now(UTC)
        usuario = credencial.usuario

        usuario.hash_contrasena = hash_contrasena(nueva_contrasena)
        credencial.utilizado_en = ahora
        self.db.flush()
        self.sesiones.invalidar_usuario(usuario.id)
        self.db.commit()

    def validar(self, token_plano: str) -> None:
        self._obtener_credencial_valida(token_plano, bloquear=False)

    def _obtener_credencial_valida(
        self, token_plano: str, *, bloquear: bool
    ) -> TokenCredencial:
        consulta: Select[tuple[TokenCredencial]] = (
            select(TokenCredencial)
            .options(selectinload(TokenCredencial.usuario))
            .where(
                TokenCredencial.token_hash == self.hash_token(token_plano),
                TokenCredencial.tipo
                == TipoTokenCredencial.RECUPERACION_CONTRASENA.value,
            )
        )
        if bloquear:
            consulta = consulta.with_for_update()
        credencial = self.db.scalar(consulta)
        if credencial is None:
            raise TokenRecuperacionInvalidoError
        ahora = datetime.now(UTC)
        if credencial.expira_en <= ahora:
            raise TokenRecuperacionInvalidoError("ENLACE_EXPIRADO")
        if credencial.utilizado_en is not None or credencial.invalidado_en is not None:
            raise TokenRecuperacionInvalidoError("ENLACE_NO_DISPONIBLE")

        usuario = credencial.usuario
        if (
            usuario is None
            or not usuario.activo
            or usuario.correo_verificado_en is None
        ):
            raise TokenRecuperacionInvalidoError("ENLACE_NO_DISPONIBLE")
        return credencial

    def _enviar(self, usuario: Usuario, token_plano: str) -> None:
        enlace = (
            f"{self.frontend_url}/restablecer-contrasena?"
            f"{urlencode({'token': token_plano})}"
        )
        self.enviador.enviar(
            MensajeCorreo(
                destinatario=usuario.correo,
                asunto=ASUNTO_RECUPERACION,
                texto=(
                    "Se solicitó restablecer la contraseña de su cuenta de ORI USB "
                    f"Cali. Restablezca su contraseña en: {enlace}\n"
                    "El enlace vence en 30 minutos. Si no realizó esta solicitud, "
                    "puede ignorar este mensaje."
                ),
                html=(
                    "<h1>Restablece tu contraseña</h1>"
                    "<p>Se solicitó restablecer la contraseña de su cuenta de "
                    "ORI USB Cali.</p>"
                    f'<p><a href="{enlace}">Restablecer contraseña</a></p>'
                    "<p>Este enlace vence en 30 minutos.</p>"
                    "<p>Si no realizó esta solicitud, puede ignorar este mensaje.</p>"
                ),
            )
        )
