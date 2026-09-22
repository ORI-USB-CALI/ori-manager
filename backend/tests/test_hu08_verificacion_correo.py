import json
import re
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import httpx
from sqlalchemy import func, select

from backend.core.config import settings
from backend.core.roles import CodigoRol
from backend.main import app
from backend.models.token_credencial import TipoTokenCredencial, TokenCredencial
from backend.models.usuario import Usuario
from backend.services.correo import (
    BREVO_EMAIL_URL,
    CorreoBrevo,
    CorreoLocal,
    MensajeCorreo,
    get_enviador_correo,
)
from backend.services.verificacion_correo import ASUNTO_VERIFICACION, MENSAJE_REENVIO


def _datos(correo: str) -> dict[str, str]:
    return {
        "correo": correo,
        "contrasena": "ClaveSegura123",
        "confirmacion_contrasena": "ClaveSegura123",
        "nombre_completo": "Solicitante de verificación",
        "documento_identidad": "CC-123",
        "entidad_externa": "Entidad de prueba",
        "cargo": "Profesional",
    }


def _token_de_ultimo_correo(correo_local: CorreoLocal) -> str:
    coincidencia = re.search(r"[?&]token=([^\s<\"]+)", correo_local.mensajes[-1].texto)
    assert coincidencia is not None
    return coincidencia.group(1)


def test_registro_crea_hash_token_24h_y_correo_local(db, client, correo_local):
    inicio = datetime.now(UTC)
    respuesta = client.post(
        "/api/auth/registro", json=_datos("token-registro@example.com")
    )

    assert respuesta.status_code == 201
    usuario = db.scalar(
        select(Usuario).where(Usuario.correo == "token-registro@example.com")
    )
    assert usuario is not None and usuario.correo_verificado_en is None
    token_db = db.scalar(
        select(TokenCredencial).where(TokenCredencial.usuario_id == usuario.id)
    )
    assert token_db is not None
    assert token_db.tipo == TipoTokenCredencial.VERIFICACION_CORREO
    token_plano = _token_de_ultimo_correo(correo_local)
    assert token_plano != token_db.token_hash
    assert sha256(token_plano.encode()).hexdigest() == token_db.token_hash
    assert len(token_db.token_hash) == 64
    assert inicio + timedelta(hours=23, minutes=59) < token_db.expira_en
    assert token_db.expira_en < inicio + timedelta(hours=24, minutes=1)

    mensaje = correo_local.mensajes[-1]
    enlace = f"http://localhost:5173/verificar-correo?token={token_plano}"
    assert mensaje.destinatario == usuario.correo
    assert mensaje.asunto == ASUNTO_VERIFICACION
    assert enlace in mensaje.texto
    assert enlace in mensaje.html
    assert "24 horas" in mensaje.texto


def test_brevo_envia_sender_destinatario_asunto_y_api_key_solo_header():
    solicitudes: list[httpx.Request] = []

    def responder(request: httpx.Request) -> httpx.Response:
        solicitudes.append(request)
        return httpx.Response(201, request=request)

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    brevo = CorreoBrevo(
        api_key="clave-controlada-prueba",
        remitente_correo="ori@example.com",
        remitente_nombre="ORI USB Cali",
        cliente=cliente,
    )
    brevo.enviar(
        MensajeCorreo(
            destinatario="solicitante@example.com",
            asunto=ASUNTO_VERIFICACION,
            texto="Contenido",
            html="<p>Contenido</p>",
        )
    )

    request = solicitudes[0]
    payload = json.loads(request.content)
    assert str(request.url) == BREVO_EMAIL_URL
    assert request.headers["api-key"] == "clave-controlada-prueba"
    assert payload["to"] == [{"email": "solicitante@example.com"}]
    assert payload["sender"] == {
        "name": "ORI USB Cali",
        "email": "ori@example.com",
    }
    assert payload["subject"] == ASUNTO_VERIFICACION
    assert "clave-controlada-prueba" not in request.content.decode()


def test_resolucion_correo_fail_closed(monkeypatch):
    get_enviador_correo.cache_clear()
    monkeypatch.setattr(settings, "email_provider", "local")
    monkeypatch.setattr(settings, "app_env", "staging")
    try:
        try:
            get_enviador_correo()
            raise AssertionError("Debió rechazar correo local fuera de development")
        except RuntimeError as exc:
            assert "development" in str(exc)
    finally:
        monkeypatch.setattr(settings, "app_env", "development")
        get_enviador_correo.cache_clear()


def test_brevo_exige_configuracion_completa(monkeypatch):
    get_enviador_correo.cache_clear()
    monkeypatch.setattr(settings, "email_provider", "brevo")
    monkeypatch.setattr(settings, "brevo_api_key", None)
    monkeypatch.setattr(settings, "email_from_address", None)
    monkeypatch.setattr(settings, "email_from_name", None)
    try:
        try:
            get_enviador_correo()
            raise AssertionError("Debió rechazar configuración incompleta")
        except RuntimeError as exc:
            assert "BREVO_API_KEY" in str(exc)
            assert "EMAIL_FROM_ADDRESS" in str(exc)
    finally:
        monkeypatch.setattr(settings, "email_provider", "local")
        get_enviador_correo.cache_clear()


def test_verificacion_valida_marca_usuario_token_y_habilita_login(
    db, client, correo_local
):
    datos = _datos("verificar-login@example.com")
    assert client.post("/api/auth/registro", json=datos).status_code == 201
    assert client.post(
        "/api/auth/login",
        json={"correo": datos["correo"], "contrasena": datos["contrasena"]},
    ).status_code == 403
    token = _token_de_ultimo_correo(correo_local)

    respuesta = client.post("/api/auth/verificar-correo", json={"token": token})

    assert respuesta.status_code == 200
    usuario = db.scalar(select(Usuario).where(Usuario.correo == datos["correo"]))
    credencial = db.scalar(
        select(TokenCredencial).where(TokenCredencial.usuario_id == usuario.id)
    )
    db.refresh(usuario)
    assert usuario.correo_verificado_en is not None
    assert credencial is not None and credencial.utilizado_en is not None
    login = client.post(
        "/api/auth/login",
        json={"correo": datos["correo"], "contrasena": datos["contrasena"]},
    )
    assert login.status_code == 200


def test_token_reutilizado_es_rechazado(client, correo_local):
    assert client.post(
        "/api/auth/registro", json=_datos("reutilizado@example.com")
    ).status_code == 201
    token = _token_de_ultimo_correo(correo_local)
    assert client.post("/api/auth/verificar-correo", json={"token": token}).status_code == 200

    repetido = client.post("/api/auth/verificar-correo", json={"token": token})

    assert repetido.status_code == 400
    assert repetido.json()["detail"]["codigo"] == "ENLACE_NO_DISPONIBLE"


def test_token_expirado_e_inexistente_son_rechazados(db, client, correo_local):
    assert client.post(
        "/api/auth/registro", json=_datos("expirado@example.com")
    ).status_code == 201
    token = _token_de_ultimo_correo(correo_local)
    credencial = db.scalar(
        select(TokenCredencial).where(
            TokenCredencial.token_hash == sha256(token.encode()).hexdigest()
        )
    )
    credencial.expira_en = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    expirado = client.post("/api/auth/verificar-correo", json={"token": token})
    inexistente = client.post(
        "/api/auth/verificar-correo", json={"token": "token-inexistente"}
    )

    assert expirado.status_code == 400
    assert expirado.json()["detail"]["codigo"] == "ENLACE_EXPIRADO"
    assert inexistente.status_code == 400
    assert inexistente.json()["detail"]["codigo"] == "ENLACE_INVALIDO"


def test_reenvio_invalida_anterior_genera_nuevo_y_no_duplica_usuario(
    db, client, correo_local
):
    correo = "reenvio@example.com"
    assert client.post("/api/auth/registro", json=_datos(correo)).status_code == 201
    token_anterior = _token_de_ultimo_correo(correo_local)
    usuarios_antes = db.scalar(select(func.count()).select_from(Usuario))

    respuesta = client.post(
        "/api/auth/reenviar-verificacion", json={"correo": correo}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["message"] == MENSAJE_REENVIO
    assert db.scalar(select(func.count()).select_from(Usuario)) == usuarios_antes
    tokens = list(
        db.scalars(
            select(TokenCredencial)
            .join(Usuario)
            .where(Usuario.correo == correo)
            .order_by(TokenCredencial.id)
        )
    )
    assert len(tokens) == 2
    assert tokens[0].invalidado_en is not None
    token_nuevo = _token_de_ultimo_correo(correo_local)
    assert token_nuevo != token_anterior
    assert tokens[1].token_hash == sha256(token_nuevo.encode()).hexdigest()
    assert client.post(
        "/api/auth/verificar-correo", json={"token": token_anterior}
    ).status_code == 400


def test_reenvio_inexistente_y_verificado_es_generico_sin_tokens(
    db, client, crear_usuario
):
    verificado = crear_usuario(
        CodigoRol.SOLICITANTE_EXTERNO, correo="ya-verificado@example.com"
    )
    cantidad_antes = db.scalar(select(func.count()).select_from(TokenCredencial))

    inexistente = client.post(
        "/api/auth/reenviar-verificacion", json={"correo": "nadie@example.com"}
    )
    existente = client.post(
        "/api/auth/reenviar-verificacion", json={"correo": verificado.correo}
    )

    assert inexistente.status_code == existente.status_code == 200
    assert inexistente.json() == existente.json() == {"message": MENSAJE_REENVIO}
    assert db.scalar(select(func.count()).select_from(TokenCredencial)) == cantidad_antes


def test_fallo_brevo_conserva_usuario_token_pendiente_y_no_usa_local(db, client):
    solicitudes: list[httpx.Request] = []

    def fallar(request: httpx.Request) -> httpx.Response:
        solicitudes.append(request)
        return httpx.Response(503, request=request)

    brevo = CorreoBrevo(
        api_key="clave-controlada-fallo",
        remitente_correo="ori@example.com",
        remitente_nombre="ORI USB Cali",
        cliente=httpx.Client(transport=httpx.MockTransport(fallar)),
    )
    app.dependency_overrides[get_enviador_correo] = lambda: brevo
    correo = "fallo-envio@example.com"

    respuesta = client.post("/api/auth/registro", json=_datos(correo))

    assert respuesta.status_code == 201
    assert len(solicitudes) == 1
    usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
    assert usuario is not None and usuario.correo_verificado_en is None
    assert db.scalar(
        select(TokenCredencial).where(TokenCredencial.usuario_id == usuario.id)
    ) is not None


def test_fallo_proveedor_en_reenvio_conserva_respuesta_anti_enumeracion(
    db, client, crear_usuario, caplog
):
    correo = "fallo-reenvio@example.com"
    assert client.post("/api/auth/registro", json=_datos(correo)).status_code == 201
    usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
    assert usuario is not None
    hash_contrasena_original = usuario.hash_contrasena
    verificado = crear_usuario(
        CodigoRol.SOLICITANTE_EXTERNO, correo="verificado-reenvio@example.com"
    )
    solicitudes: list[httpx.Request] = []

    def fallar(request: httpx.Request) -> httpx.Response:
        solicitudes.append(request)
        return httpx.Response(503, request=request)

    brevo = CorreoBrevo(
        api_key="clave-controlada-reenvio",
        remitente_correo="ori@example.com",
        remitente_nombre="ORI USB Cali",
        cliente=httpx.Client(transport=httpx.MockTransport(fallar)),
    )
    app.dependency_overrides[get_enviador_correo] = lambda: brevo
    cantidad_usuarios = db.scalar(select(func.count()).select_from(Usuario))

    respuestas = [
        client.post("/api/auth/reenviar-verificacion", json={"correo": correo}),
        client.post(
            "/api/auth/reenviar-verificacion",
            json={"correo": "inexistente-reenvio@example.com"},
        ),
        client.post(
            "/api/auth/reenviar-verificacion", json={"correo": verificado.correo}
        ),
    ]

    primera = respuestas[0]
    assert all(respuesta.status_code == primera.status_code == 200 for respuesta in respuestas)
    assert all(respuesta.content == primera.content for respuesta in respuestas)
    assert all(dict(respuesta.headers) == dict(primera.headers) for respuesta in respuestas)
    assert primera.json() == {"message": MENSAJE_REENVIO}
    assert len(solicitudes) == 1
    assert "Falló el envío de una verificación solicitada" in caplog.text
    assert correo not in caplog.text
    assert db.scalar(select(func.count()).select_from(Usuario)) == cantidad_usuarios
    db.refresh(usuario)
    assert usuario.correo_verificado_en is None
    assert usuario.hash_contrasena == hash_contrasena_original
