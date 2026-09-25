import re
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from sqlalchemy import func, select

from backend.core.roles import CodigoRol
from backend.core.security import generar_token_sesion, verificar_contrasena
from backend.main import app
from backend.models.token_credencial import TipoTokenCredencial, TokenCredencial
from backend.services.auth import DURACION_SESION
from backend.services.correo import ErrorEnvioCorreo, get_enviador_correo
from backend.services.recuperacion_contrasena import (
    ASUNTO_RECUPERACION,
    MENSAJE_RECUPERACION,
)


def _solicitar(client, correo: str):
    return client.post("/api/auth/recuperar-contrasena", json={"correo": correo})


def _token_de_ultimo_correo(correo_local) -> str:
    coincidencia = re.search(r"[?&]token=([^\s<\"]+)", correo_local.mensajes[-1].texto)
    assert coincidencia is not None
    return coincidencia.group(1)


def _restablecer(client, token: str, contrasena: str = "NuevaClave456!"):
    return client.post(
        "/api/auth/restablecer-contrasena",
        json={
            "token": token,
            "nueva_contrasena": contrasena,
            "confirmacion_contrasena": contrasena,
        },
    )


def _validar(client, token: str):
    return client.post(
        "/api/auth/validar-recuperacion-contrasena", json={"token": token}
    )


@pytest.mark.parametrize("rol", list(CodigoRol))
def test_cuenta_activa_verificada_de_cualquier_rol_genera_token_hash_30_min_y_correo(
    db, client, correo_local, crear_usuario, rol
):
    usuario = crear_usuario(rol, correo=f"recuperacion-{rol.value.lower()}@example.com")
    inicio = datetime.now(UTC)

    respuesta = _solicitar(client, usuario.correo)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"message": MENSAJE_RECUPERACION}
    credencial = db.scalar(
        select(TokenCredencial).where(TokenCredencial.usuario_id == usuario.id)
    )
    assert credencial is not None
    assert credencial.tipo == TipoTokenCredencial.RECUPERACION_CONTRASENA
    token_plano = _token_de_ultimo_correo(correo_local)
    assert token_plano != credencial.token_hash
    assert sha256(token_plano.encode()).hexdigest() == credencial.token_hash
    assert len(credencial.token_hash) == 64
    assert inicio + timedelta(minutes=29, seconds=50) < credencial.expira_en
    assert credencial.expira_en < inicio + timedelta(minutes=30, seconds=10)

    mensaje = correo_local.mensajes[-1]
    enlace = f"http://localhost:5173/restablecer-contrasena?token={token_plano}"
    assert mensaje.asunto == ASUNTO_RECUPERACION
    assert mensaje.destinatario == usuario.correo
    assert enlace in mensaje.texto and enlace in mensaje.html
    assert "30 minutos" in mensaje.texto and "30 minutos" in mensaje.html
    assert "ClaveSegura123" not in mensaje.texto
    assert "ClaveSegura123" not in mensaje.html


def test_prevalidacion_vigente_no_consume_cambia_password_ni_invalida_sesion(
    db, client, correo_local, crear_usuario, sesiones
):
    usuario = crear_usuario(correo="prevalidacion-vigente@example.com")
    hash_original = usuario.hash_contrasena
    token_sesion = generar_token_sesion()
    sesiones.crear(usuario.id, token_sesion, datetime.now(UTC) + DURACION_SESION)
    _solicitar(client, usuario.correo)
    token = _token_de_ultimo_correo(correo_local)

    respuesta = _validar(client, token)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"message": "Enlace válido."}
    credencial = db.scalar(
        select(TokenCredencial).where(
            TokenCredencial.token_hash == sha256(token.encode()).hexdigest()
        )
    )
    assert credencial is not None
    assert credencial.utilizado_en is None
    assert credencial.invalidado_en is None
    db.refresh(usuario)
    assert usuario.hash_contrasena == hash_original
    assert sesiones.obtener_por_token(token_sesion) is not None

    assert _restablecer(client, token).status_code == 200
    db.refresh(credencial)
    assert credencial.utilizado_en is not None
    assert sesiones.obtener_por_token(token_sesion) is None


def test_prevalidacion_token_inexistente_retorna_enlace_invalido(client):
    respuesta = _validar(client, "token-inexistente-prevalidacion")

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "ENLACE_INVALIDO"


def test_prevalidacion_token_expirado_retorna_enlace_expirado(
    db, client, correo_local, crear_usuario
):
    usuario = crear_usuario(correo="prevalidacion-expirado@example.com")
    _solicitar(client, usuario.correo)
    token = _token_de_ultimo_correo(correo_local)
    credencial = db.scalar(
        select(TokenCredencial).where(
            TokenCredencial.token_hash == sha256(token.encode()).hexdigest()
        )
    )
    credencial.expira_en = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    respuesta = _validar(client, token)

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "ENLACE_EXPIRADO"
    db.refresh(credencial)
    assert credencial.utilizado_en is None


def test_prevalidacion_token_utilizado_retorna_enlace_no_disponible(
    client, correo_local, crear_usuario
):
    usuario = crear_usuario(correo="prevalidacion-utilizado@example.com")
    _solicitar(client, usuario.correo)
    token = _token_de_ultimo_correo(correo_local)
    assert _restablecer(client, token).status_code == 200

    respuesta = _validar(client, token)

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "ENLACE_NO_DISPONIBLE"


def test_prevalidacion_token_invalidado_retorna_enlace_no_disponible(
    client, correo_local, crear_usuario
):
    usuario = crear_usuario(correo="prevalidacion-invalidado@example.com")
    _solicitar(client, usuario.correo)
    token_anterior = _token_de_ultimo_correo(correo_local)
    _solicitar(client, usuario.correo)

    respuesta = _validar(client, token_anterior)

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "ENLACE_NO_DISPONIBLE"


def test_nueva_solicitud_invalida_solo_recuperaciones_pendientes(
    db, client, correo_local, crear_usuario
):
    usuario = crear_usuario(correo="reemplazo-recovery@example.com")
    verificacion = TokenCredencial(
        usuario=usuario,
        tipo=TipoTokenCredencial.VERIFICACION_CORREO.value,
        token_hash=sha256(b"token-verificacion-independiente").hexdigest(),
        expira_en=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(verificacion)
    db.commit()
    assert _solicitar(client, usuario.correo).status_code == 200
    token_anterior = _token_de_ultimo_correo(correo_local)

    assert _solicitar(client, usuario.correo).status_code == 200
    token_nuevo = _token_de_ultimo_correo(correo_local)

    recuperaciones = list(
        db.scalars(
            select(TokenCredencial)
            .where(
                TokenCredencial.usuario_id == usuario.id,
                TokenCredencial.tipo
                == TipoTokenCredencial.RECUPERACION_CONTRASENA.value,
            )
            .order_by(TokenCredencial.id)
        )
    )
    assert len(recuperaciones) == 2
    assert recuperaciones[0].invalidado_en is not None
    assert recuperaciones[1].invalidado_en is None
    assert token_anterior != token_nuevo
    db.refresh(verificacion)
    assert verificacion.invalidado_en is None
    assert _restablecer(client, token_anterior).json()["detail"]["codigo"] == "ENLACE_NO_DISPONIBLE"


def test_cuentas_no_elegibles_no_generan_token_ni_correo(
    db, client, correo_local, crear_usuario
):
    inactivo = crear_usuario(activo=False, correo="inactivo-recovery@example.com")
    no_verificado = crear_usuario(correo="sin-verificar-recovery@example.com")
    no_verificado.correo_verificado_en = None
    db.commit()
    cantidad_inicial = db.scalar(select(func.count()).select_from(TokenCredencial))

    for correo in (
        "inexistente-recovery@example.com",
        inactivo.correo,
        no_verificado.correo,
    ):
        respuesta = _solicitar(client, correo)
        assert respuesta.status_code == 200
        assert respuesta.json() == {"message": MENSAJE_RECUPERACION}

    assert db.scalar(select(func.count()).select_from(TokenCredencial)) == cantidad_inicial
    assert correo_local.mensajes == []


class _CorreoFallido:
    def enviar(self, mensaje) -> None:
        raise ErrorEnvioCorreo("fallo controlado")


def test_respuestas_anti_enumeracion_son_equivalentes_incluso_si_falla_proveedor(
    db, client, crear_usuario, caplog
):
    valido = crear_usuario(correo="valido-anti-enumeracion@example.com")
    inactivo = crear_usuario(activo=False, correo="inactivo-anti-enumeracion@example.com")
    no_verificado = crear_usuario(correo="no-verificado-anti-enumeracion@example.com")
    no_verificado.correo_verificado_en = None
    db.commit()

    respuestas = [
        _solicitar(client, "inexistente-anti-enumeracion@example.com"),
        _solicitar(client, inactivo.correo),
        _solicitar(client, no_verificado.correo),
        _solicitar(client, valido.correo),
    ]
    app.dependency_overrides[get_enviador_correo] = lambda: _CorreoFallido()
    fallo = _solicitar(client, valido.correo)
    respuestas.append(fallo)

    primera = respuestas[0]
    assert all(respuesta.status_code == primera.status_code == 200 for respuesta in respuestas)
    assert all(respuesta.content == primera.content for respuesta in respuestas)
    for respuesta in respuestas:
        assert respuesta.headers["content-type"] == primera.headers["content-type"]
        assert respuesta.headers["content-length"] == primera.headers["content-length"]
    assert primera.json() == {"message": MENSAJE_RECUPERACION}
    assert "Falló el envío de una recuperación solicitada" in caplog.text
    assert valido.correo not in caplog.text


def test_fallo_proveedor_conserva_usuario_estado_hash_y_token(
    db, client, crear_usuario
):
    usuario = crear_usuario(correo="fallo-proveedor-recovery@example.com")
    estado_original = (
        usuario.hash_contrasena,
        usuario.activo,
        usuario.correo_verificado_en,
    )
    app.dependency_overrides[get_enviador_correo] = lambda: _CorreoFallido()

    respuesta = _solicitar(client, usuario.correo)

    assert respuesta.status_code == 200
    db.refresh(usuario)
    assert (
        usuario.hash_contrasena,
        usuario.activo,
        usuario.correo_verificado_en,
    ) == estado_original
    assert db.scalar(
        select(TokenCredencial).where(TokenCredencial.usuario_id == usuario.id)
    ) is not None


def test_reset_valido_cambia_password_consume_token_invalida_sesiones_y_no_autentica(
    db, client, correo_local, crear_usuario, sesiones
):
    usuario = crear_usuario(correo="reset-completo@example.com")
    token_sesion_1 = generar_token_sesion()
    token_sesion_2 = generar_token_sesion()
    expira = datetime.now(UTC) + DURACION_SESION
    sesiones.crear(usuario.id, token_sesion_1, expira)
    sesiones.crear(usuario.id, token_sesion_2, expira)
    assert _solicitar(client, usuario.correo).status_code == 200
    token = _token_de_ultimo_correo(correo_local)
    cantidad_sesiones_antes = len(sesiones._sesiones)

    respuesta = _restablecer(client, token)

    assert respuesta.status_code == 200
    credencial = db.scalar(
        select(TokenCredencial).where(
            TokenCredencial.token_hash == sha256(token.encode()).hexdigest()
        )
    )
    assert credencial is not None and credencial.utilizado_en is not None
    assert sesiones.obtener_por_token(token_sesion_1) is None
    assert sesiones.obtener_por_token(token_sesion_2) is None
    assert len(sesiones._sesiones) == cantidad_sesiones_antes - 2
    assert "session_id" not in respuesta.cookies

    anterior = client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123!"},
    )
    nueva = client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "NuevaClave456!"},
    )
    assert anterior.status_code == 401
    assert nueva.status_code == 200


def test_misma_contrasena_no_consume_token_y_permite_reintento_valido(
    db, client, correo_local, crear_usuario, sesiones
):
    usuario = crear_usuario(correo="misma-recovery@example.com")
    hash_original = usuario.hash_contrasena
    token_sesion = generar_token_sesion()
    sesiones.crear(
        usuario.id,
        token_sesion,
        datetime.now(UTC) + DURACION_SESION,
    )
    _solicitar(client, usuario.correo)
    token = _token_de_ultimo_correo(correo_local)
    credencial = db.scalar(
        select(TokenCredencial).where(
            TokenCredencial.token_hash == sha256(token.encode()).hexdigest()
        )
    )
    assert credencial is not None

    reutilizada = _restablecer(client, token, "ClaveSegura123!")

    assert reutilizada.status_code == 409
    assert reutilizada.json()["detail"] == {
        "codigo": "CONTRASENA_REUTILIZADA",
        "message": "La nueva contraseña debe ser diferente a la actual",
    }
    db.refresh(usuario)
    db.refresh(credencial)
    assert usuario.hash_contrasena == hash_original
    assert credencial.utilizado_en is None
    assert credencial.invalidado_en is None
    assert sesiones.obtener_por_token(token_sesion) is not None
    assert _validar(client, token).status_code == 200

    corregida = _restablecer(client, token, "NuevaClave456!")

    assert corregida.status_code == 200
    db.refresh(usuario)
    db.refresh(credencial)
    assert verificar_contrasena("NuevaClave456!", usuario.hash_contrasena)
    assert credencial.utilizado_en is not None
    assert sesiones.obtener_por_token(token_sesion) is None


def test_contrasena_debil_no_cambia_estado_y_conserva_token_y_sesion(
    db, client, correo_local, crear_usuario, sesiones
):
    usuario = crear_usuario(correo="debil-recovery@example.com")
    hash_original = usuario.hash_contrasena
    token_sesion = generar_token_sesion()
    sesiones.crear(
        usuario.id,
        token_sesion,
        datetime.now(UTC) + DURACION_SESION,
    )
    _solicitar(client, usuario.correo)
    token = _token_de_ultimo_correo(correo_local)
    credencial = db.scalar(
        select(TokenCredencial).where(
            TokenCredencial.token_hash == sha256(token.encode()).hexdigest()
        )
    )
    assert credencial is not None

    respuesta = _restablecer(client, token, "password")

    assert respuesta.status_code == 422
    db.refresh(usuario)
    db.refresh(credencial)
    assert usuario.hash_contrasena == hash_original
    assert credencial.utilizado_en is None
    assert credencial.invalidado_en is None
    assert sesiones.obtener_por_token(token_sesion) is not None
    assert _validar(client, token).status_code == 200


def test_token_reutilizado_falla_sin_nuevo_cambio(db, client, correo_local, crear_usuario):
    usuario = crear_usuario(correo="reutilizado-recovery@example.com")
    _solicitar(client, usuario.correo)
    token = _token_de_ultimo_correo(correo_local)
    assert _restablecer(client, token).status_code == 200

    repetido = _restablecer(client, token, "TerceraClave789!")

    assert repetido.status_code == 400
    assert repetido.json()["detail"]["codigo"] == "ENLACE_NO_DISPONIBLE"
    assert client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "TerceraClave789!"},
    ).status_code == 401


def test_token_expirado_falla_sin_consumirse(db, client, correo_local, crear_usuario):
    usuario = crear_usuario(correo="expirado-recovery@example.com")
    _solicitar(client, usuario.correo)
    token = _token_de_ultimo_correo(correo_local)
    credencial = db.scalar(
        select(TokenCredencial).where(
            TokenCredencial.token_hash == sha256(token.encode()).hexdigest()
        )
    )
    credencial.expira_en = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    respuesta = _restablecer(client, token)

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "ENLACE_EXPIRADO"
    db.refresh(credencial)
    assert credencial.utilizado_en is None


def test_token_invalidado_e_inexistente_fallan(client, correo_local, crear_usuario):
    usuario = crear_usuario(correo="invalidado-recovery@example.com")
    _solicitar(client, usuario.correo)
    anterior = _token_de_ultimo_correo(correo_local)
    _solicitar(client, usuario.correo)

    invalidado = _restablecer(client, anterior)
    inexistente = _restablecer(client, "token-inexistente")

    assert invalidado.status_code == 400
    assert invalidado.json()["detail"]["codigo"] == "ENLACE_NO_DISPONIBLE"
    assert inexistente.status_code == 400
    assert inexistente.json()["detail"]["codigo"] == "ENLACE_INVALIDO"


def test_passwords_diferentes_y_corta_son_rechazadas(client):
    diferentes = client.post(
        "/api/auth/restablecer-contrasena",
        json={
            "token": "cualquier-token",
            "nueva_contrasena": "NuevaClave456!",
            "confirmacion_contrasena": "OtraClave789!",
        },
    )
    corta = client.post(
        "/api/auth/restablecer-contrasena",
        json={
            "token": "cualquier-token",
            "nueva_contrasena": "corta",
            "confirmacion_contrasena": "corta",
        },
    )

    assert diferentes.status_code == 422
    assert corta.status_code == 422


def test_cuenta_desactivada_despues_de_emitir_token_es_rechazada(
    db, client, correo_local, crear_usuario
):
    usuario = crear_usuario(correo="desactivado-despues@example.com")
    hash_original = usuario.hash_contrasena
    _solicitar(client, usuario.correo)
    token = _token_de_ultimo_correo(correo_local)
    usuario.activo = False
    db.commit()

    respuesta = _restablecer(client, token)

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "ENLACE_NO_DISPONIBLE"
    db.refresh(usuario)
    assert usuario.activo is False
    assert usuario.hash_contrasena == hash_original
