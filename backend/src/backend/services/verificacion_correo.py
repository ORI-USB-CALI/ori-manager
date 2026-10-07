import logging
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import urlencode

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.core.roles import CodigoRol
from backend.models.token_credencial import TipoTokenCredencial, TokenCredencial
from backend.models.usuario import Usuario
from backend.services.correo import (
    EnviadorCorreo,
    ErrorEnvioCorreo,
    MensajeCorreo,
)

VIGENCIA_TOKEN_VERIFICACION = timedelta(hours=24)
ASUNTO_VERIFICACION = "Verifica tu cuenta de ORI USB Cali"
MENSAJE_REENVIO = (
    "Si existe una cuenta pendiente de verificación, enviaremos un nuevo enlace "
    "al correo indicado."
)
ROLES_SOLICITANTES = {
    CodigoRol.SOLICITANTE_INTERNO.value,
    CodigoRol.SOLICITANTE_EXTERNO.value,
}
logger = logging.getLogger(__name__)


class TokenVerificacionInvalidoError(Exception):
    def __init__(self, codigo: str = "ENLACE_INVALIDO") -> None:
        super().__init__("El enlace de verificación no es válido o ya fue utilizado")
        self.codigo = codigo


class ServicioVerificacionCorreo:
    def __init__(
        self,
        db: Session,
        enviador: EnviadorCorreo,
        frontend_url: str,
    ) -> None:
        self.db = db
        self.enviador = enviador
        self.frontend_url = frontend_url.rstrip("/")

    @staticmethod
    def hash_token(token: str) -> str:
        return sha256(token.encode()).hexdigest()

    def crear_token(self, usuario: Usuario) -> tuple[TokenCredencial, str]:
        token_plano = secrets.token_urlsafe(32)
        ahora = datetime.now(UTC)
        credencial = TokenCredencial(
            usuario=usuario,
            tipo=TipoTokenCredencial.VERIFICACION_CORREO.value,
            token_hash=self.hash_token(token_plano),
            expira_en=ahora + VIGENCIA_TOKEN_VERIFICACION,
        )
        self.db.add(credencial)
        return credencial, token_plano

    def enviar(self, usuario: Usuario, token_plano: str) -> None:
        enlace = self._construir_enlace(token_plano)
        self.enviador.enviar(
            MensajeCorreo(
                destinatario=usuario.correo,
                asunto=ASUNTO_VERIFICACION,
                texto=(
                    "Se creó una cuenta en ORI USB Cali. Verifique su correo en: "
                    f"{enlace}\nEl enlace vence en 24 horas. Si no realizó el "
                    "registro, puede ignorar este mensaje."
                ),
                html=(
                    "<h1>Verifica tu cuenta</h1>"
                    "<p>Se creó una cuenta en ORI USB Cali.</p>"
                    f'<p><a href="{enlace}">Verificar mi correo</a></p>'
                    "<p>Este enlace vence en 24 horas.</p>"
                    "<p>Si no realizó el registro, puede ignorar este mensaje.</p>"
                ),
            )
        )

    def intentar_enviar(self, usuario: Usuario, token_plano: str) -> bool:
        try:
            self.enviar(usuario, token_plano)
        except ErrorEnvioCorreo:
            return False
        return True

    def verificar(self, token_plano: str) -> None:
        ahora = datetime.now(UTC)
        credencial = self.db.scalar(
            select(TokenCredencial)
            .options(selectinload(TokenCredencial.usuario))
            .where(
                TokenCredencial.token_hash == self.hash_token(token_plano),
                TokenCredencial.tipo == TipoTokenCredencial.VERIFICACION_CORREO.value,
            )
            .with_for_update()
        )
        if credencial is None:
            raise TokenVerificacionInvalidoError
        if credencial.expira_en <= ahora:
            raise TokenVerificacionInvalidoError("ENLACE_EXPIRADO")
        if credencial.utilizado_en is not None or credencial.invalidado_en is not None:
            raise TokenVerificacionInvalidoError("ENLACE_NO_DISPONIBLE")
        if credencial.usuario.correo_verificado_en is not None:
            raise TokenVerificacionInvalidoError("ENLACE_NO_DISPONIBLE")

        credencial.usuario.correo_verificado_en = ahora
        credencial.utilizado_en = ahora
        self.db.commit()

    def reenviar(self, correo: str) -> None:
        usuario = self.db.scalar(
            select(Usuario)
            .options(joinedload(Usuario.rol))
            .where(func.lower(Usuario.correo) == correo.lower())
        )
        if (
            usuario is None
            or usuario.correo_verificado_en is not None
            or usuario.rol.codigo not in ROLES_SOLICITANTES
        ):
            return

        ahora = datetime.now(UTC)
        self.db.execute(
            update(TokenCredencial)
            .where(
                TokenCredencial.usuario_id == usuario.id,
                TokenCredencial.tipo == TipoTokenCredencial.VERIFICACION_CORREO.value,
                TokenCredencial.utilizado_en.is_(None),
                TokenCredencial.invalidado_en.is_(None),
            )
            .values(invalidado_en=ahora)
        )
        _, token_plano = self.crear_token(usuario)
        self.db.commit()
        if not self.intentar_enviar(usuario, token_plano):
            logger.warning("Falló el envío de una verificación solicitada")

    def _construir_enlace(self, token_plano: str) -> str:
        return (
            f"{self.frontend_url}/verificar-correo?{urlencode({'token': token_plano})}"
        )
