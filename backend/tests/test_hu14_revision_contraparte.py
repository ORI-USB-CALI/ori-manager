"""HU-14: revisión externa de contraparte mediante invitación temporal."""

import base64
import importlib.util
import re
import struct
import zlib
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings
from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.security import hash_contrasena
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import (
    AlcanceConvenio,
    ContextoVersionConvenio,
    EstadoSolicitud,
    TipoSolicitante,
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
from backend.models.rol import Rol
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.models.version_convenio import VersionConvenio
from backend.schemas.convenio import ConvenioCrear, ConvenioElaboracionGuardar
from backend.services.contraparte_externa import (
    MAX_FIRMA_PNG_BYTES,
    DecisionContraparteInvalida,
    EnlaceContraparteError,
    ServicioContraparteExterna,
)
from backend.services.convenios import (
    ConflictoVersionConvenio,
    RevisionNoDisponible,
    ServicioConvenios,
)
from backend.services.correo import CorreoLocal, ErrorEnvioCorreo

FRONTEND_URL = "https://ori.example.com"


def _chunk_png(tipo: bytes, datos: bytes) -> bytes:
    crc = zlib.crc32(tipo)
    crc = zlib.crc32(datos, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", crc)


def _png_valido(ancho: int = 2, alto: int = 1) -> bytes:
    ihdr = struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0)
    filas = b"".join(b"\x00" + b"\x00\x00\x00\xff" * ancho for _ in range(alto))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk_png(b"IHDR", ihdr)
        + _chunk_png(b"IDAT", zlib.compress(filas))
        + _chunk_png(b"IEND", b"")
    )


def _data_url_png(contenido: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(contenido).decode()


FIRMA_PNG_BYTES = _png_valido()
FIRMA_PNG = _data_url_png(FIRMA_PNG_BYTES)


def _habilitar_contraparte(
    db, convenio, gestor, solicitante, revisor, crear_usuario,
    *, correo_contraparte="contacto.contraparte@example.com",
) -> VersionConvenio:
    solicitud = db.get(SolicitudConvenio, convenio.solicitud_id)
    solicitud.solicitante_id = solicitante.id
    solicitud.contacto_contraparte_correo = correo_contraparte
    db.commit()
    ServicioConvenios(db).finalizar_elaboracion(convenio.id, gestor)
    primera = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    ServicioConvenios(db).aprobar(
        convenio.id, primera.id, convenio.version_actual, revisor
    )
    segunda = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    ServicioConvenios(db).aprobar(
        convenio.id, segunda.id, convenio.version_actual, otro_revisor
    )
    db.refresh(convenio)
    return db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio.id,
            VersionConvenio.numero == convenio.version_actual,
        )
    )


def _servicio(db, correo):
    return ServicioConvenios(
        db,
        enviador=correo,
        frontend_url=FRONTEND_URL,
    )


def _token(correo_local) -> str:
    mensaje = correo_local.mensajes[-1]
    coincidencia = re.search(r"#token=([^\s<\"]+)", mensaje.texto)
    assert coincidencia is not None
    return coincidencia.group(1)


def _enviar(db, correo_local, convenio, gestor) -> tuple[RevisionConvenio, str]:
    revision = _servicio(db, correo_local).enviar_a_contraparte(
        convenio.id, convenio.version_actual, gestor
    )
    return revision, _token(correo_local)


def _contenido_corregido(contenido: dict) -> dict:
    nuevo = deepcopy(contenido)
    nuevo["content"].append(
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Corrección externa"}],
        }
    )
    return nuevo


def _crear_escenario_independiente(db_engine) -> dict:
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    correo = CorreoLocal()
    identificador = uuid4().hex
    with fabrica() as sesion:
        def crear_usuario_independiente(
            codigo_rol: CodigoRol, tipo_usuario: TipoUsuario = TipoUsuario.INTERNO
        ) -> Usuario:
            rol = sesion.scalar(select(Rol).where(Rol.codigo == codigo_rol.value))
            usuario = Usuario(
                correo=f"hu14-{uuid4().hex}@example.com",
                hash_contrasena=hash_contrasena("ClaveSegura123!"),
                nombre_completo="Usuario concurrencia HU-14",
                rol=rol,
                tipo_usuario=tipo_usuario.value,
                activo=True,
                correo_verificado_en=datetime.now(UTC),
            )
            sesion.add(usuario)
            sesion.commit()
            return usuario

        gestor = crear_usuario_independiente(CodigoRol.GESTOR_ORI)
        solicitante = crear_usuario_independiente(CodigoRol.SOLICITANTE_INTERNO)
        revisor = crear_usuario_independiente(CodigoRol.REVISOR_ORI)
        solicitud = SolicitudConvenio(
            consecutivo=f"H14-{identificador}",
            tipo_solicitante=TipoSolicitante.INTERNO.value,
            solicitante_id=solicitante.id,
            objeto="Solicitud para concurrencia HU-14",
            justificacion="Validar decisiones concurrentes",
            vigencia_estimada="24 meses",
            estado=EstadoSolicitud.APROBADA.value,
            nombre_aliado_propuesto="Universidad Contraparte",
            correo_aliado_propuesto="convenios@contraparte.example",
            contacto_contraparte_correo="contacto.contraparte@example.com",
        )
        sesion.add(solicitud)
        sesion.commit()
        tipo = sesion.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
        convenio = ServicioConvenios(sesion).crear(
            ConvenioCrear(
                solicitud_id=solicitud.id,
                objeto="Convenio para concurrencia HU-14",
                alcance=AlcanceConvenio.INSTITUCIONAL,
                tipo_convenio_id=tipo.id,
                implicacion_financiera="Sin costo",
                duracion_meses=24,
                fecha_inicio=date(2026, 1, 1),
                fecha_vencimiento=date(2028, 1, 1),
            ),
            gestor,
        )
        _habilitar_contraparte(
            sesion,
            convenio,
            gestor,
            solicitante,
            revisor,
            crear_usuario_independiente,
        )
        revision, token = _enviar(sesion, correo, convenio, gestor)
        ids_usuario = list(
            sesion.scalars(
                select(Usuario.id).where(Usuario.correo.like("hu14-%@example.com"))
            )
        )
        return {
            "convenio_id": convenio.id,
            "solicitud_id": solicitud.id,
            "revision_id": revision.id,
            "invitacion_id": revision.invitaciones_contraparte[0].id,
            "gestor_id": gestor.id,
            "usuario_ids": ids_usuario,
            "token": token,
        }


def _limpiar_escenario_independiente(db_engine, escenario: dict) -> None:
    fabrica = sessionmaker(bind=db_engine)
    with fabrica() as sesion:
        convenio_id = escenario["convenio_id"]
        revision_ids = select(RevisionConvenio.id).where(
            RevisionConvenio.convenio_id == convenio_id
        )
        sesion.execute(
            delete(ObservacionRevision).where(
                ObservacionRevision.convenio_id == convenio_id
            )
        )
        sesion.execute(
            delete(RespuestaRevisionContraparte).where(
                RespuestaRevisionContraparte.revision_convenio_id.in_(revision_ids)
            )
        )
        sesion.execute(
            delete(InvitacionRevisionContraparte).where(
                InvitacionRevisionContraparte.revision_convenio_id.in_(revision_ids)
            )
        )
        sesion.execute(
            delete(RevisionConvenio).where(
                RevisionConvenio.convenio_id == convenio_id
            )
        )
        sesion.execute(
            delete(HistorialEtapa).where(HistorialEtapa.convenio_id == convenio_id)
        )
        sesion.execute(
            delete(VersionConvenio).where(VersionConvenio.convenio_id == convenio_id)
        )
        sesion.execute(
            delete(Documento).where(
                (Documento.convenio_id == convenio_id)
                | (Documento.solicitud_id == escenario["solicitud_id"])
            )
        )
        sesion.execute(
            delete(Auditoria).where(
                Auditoria.usuario_id.in_(escenario["usuario_ids"])
            )
        )
        sesion.execute(delete(Convenio).where(Convenio.id == convenio_id))
        sesion.execute(
            delete(SolicitudConvenio).where(
                SolicitudConvenio.id == escenario["solicitud_id"]
            )
        )
        sesion.execute(
            delete(Usuario).where(Usuario.id.in_(escenario["usuario_ids"]))
        )
        sesion.commit()


def test_envio_externo_guarda_to_cc_hash_expiracion_y_version(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    version = _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    antes = datetime.now(UTC)

    revision, token = _enviar(db, correo_local, convenio_listo, gestor)

    invitacion = db.scalar(
        select(InvitacionRevisionContraparte).where(
            InvitacionRevisionContraparte.revision_convenio_id == revision.id
        )
    )
    assert revision.responsable_id is None
    assert revision.creada_por_id == gestor.id
    assert revision.version_convenio_id == version.id
    assert invitacion.correo_destino == "contacto.contraparte@example.com"
    assert invitacion.correo_cc == solicitante.correo
    assert invitacion.generada_por_id == gestor.id
    assert correo_local.mensajes[-1].destinatario == invitacion.correo_destino
    assert correo_local.mensajes[-1].cc == (solicitante.correo,)
    assert invitacion.token_hash == sha256(token.encode()).hexdigest()
    assert token not in invitacion.token_hash
    assert antes + timedelta(minutes=59) <= invitacion.expira_en
    assert invitacion.expira_en <= antes + timedelta(minutes=61)
    assert invitacion.enviado_en is not None
    mensaje = correo_local.mensajes[-1]
    identificador = f"#{convenio_listo.id}"
    assert mensaje.asunto == (
        f"Revisión de contraparte - elaboración de convenio {identificador}"
    )
    assert (
        "La ORI de la Universidad de San Buenaventura Cali solicita revisar la elaboración "
        f"de convenio {identificador}."
    ) in mensaje.texto
    assert "<h1>Revisión de elaboración de convenio</h1>" in mensaje.html
    assert (
        f"<p>La ORI solicita revisar la elaboración de convenio {identificador}.</p>"
        in mensaje.html
    )
    assert ">Revisar elaboración de convenio</a>" in mensaje.html
    assert f"{FRONTEND_URL}/revision-contraparte#token=" in mensaje.texto


def test_envio_deduplica_to_cc_case_insensitive(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    solicitante.correo = "Misma.Persona@example.com"
    db.commit()
    _habilitar_contraparte(
        db,
        convenio_listo,
        gestor,
        solicitante,
        revisor,
        crear_usuario,
        correo_contraparte="misma.persona@EXAMPLE.com",
    )

    revision, _ = _enviar(db, correo_local, convenio_listo, gestor)
    invitacion = revision.invitaciones_contraparte[0]

    assert invitacion.correo_cc is None
    assert correo_local.mensajes[-1].cc == ()


def test_correo_escapa_identificador_dinamico_y_conserva_enlace(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    convenio_listo.codigo = "<script>alert(1)</script>"
    db.commit()
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )

    _enviar(db, correo_local, convenio_listo, gestor)

    mensaje = correo_local.mensajes[-1]
    assert "<script>alert(1)</script>" not in mensaje.html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in mensaje.html
    assert f'{FRONTEND_URL}/revision-contraparte#token=' in mensaje.html


def test_envio_y_reenvio_autenticados_exigen_permiso_de_gestion(
    client,
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    entrar_como,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "public_frontend_url", FRONTEND_URL)
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    ruta_envio = f"/api/convenios/{convenio_listo.id}/revision-contraparte/enviar"
    payload = {"expected_version": convenio_listo.version_actual}
    entrar_como(solicitante)
    assert client.post(ruta_envio, json=payload).status_code == 403
    entrar_como(gestor)
    enviada = client.post(ruta_envio, json=payload)
    assert enviada.status_code == 201
    assert enviada.json()["responsable"] is None
    revision_id = enviada.json()["id"]
    ruta_reenvio = (
        f"/api/convenios/{convenio_listo.id}/revisiones/{revision_id}"
        "/contraparte/reenviar"
    )
    entrar_como(solicitante)
    assert client.post(ruta_reenvio).status_code == 403
    entrar_como(gestor)
    reenviada = client.post(ruta_reenvio)
    assert reenviada.status_code == 201
    assert reenviada.json()["revision_convenio_id"] == revision_id
    assert len(correo_local.mensajes) == 2


def test_envio_rechaza_correo_ausente_version_y_doble_aval_invalidos(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    _habilitar_contraparte(
        db,
        convenio_listo,
        gestor,
        solicitante,
        revisor,
        crear_usuario,
        correo_contraparte=None,
    )
    with pytest.raises(RevisionNoDisponible, match="correos válidos"):
        _servicio(db, correo_local).enviar_a_contraparte(
            convenio_listo.id, convenio_listo.version_actual, gestor
        )

    solicitud = db.get(SolicitudConvenio, convenio_listo.solicitud_id)
    solicitud.contacto_contraparte_correo = "externo@example.com"
    segunda = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.instancia_juridica == 2,
        )
    )
    primera = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.instancia_juridica == 1,
        )
    )
    ronda_primera = primera.numero_ronda
    primera.numero_ronda = segunda.numero_ronda + 1
    db.commit()
    with pytest.raises(RevisionNoDisponible, match="dos aprobaciones"):
        _servicio(db, correo_local).enviar_a_contraparte(
            convenio_listo.id, convenio_listo.version_actual, gestor
        )
    primera.numero_ronda = ronda_primera
    version_resultado = segunda.version_resultado_id
    segunda.version_resultado_id = None
    db.commit()
    with pytest.raises(RevisionNoDisponible):
        _servicio(db, correo_local).enviar_a_contraparte(
            convenio_listo.id, convenio_listo.version_actual, gestor
        )
    segunda.version_resultado_id = version_resultado
    db.commit()
    with pytest.raises(ConflictoVersionConvenio, match="versión"):
        _servicio(db, correo_local).enviar_a_contraparte(
            convenio_listo.id, convenio_listo.version_actual - 1, gestor
        )


def test_acceso_publico_es_minimo_y_no_consume_token(
    client,
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    version = _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision, token = _enviar(db, correo_local, convenio_listo, gestor)
    client.cookies.clear()

    respuesta = client.post(
        "/api/public/revision-contraparte/acceso", json={"token": token}
    )

    assert respuesta.status_code == 200
    assert set(respuesta.json()) == {
        "codigo_convenio",
        "objeto",
        "contraparte",
        "version_numero",
        "contenido",
        "estado",
        "expira_en",
        "correo_destino",
    }
    assert respuesta.json()["version_numero"] == version.numero
    assert respuesta.json()["contenido"] == version.contenido
    invitacion = revision.invitaciones_contraparte[0]
    db.refresh(invitacion)
    assert invitacion.utilizado_en is None


@pytest.mark.parametrize(
    ("cambio", "codigo"),
    [
        ("expirada", "ENLACE_EXPIRADO"),
        ("revocada", "ENLACE_NO_DISPONIBLE"),
        ("utilizada", "ENLACE_NO_DISPONIBLE"),
    ],
)
def test_acceso_rechaza_invitacion_no_disponible(
    cambio,
    codigo,
    client,
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision, token = _enviar(db, correo_local, convenio_listo, gestor)
    invitacion = revision.invitaciones_contraparte[0]
    if cambio == "expirada":
        invitacion.expira_en = datetime.now(UTC) - timedelta(seconds=1)
    elif cambio == "revocada":
        invitacion.revocado_en = datetime.now(UTC)
    else:
        invitacion.utilizado_en = datetime.now(UTC)
    db.commit()

    respuesta = client.post(
        "/api/public/revision-contraparte/acceso", json={"token": token}
    )
    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == codigo


def test_acceso_token_inexistente_es_invalido(client) -> None:
    respuesta = client.post(
        "/api/public/revision-contraparte/acceso",
        json={"token": "x" * 48},
    )
    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "ENLACE_INVALIDO"


def test_firma_png_real_valida_y_calcula_hash_sobre_bytes() -> None:
    contenido, firma_hash = ServicioContraparteExterna.decodificar_firma(FIRMA_PNG)

    assert contenido == FIRMA_PNG_BYTES
    assert firma_hash == sha256(FIRMA_PNG_BYTES).hexdigest()


def test_firma_png_rechaza_base64_invalido() -> None:
    with pytest.raises(DecisionContraparteInvalida):
        ServicioContraparteExterna.decodificar_firma(
            "data:image/png;base64,esto-no-es-base64%%%"
        )


@pytest.mark.parametrize(
    "contenido",
    [
        b"\x89PNG\r\n\x1a\n",
        b"\x89PNG\r\n\x1a\nbasura",
        FIRMA_PNG_BYTES[:-3],
        FIRMA_PNG_BYTES[:-12],
        (
            b"\x89PNG\r\n\x1a\n"
            + _chunk_png(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
            + _chunk_png(b"IEND", b"")
        ),
        FIRMA_PNG_BYTES + b"basura",
    ],
    ids=[
        "solo-signature",
        "signature-basura",
        "truncado",
        "sin-iend",
        "sin-idat",
        "bytes-despues-iend",
    ],
)
def test_firma_png_rechaza_estructura_incompleta(contenido) -> None:
    with pytest.raises(DecisionContraparteInvalida):
        ServicioContraparteExterna.decodificar_firma(_data_url_png(contenido))


def test_firma_png_rechaza_crc_incorrecto() -> None:
    contenido = bytearray(FIRMA_PNG_BYTES)
    posicion_idat = contenido.index(b"IDAT")
    longitud = struct.unpack(">I", contenido[posicion_idat - 4 : posicion_idat])[0]
    posicion_crc = posicion_idat + 4 + longitud
    contenido[posicion_crc] ^= 0xFF

    with pytest.raises(DecisionContraparteInvalida, match="CRC"):
        ServicioContraparteExterna.decodificar_firma(_data_url_png(bytes(contenido)))


def test_firma_png_rechaza_mas_de_un_mibibyte_decodificado() -> None:
    with pytest.raises(DecisionContraparteInvalida):
        ServicioContraparteExterna.decodificar_firma(
            _data_url_png(b"\x89PNG\r\n\x1a\n" + b"x" * MAX_FIRMA_PNG_BYTES)
        )


def test_aprobacion_publica_exige_firma_guarda_evidencia_y_rechaza_replay(
    client,
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    version = _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision, token = _enviar(db, correo_local, convenio_listo, gestor)
    ruta = "/api/public/revision-contraparte/aprobar"
    base = {
        "token": token,
        "nombre_firmante": "Representante Externo",
        "cargo_firmante": "Rector",
    }
    assert client.post(
        ruta, json={**base, "nombre_firmante": "", "firma": FIRMA_PNG}
    ).status_code == 422
    assert client.post(
        ruta, json={**base, "cargo_firmante": "", "firma": FIRMA_PNG}
    ).status_code == 422
    assert client.post(ruta, json=base).status_code == 422
    assert client.post(ruta, json={**base, "firma": "invalida"}).status_code == 422
    firma_grande = "data:image/png;base64," + base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + b"x" * MAX_FIRMA_PNG_BYTES
    ).decode()
    assert client.post(ruta, json={**base, "firma": firma_grande}).status_code == 422

    respuesta = client.post(ruta, json={**base, "firma": FIRMA_PNG})

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "RESUELTA", "resultado": "APROBADA"}
    db.refresh(revision)
    db.refresh(convenio_listo)
    assert revision.resuelta_por_id is None
    assert revision.version_resultado_id == version.id
    assert convenio_listo.etapa_actual.codigo == "REVISION_FINAL"
    assert convenio_listo.estado == "EN_TRAMITE"
    evidencia = db.scalar(
        select(RespuestaRevisionContraparte).where(
            RespuestaRevisionContraparte.revision_convenio_id == revision.id
        )
    )
    assert evidencia.correo_actor == "contacto.contraparte@example.com"
    assert evidencia.firma_png.startswith(b"\x89PNG")
    assert evidencia.firma_sha256 == sha256(evidencia.firma_png).hexdigest()
    assert revision.invitaciones_contraparte[0].utilizado_en is not None
    replay = client.post(ruta, json={**base, "firma": FIRMA_PNG})
    assert replay.status_code == 400
    assert replay.json()["detail"]["codigo"] == "ENLACE_NO_DISPONIBLE"


def test_historial_expone_metadata_sin_firma_ni_secretos(
    client,
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision, token = _enviar(db, correo_local, convenio_listo, gestor)
    ServicioContraparteExterna(db).aprobar(
        token, "Representante Externo", "Rector", FIRMA_PNG
    )

    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revisiones")

    assert respuesta.status_code == 200
    ciclo = next(item for item in respuesta.json()["revisiones"] if item["id"] == revision.id)
    evidencia = ciclo["respuesta_contraparte"]
    assert evidencia == {
        "nombre_firmante": "Representante Externo",
        "cargo_firmante": "Rector",
        "correo_actor": "contacto.contraparte@example.com",
        "firma_sha256": sha256(FIRMA_PNG_BYTES).hexdigest(),
        "creado_en": evidencia["creado_en"],
        "tiene_firma": True,
    }
    invitacion = ciclo["invitaciones_contraparte"][0]
    assert invitacion["generada_por"]["id"] == gestor.id
    serializado = respuesta.text
    assert "firma_png" not in serializado
    assert "token_hash" not in serializado
    assert token not in serializado


def test_devolucion_externa_no_falsifica_usuario_y_regresa_a_elaboracion(
    client,
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    version = _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision, token = _enviar(db, correo_local, convenio_listo, gestor)
    ruta = "/api/public/revision-contraparte/devolver"
    base = {
        "token": token,
        "nombre_firmante": "Delegada Externa",
        "cargo_firmante": "Directora jurídica",
    }
    assert client.post(ruta, json={**base, "observaciones": []}).status_code == 422

    respuesta = client.post(
        ruta,
        json={**base, "observaciones": [" Ajustar alcance ", "Precisar vigencia"]},
    )

    assert respuesta.status_code == 200
    db.refresh(revision)
    db.refresh(convenio_listo)
    assert revision.resultado == "DEVUELTA"
    assert revision.resuelta_por_id is None
    assert revision.version_resultado_id == version.id
    assert convenio_listo.etapa_actual.codigo == "ELABORACION"
    observaciones = list(
        db.scalars(
            select(ObservacionRevision).where(
                ObservacionRevision.revision_convenio_id == revision.id
            )
        )
    )
    assert [item.descripcion for item in observaciones] == [
        "Ajustar alcance",
        "Precisar vigencia",
    ]
    assert all(item.registrada_por_id is None for item in observaciones)
    assert all(item.responsable_id == gestor.id for item in observaciones)
    evidencia = db.scalar(
        select(RespuestaRevisionContraparte).where(
            RespuestaRevisionContraparte.revision_convenio_id == revision.id
        )
    )
    assert evidencia.nombre_firmante == "Delegada Externa"
    assert evidencia.firma_png is None


def test_constraint_actor_observacion_solo_permite_null_para_contraparte(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision, _ = _enviar(db, correo_local, convenio_listo, gestor)
    juridica_sin_actor = ObservacionRevision(
        convenio_id=convenio_listo.id,
        historial_etapa_id=revision.historial_etapa_id,
        revision_convenio_id=revision.id,
        origen="REVISOR_ORI",
        registrada_por_id=None,
        responsable_id=gestor.id,
        descripcion="No debe persistir",
        estado="PENDIENTE",
    )
    db.add(juridica_sin_actor)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()

    contraparte_sin_actor = ObservacionRevision(
        convenio_id=convenio_listo.id,
        historial_etapa_id=revision.historial_etapa_id,
        revision_convenio_id=revision.id,
        origen="CONTRAPARTE",
        registrada_por_id=None,
        responsable_id=gestor.id,
        descripcion="Actor externo permitido",
        estado="PENDIENTE",
    )
    db.add(contraparte_sin_actor)
    db.commit()
    assert contraparte_sin_actor.id is not None


def test_devolucion_conserva_reentrada_rj1_rj2_y_nuevo_ciclo(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    primera, token = _enviar(db, correo_local, convenio_listo, gestor)
    ServicioContraparteExterna(db).devolver(
        token, "Actor externo", "Representante", ["Corregir alcance"]
    )
    observacion = db.scalar(
        select(ObservacionRevision).where(
            ObservacionRevision.revision_convenio_id == primera.id
        )
    )
    ServicioConvenios(db).atender_observacion(
        convenio_listo.id, observacion.id, "Corregido", gestor
    )
    with pytest.raises(RevisionNoDisponible):
        ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    elaboracion = ServicioConvenios(db).obtener_para_elaboracion(convenio_listo.id)
    guardada = ServicioConvenios(db).guardar_elaboracion(
        convenio_listo.id,
        ConvenioElaboracionGuardar(
            contenido=_contenido_corregido(elaboracion.contenido),
            expected_version=elaboracion.version_actual,
        ),
        gestor,
    )
    assert guardada.version_actual > primera.version_convenio.numero
    assert db.scalar(
        select(VersionConvenio.contexto).where(
            VersionConvenio.convenio_id == convenio_listo.id,
            VersionConvenio.numero == guardada.version_actual,
        )
    ) == ContextoVersionConvenio.GUARDADO.value
    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    nueva_rj1 = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    ServicioConvenios(db).aprobar(
        convenio_listo.id, nueva_rj1.id, convenio_listo.version_actual, revisor
    )
    nueva_rj2 = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    tercer_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    ServicioConvenios(db).aprobar(
        convenio_listo.id, nueva_rj2.id, convenio_listo.version_actual, tercer_revisor
    )
    segunda, _ = _enviar(db, correo_local, convenio_listo, gestor)
    assert segunda.id != primera.id
    assert db.scalar(
        select(func.count()).select_from(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.tipo == "CONTRAPARTE",
        )
    ) == 2


def test_reenvio_revoca_anterior_y_conserva_revision_y_version(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision, token_anterior = _enviar(db, correo_local, convenio_listo, gestor)
    version_id = revision.version_convenio_id
    nuevo_generador = crear_usuario(
        CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO
    )

    nueva = _servicio(db, correo_local).reenviar_invitacion_contraparte(
        convenio_listo.id, revision.id, nuevo_generador
    )
    token_nuevo = _token(correo_local)

    invitaciones = list(
        db.scalars(
            select(InvitacionRevisionContraparte)
            .where(
                InvitacionRevisionContraparte.revision_convenio_id == revision.id
            )
            .order_by(InvitacionRevisionContraparte.id)
        )
    )
    assert len(invitaciones) == 2
    assert invitaciones[0].revocado_en is not None
    assert invitaciones[0].generada_por_id == gestor.id
    assert nueva.id == invitaciones[1].id
    assert nueva.generada_por_id == nuevo_generador.id
    assert token_nuevo != token_anterior
    assert revision.version_convenio_id == version_id
    assert revision.estado == "PENDIENTE"
    with pytest.raises(EnlaceContraparteError, match="ENLACE_NO_DISPONIBLE"):
        ServicioContraparteExterna(db).acceder(token_anterior)


def test_fallo_correo_conserva_ciclo_y_permite_reenvio(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    class CorreoFallido:
        def enviar(self, mensaje) -> None:
            raise ErrorEnvioCorreo("fallo controlado")

    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    with pytest.raises(ErrorEnvioCorreo):
        _servicio(db, CorreoFallido()).enviar_a_contraparte(
            convenio_listo.id, convenio_listo.version_actual, gestor
        )
    revision = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.tipo == "CONTRAPARTE",
        )
    )
    assert revision is not None and revision.estado == "PENDIENTE"
    anterior = revision.invitaciones_contraparte[0]
    assert anterior.enviado_en is None

    nueva = _servicio(db, correo_local).reenviar_invitacion_contraparte(
        convenio_listo.id, revision.id, gestor
    )
    assert nueva.enviado_en is not None
    assert anterior.revocado_en is not None


def test_fallo_brevo_en_reenvio_persiste_invitacion_y_permite_otro_intento(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
) -> None:
    class CorreoFallido:
        def __init__(self) -> None:
            self.mensaje = None

        def enviar(self, mensaje) -> None:
            self.mensaje = mensaje
            raise ErrorEnvioCorreo("fallo controlado")

    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision, _ = _enviar(db, correo_local, convenio_listo, gestor)
    version_id = revision.version_convenio_id
    correo_fallido = CorreoFallido()

    with pytest.raises(ErrorEnvioCorreo):
        _servicio(db, correo_fallido).reenviar_invitacion_contraparte(
            convenio_listo.id, revision.id, gestor
        )

    invitaciones = list(
        db.scalars(
            select(InvitacionRevisionContraparte)
            .where(InvitacionRevisionContraparte.revision_convenio_id == revision.id)
            .order_by(InvitacionRevisionContraparte.id)
        )
    )
    token_fallido = re.search(r"#token=([^\s<\"]+)", correo_fallido.mensaje.texto).group(1)
    assert len(invitaciones) == 2
    assert invitaciones[0].revocado_en is not None
    assert invitaciones[1].enviado_en is None
    assert invitaciones[1].revocado_en is None
    assert invitaciones[1].token_hash == sha256(token_fallido.encode()).hexdigest()
    assert token_fallido not in invitaciones[1].token_hash
    assert revision.estado == "PENDIENTE"
    assert revision.version_convenio_id == version_id

    recuperada = _servicio(db, correo_local).reenviar_invitacion_contraparte(
        convenio_listo.id, revision.id, gestor
    )
    assert recuperada.enviado_en is not None
    assert invitaciones[1].revocado_en is not None
    assert db.scalar(
        select(func.count()).select_from(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.tipo == "CONTRAPARTE",
        )
    ) == 1


def test_endpoint_recupera_ciclo_persistido_despues_de_502(
    client,
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    monkeypatch,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    envio_real = correo_local.enviar

    def fallar_envio(_mensaje) -> None:
        raise ErrorEnvioCorreo("fallo controlado")

    monkeypatch.setattr(correo_local, "enviar", fallar_envio)
    ruta_envio = f"/api/convenios/{convenio_listo.id}/revision-contraparte/enviar"
    payload = {"expected_version": convenio_listo.version_actual}
    assert client.post(ruta_envio, json=payload).status_code == 502
    assert client.post(ruta_envio, json=payload).status_code == 409
    assert db.scalar(
        select(func.count()).select_from(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.tipo == "CONTRAPARTE",
        )
    ) == 1

    historial = client.get(f"/api/convenios/{convenio_listo.id}/revisiones")
    assert historial.status_code == 200
    ciclo = next(
        item for item in historial.json()["revisiones"] if item["tipo"] == "CONTRAPARTE"
    )
    assert ciclo["estado"] == "PENDIENTE"
    assert len(ciclo["invitaciones_contraparte"]) == 1
    assert ciclo["invitaciones_contraparte"][0]["enviado_en"] is None

    monkeypatch.setattr(correo_local, "enviar", envio_real)
    reenvio = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{ciclo['id']}"
        "/contraparte/reenviar"
    )
    assert reenvio.status_code == 201
    assert reenvio.json()["revision_convenio_id"] == ciclo["id"]


def test_endpoints_autenticados_del_solicitante_fueron_retirados(
    client, solicitante, entrar_como
) -> None:
    entrar_como(solicitante)
    assert client.get(
        "/api/convenios/revisiones-contraparte/pendientes"
    ).status_code == 404


class _ErrorPostgresSimulado(Exception):
    def __init__(self, constraint_name: str) -> None:
        self.diag = SimpleNamespace(constraint_name=constraint_name)


def test_indice_parcial_sigue_convirtiendo_solo_su_integrity_error(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    monkeypatch,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    error = IntegrityError(
        "INSERT revision_convenio",
        {},
        _ErrorPostgresSimulado("uq_revision_convenio_contraparte_pendiente"),
    )
    flush_real = db.flush

    def fallar_flush(*args, **kwargs) -> None:
        if any(
            isinstance(item, RevisionConvenio)
            and item.tipo == "CONTRAPARTE"
            and item.id is None
            for item in db.new
        ):
            raise error
        flush_real(*args, **kwargs)

    monkeypatch.setattr(db, "flush", fallar_flush)
    with pytest.raises(RevisionNoDisponible, match="Ya existe una revisión"):
        _servicio(db, correo_local).enviar_a_contraparte(
            convenio_listo.id, convenio_listo.version_actual, gestor
        )


def test_decision_atomica_revierte_todas_las_escrituras(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    monkeypatch,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision, token = _enviar(db, correo_local, convenio_listo, gestor)
    commit_real = db.commit

    def fallar_commit() -> None:
        db.flush()
        raise SQLAlchemyError("fallo controlado")

    monkeypatch.setattr(db, "commit", fallar_commit)
    with pytest.raises(SQLAlchemyError):
        ServicioContraparteExterna(db).devolver(
            token, "Actor", "Cargo", ["Primera", "Segunda"]
        )
    monkeypatch.setattr(db, "commit", commit_real)
    db.expire_all()
    persistida = db.get(RevisionConvenio, revision.id)
    assert persistida.estado == "PENDIENTE"
    assert persistida.resultado is None
    assert persistida.resuelta_en is None
    assert persistida.resuelta_por_id is None
    assert not persistida.observaciones
    assert persistida.respuesta_contraparte is None
    assert persistida.invitaciones_contraparte[0].utilizado_en is None
    db.refresh(convenio_listo)
    assert convenio_listo.etapa_actual.codigo == "REVISION_CONTRAPARTE"


def test_aprobacion_atomica_revierte_firma_y_transicion(
    db,
    correo_local,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    monkeypatch,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision, token = _enviar(db, correo_local, convenio_listo, gestor)
    commit_real = db.commit

    def fallar_commit() -> None:
        db.flush()
        raise SQLAlchemyError("fallo controlado")

    monkeypatch.setattr(db, "commit", fallar_commit)
    with pytest.raises(SQLAlchemyError):
        ServicioContraparteExterna(db).aprobar(
            token, "Actor", "Cargo", FIRMA_PNG
        )
    monkeypatch.setattr(db, "commit", commit_real)
    db.expire_all()

    persistida = db.get(RevisionConvenio, revision.id)
    assert persistida.estado == "PENDIENTE"
    assert persistida.resultado is None
    assert persistida.resuelta_en is None
    assert persistida.respuesta_contraparte is None
    assert persistida.invitaciones_contraparte[0].utilizado_en is None
    db.refresh(convenio_listo)
    assert convenio_listo.etapa_actual.codigo == "REVISION_CONTRAPARTE"
    assert db.scalar(
        select(func.count())
        .select_from(HistorialEtapa)
        .join(Etapa, HistorialEtapa.etapa_destino_id == Etapa.id)
        .where(
            HistorialEtapa.convenio_id == convenio_listo.id,
            Etapa.codigo == "REVISION_FINAL",
        )
    ) == 0


def test_token_stale_no_decide_despues_de_reenvio_en_otra_sesion(db_engine) -> None:
    escenario = _crear_escenario_independiente(db_engine)
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    sesion_a = fabrica()
    try:
        invitacion_stale = sesion_a.get(
            InvitacionRevisionContraparte, escenario["invitacion_id"]
        )
        assert invitacion_stale.revocado_en is None

        with fabrica() as sesion_b:
            gestor_b = sesion_b.get(Usuario, escenario["gestor_id"])
            ServicioConvenios(
                sesion_b,
                enviador=CorreoLocal(),
                frontend_url=FRONTEND_URL,
            ).reenviar_invitacion_contraparte(
                escenario["convenio_id"],
                escenario["revision_id"],
                gestor_b,
            )

        # Demuestra la precondición de la regresión: la sesión A conserva el
        # objeto viejo en su identity map, pero el servicio debe recargarlo.
        assert invitacion_stale.revocado_en is None
        with pytest.raises(EnlaceContraparteError, match="ENLACE_NO_DISPONIBLE"):
            ServicioContraparteExterna(sesion_a).aprobar(
                escenario["token"], "Actor", "Cargo", FIRMA_PNG
            )
        sesion_a.rollback()
        revision = sesion_a.get(RevisionConvenio, escenario["revision_id"])
        sesion_a.refresh(revision)
        assert revision.estado == "PENDIENTE"
        assert revision.respuesta_contraparte is None
    finally:
        sesion_a.close()
        _limpiar_escenario_independiente(db_engine, escenario)


@pytest.mark.parametrize(
    ("primera_accion", "segunda_accion"),
    [
        ("aprobar", "aprobar"),
        ("devolver", "devolver"),
        ("aprobar", "devolver"),
    ],
)
def test_decisiones_concurrentes_solo_permiten_un_resultado(
    db_engine, primera_accion, segunda_accion
) -> None:
    escenario = _crear_escenario_independiente(db_engine)
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    barrera = Barrier(2)

    def decidir(accion: str) -> tuple[str, str]:
        with fabrica() as sesion:
            barrera.wait(timeout=10)
            try:
                servicio = ServicioContraparteExterna(sesion)
                if accion == "aprobar":
                    servicio.aprobar(
                        escenario["token"], "Actor", "Cargo", FIRMA_PNG
                    )
                else:
                    servicio.devolver(
                        escenario["token"], "Actor", "Cargo", ["Corrección"]
                    )
                return "ok", accion
            except EnlaceContraparteError as exc:
                return "rechazada", exc.codigo

    try:
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(
                ejecutor.map(decidir, [primera_accion, segunda_accion])
            )
        assert [estado for estado, _ in resultados].count("ok") == 1
        assert [estado for estado, _ in resultados].count("rechazada") == 1

        with fabrica() as verificacion:
            revision = verificacion.get(RevisionConvenio, escenario["revision_id"])
            convenio = verificacion.get(Convenio, escenario["convenio_id"])
            assert revision.estado == "RESUELTA"
            assert revision.resultado in {"APROBADA", "DEVUELTA"}
            assert db_engine.dialect.name == "postgresql"
            assert verificacion.scalar(
                select(func.count())
                .select_from(RespuestaRevisionContraparte)
                .where(
                    RespuestaRevisionContraparte.revision_convenio_id
                    == revision.id
                )
            ) == 1
            transiciones = verificacion.scalar(
                select(func.count())
                .select_from(HistorialEtapa)
                .where(
                    HistorialEtapa.convenio_id == convenio.id,
                    HistorialEtapa.observacion.in_(
                        [
                            "Aprobación externa de la contraparte",
                            "Devolución externa de revisión de contraparte",
                        ]
                    ),
                )
            )
            assert transiciones == 1
            observaciones = verificacion.scalar(
                select(func.count())
                .select_from(ObservacionRevision)
                .where(ObservacionRevision.revision_convenio_id == revision.id)
            )
            if revision.resultado == "APROBADA":
                assert convenio.etapa_actual.codigo == "REVISION_FINAL"
                assert observaciones == 0
            else:
                assert convenio.etapa_actual.codigo == "ELABORACION"
                assert observaciones == 1
    finally:
        _limpiar_escenario_independiente(db_engine, escenario)


def test_downgrade_rechaza_antes_de_ddl_si_hay_actor_externo(monkeypatch) -> None:
    ruta = (
        Path(__file__).parents[1]
        / "migrations/versions/d9e1f3a5b7c2_hu14_hardening_revision_externa.py"
    )
    spec = importlib.util.spec_from_file_location("migracion_hu14_hardening", ruta)
    assert spec is not None and spec.loader is not None
    migracion = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migracion)

    class Resultado:
        @staticmethod
        def scalar_one() -> int:
            return 1

    class Conexion:
        @staticmethod
        def execute(_consulta):
            return Resultado()

    monkeypatch.setattr(migracion.op, "get_bind", lambda: Conexion())

    def ddl_no_permitido(*_args, **_kwargs) -> None:
        pytest.fail("El downgrade intentó DDL antes de validar la pérdida de datos")

    monkeypatch.setattr(migracion.op, "drop_index", ddl_no_permitido)
    monkeypatch.setattr(migracion.op, "drop_constraint", ddl_no_permitido)
    monkeypatch.setattr(migracion.op, "drop_column", ddl_no_permitido)

    with pytest.raises(RuntimeError, match="sin perder o falsificar datos"):
        migracion.downgrade()
