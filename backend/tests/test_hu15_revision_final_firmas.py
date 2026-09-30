import base64
import struct
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.security import hash_contrasena
from backend.main import app
from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import (
    ContextoVersionConvenio,
    EstadoConvenio,
    EstadoFirmaConvenio,
    EstadoProcesoFirmasConvenio,
    EstadoRevisionConvenio,
    EstadoSolicitud,
    ModalidadFirma,
    OrigenObservacionRevision,
    ResultadoRevisionConvenio,
    RolFirmanteConvenio,
    TipoAliado,
    TipoIdentificacion,
    TipoRevisionConvenio,
    TipoSolicitante,
)
from backend.models.etapa import Etapa
from backend.models.firma_convenio import FirmaConvenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.invitacion_firma_convenio import InvitacionFirmaConvenio
from backend.models.observacion_revision import ObservacionRevision
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.revision_convenio import RevisionConvenio
from backend.models.rol import Rol
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.usuario import Usuario
from backend.models.version_convenio import VersionConvenio
from backend.services.convenios import RevisionNoDisponible
from backend.services.correo import CorreoLocal, ErrorEnvioCorreo, get_enviador_correo
from backend.services.firma_electronica import (
    EnlaceFirmaConvenioError,
    ServicioFirmaElectronica,
)
from backend.services.firma_png import MAX_FIRMA_PNG_BYTES
from backend.services.firmas import ServicioFirmas

ROLES_ESPERADOS = [
    "ADMINISTRADOR_ORI",
    "REVISOR_ORI",
    "VICERRECTORIA_FINANCIERA",
    "VICERRECTORIA_ACADEMICA",
    "SECRETARIA",
    "RECTOR",
    "PARTE_SOLICITANTE",
]
FRONTEND_URL = "https://ori.example.com"


def _chunk_png(tipo: bytes, datos: bytes) -> bytes:
    crc = zlib.crc32(tipo)
    crc = zlib.crc32(datos, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", crc)


def _firma_png() -> str:
    ihdr = struct.pack(">IIBBBBB", 2, 1, 8, 6, 0, 0, 0)
    filas = b"\x00" + b"\x00\x00\x00\xff" * 2
    contenido = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk_png(b"IHDR", ihdr)
        + _chunk_png(b"IDAT", zlib.compress(filas))
        + _chunk_png(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(contenido).decode()


FIRMA_PNG = _firma_png()


def _token_mensaje(mensaje) -> str:
    marcador = "/firma-convenio#token="
    return mensaje.texto.split(marcador, 1)[1].splitlines()[0]


def _crear_escenario_concurrente(db_engine) -> dict[str, object]:
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    identificador = uuid4().hex
    with fabrica() as sesion:
        rol_gestor = sesion.scalar(
            select(Rol).where(Rol.codigo == CodigoRol.GESTOR_ORI.value)
        )
        rol_revisor = sesion.scalar(
            select(Rol).where(Rol.codigo == CodigoRol.REVISOR_ORI.value)
        )
        assert rol_gestor is not None and rol_revisor is not None
        gestor = Usuario(
            correo=f"hu15-gestor-{identificador}@example.com",
            hash_contrasena=hash_contrasena("ClaveSegura123!"),
            nombre_completo="Gestor concurrencia HU-15",
            rol=rol_gestor,
            tipo_usuario=TipoUsuario.INTERNO.value,
            activo=True,
            correo_verificado_en=datetime.now(UTC),
        )
        revisor = Usuario(
            correo=f"hu15-revisor-{identificador}@example.com",
            hash_contrasena=hash_contrasena("ClaveSegura123!"),
            nombre_completo="Revisor concurrencia HU-15",
            rol=rol_revisor,
            tipo_usuario=TipoUsuario.INTERNO.value,
            activo=True,
            correo_verificado_en=datetime.now(UTC),
        )
        sesion.add_all([gestor, revisor])
        sesion.flush()
        solicitud = SolicitudConvenio(
            consecutivo=f"HU15-{identificador}",
            tipo_solicitante=TipoSolicitante.INTERNO.value,
            solicitante_id=gestor.id,
            objeto="Solicitud para concurrencia HU-15",
            estado=EstadoSolicitud.APROBADA.value,
            nombre_aliado_propuesto="Aliado concurrencia HU-15",
            tipo_identificacion_aliado_propuesto=TipoIdentificacion.NIT.value,
            identificacion_aliado_propuesto=f"9{identificador[:15]}",
            tipo_aliado_propuesto=TipoAliado.UNIVERSIDAD.value,
            correo_aliado_propuesto=f"aliado-{identificador}@example.com",
        )
        sesion.add(solicitud)
        sesion.flush()
        etapa_elaboracion = sesion.scalar(
            select(Etapa).where(Etapa.codigo == "ELABORACION")
        )
        etapa_final = sesion.scalar(
            select(Etapa).where(Etapa.codigo == "REVISION_FINAL")
        )
        etapa_firmas = sesion.scalar(
            select(Etapa).where(Etapa.codigo == "APROBACION_FIRMAS")
        )
        assert etapa_elaboracion and etapa_final and etapa_firmas
        convenio = Convenio(
            solicitud_id=solicitud.id,
            version_actual=1,
            etapa_actual=etapa_final,
            estado=EstadoConvenio.EN_TRAMITE.value,
            objeto="Convenio para concurrencia HU-15",
            creado_por_id=gestor.id,
        )
        sesion.add(convenio)
        sesion.flush()
        version = VersionConvenio(
            convenio_id=convenio.id,
            numero=1,
            contenido={"type": "doc", "content": [{"type": "paragraph"}]},
            snapshot_metadata={},
            autor_id=gestor.id,
            etapa_id=etapa_final.id,
            contexto=ContextoVersionConvenio.FINALIZACION.value,
        )
        historial = HistorialEtapa(
            convenio_id=convenio.id,
            etapa_origen_id=etapa_elaboracion.id,
            etapa_destino_id=etapa_final.id,
            usuario_id=gestor.id,
            responsable_id=gestor.id,
            observacion="Escenario concurrente HU-15",
        )
        sesion.add_all([version, historial])
        sesion.flush()
        juridicas = [
            RevisionConvenio(
                convenio_id=convenio.id,
                tipo=TipoRevisionConvenio.JURIDICA.value,
                historial_etapa_id=historial.id,
                version_convenio_id=version.id,
                version_resultado_id=version.id,
                instancia_juridica=instancia,
                numero_ronda=1,
                responsable_id=revisor.id,
                estado=EstadoRevisionConvenio.RESUELTA.value,
                resultado=ResultadoRevisionConvenio.APROBADA.value,
                resuelta_por_id=revisor.id,
                resuelta_en=datetime.now(UTC),
            )
            for instancia in (1, 2)
        ]
        contraparte = RevisionConvenio(
            convenio_id=convenio.id,
            tipo=TipoRevisionConvenio.CONTRAPARTE.value,
            historial_etapa_id=historial.id,
            version_convenio_id=version.id,
            version_resultado_id=version.id,
            creada_por_id=gestor.id,
            estado=EstadoRevisionConvenio.RESUELTA.value,
            resultado=ResultadoRevisionConvenio.APROBADA.value,
            resuelta_en=datetime.now(UTC),
        )
        revision_final = RevisionConvenio(
            convenio_id=convenio.id,
            tipo=TipoRevisionConvenio.FINAL.value,
            historial_etapa_id=historial.id,
            version_convenio_id=version.id,
            responsable_id=gestor.id,
            creada_por_id=gestor.id,
            estado=EstadoRevisionConvenio.PENDIENTE.value,
        )
        sesion.add_all([*juridicas, contraparte, revision_final])
        sesion.commit()
        return {
            "convenio_id": convenio.id,
            "solicitud_id": solicitud.id,
            "gestor_id": gestor.id,
            "revisor_id": revisor.id,
            "version_numero": version.numero,
            "etapa_final_id": etapa_final.id,
            "etapa_firmas_id": etapa_firmas.id,
        }


def _limpiar_escenario_concurrente(db_engine, escenario: dict[str, object]) -> None:
    fabrica = sessionmaker(bind=db_engine)
    convenio_id = int(escenario["convenio_id"])
    with fabrica() as sesion:
        aliado_id = sesion.scalar(
            select(Convenio.aliado_id).where(Convenio.id == convenio_id)
        )
        proceso_ids = select(ProcesoFirmasConvenio.id).where(
            ProcesoFirmasConvenio.convenio_id == convenio_id
        )
        firma_ids = select(FirmaConvenio.id).where(
            FirmaConvenio.proceso_firmas_id.in_(proceso_ids)
        )
        sesion.execute(
            delete(InvitacionFirmaConvenio).where(
                InvitacionFirmaConvenio.firma_convenio_id.in_(firma_ids)
            )
        )
        sesion.execute(
            delete(FirmaConvenio).where(
                FirmaConvenio.proceso_firmas_id.in_(proceso_ids)
            )
        )
        sesion.execute(
            delete(ProcesoFirmasConvenio).where(
                ProcesoFirmasConvenio.convenio_id == convenio_id
            )
        )
        sesion.execute(
            delete(ObservacionRevision).where(
                ObservacionRevision.convenio_id == convenio_id
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
        sesion.execute(delete(Convenio).where(Convenio.id == convenio_id))
        sesion.execute(
            delete(SolicitudConvenio).where(
                SolicitudConvenio.id == int(escenario["solicitud_id"])
            )
        )
        if aliado_id is not None:
            sesion.execute(delete(Aliado).where(Aliado.id == aliado_id))
        sesion.execute(
            delete(Usuario).where(
                Usuario.id.in_(
                    (int(escenario["gestor_id"]), int(escenario["revisor_id"]))
                )
            )
        )
        sesion.commit()


@pytest.fixture
def escenario_final(db, convenio_listo, gestor, revisor):
    etapa_final = db.scalar(select(Etapa).where(Etapa.codigo == "REVISION_FINAL"))
    assert etapa_final is not None
    version = db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio_listo.id,
            VersionConvenio.numero == convenio_listo.version_actual,
        )
    )
    assert version is not None
    historial = HistorialEtapa(
        convenio_id=convenio_listo.id,
        etapa_origen_id=convenio_listo.etapa_actual_id,
        etapa_destino_id=etapa_final.id,
        usuario_id=gestor.id,
        responsable_id=gestor.id,
        observacion="Escenario HU-15",
    )
    db.add(historial)
    db.flush()
    juridicas = [
        RevisionConvenio(
            convenio_id=convenio_listo.id,
            tipo=TipoRevisionConvenio.JURIDICA.value,
            historial_etapa_id=historial.id,
            version_convenio_id=version.id,
            version_resultado_id=version.id,
            instancia_juridica=instancia,
            numero_ronda=1,
            responsable_id=revisor.id,
            estado=EstadoRevisionConvenio.RESUELTA.value,
            resultado=ResultadoRevisionConvenio.APROBADA.value,
            resuelta_por_id=revisor.id,
            resuelta_en=datetime.now(UTC),
        )
        for instancia in (1, 2)
    ]
    contraparte = RevisionConvenio(
        convenio_id=convenio_listo.id,
        tipo=TipoRevisionConvenio.CONTRAPARTE.value,
        historial_etapa_id=historial.id,
        version_convenio_id=version.id,
        version_resultado_id=version.id,
        creada_por_id=gestor.id,
        estado=EstadoRevisionConvenio.RESUELTA.value,
        resultado=ResultadoRevisionConvenio.APROBADA.value,
        resuelta_en=datetime.now(UTC),
    )
    revision_final = RevisionConvenio(
        convenio_id=convenio_listo.id,
        tipo=TipoRevisionConvenio.FINAL.value,
        historial_etapa_id=historial.id,
        version_convenio_id=version.id,
        responsable_id=gestor.id,
        creada_por_id=gestor.id,
        estado=EstadoRevisionConvenio.PENDIENTE.value,
    )
    db.add_all([*juridicas, contraparte, revision_final])
    convenio_listo.etapa_actual = etapa_final
    db.commit()
    return {
        "convenio": convenio_listo,
        "version": version,
        "historial": historial,
        "juridicas": juridicas,
        "contraparte": contraparte,
        "revision_final": revision_final,
        "gestor": gestor,
    }


def _aprobar(client, escenario):
    return client.post(
        f"/api/convenios/{escenario['convenio'].id}/revision-final/aprobar",
        json={"expected_version": escenario["version"].numero},
    )


def _configurar(client, convenio_id, firma_id, modalidad="ELECTRONICA"):
    datos = {
        "nombre": f"Firmante {firma_id}",
        "cargo": "Cargo institucional",
        "modalidad": modalidad,
    }
    if modalidad == "ELECTRONICA":
        datos["correo"] = f"firmante-{firma_id}@example.com"
    return client.patch(
        f"/api/convenios/{convenio_id}/firmas/{firma_id}", json=datos
    )


def _iniciar_proceso(client, escenario, modalidades):
    proceso = _aprobar(client, escenario).json()
    for firma, modalidad in zip(proceso["firmas"], modalidades, strict=True):
        assert (
            _configurar(
                client,
                escenario["convenio"].id,
                firma["id"],
                modalidad=modalidad,
            ).status_code
            == 200
        )
    respuesta = client.post(
        f"/api/convenios/{escenario['convenio'].id}/firmas/iniciar"
    )
    assert respuesta.status_code == 200
    return respuesta.json()


def _registrar_fisicas(
    client, convenio_id, firma_ids, fecha="2026-09-28", archivo=b"%PDF-1.4 firmado"
):
    partes = [("firma_ids", (None, str(firma_id))) for firma_id in firma_ids]
    partes.extend(
        [
            ("fecha_firma", (None, fecha)),
            ("archivo", ("convenio-firmado.pdf", archivo, "application/pdf")),
        ]
    )
    return client.post(
        f"/api/convenios/{convenio_id}/firmas/fisicas", files=partes
    )


def _preparar_contraparte_formalizacion(db, escenario, identificacion=None):
    solicitud = escenario["convenio"].solicitud
    solicitud.nombre_aliado_propuesto = "Aliado formalización HU-15"
    solicitud.tipo_identificacion_aliado_propuesto = TipoIdentificacion.NIT.value
    solicitud.identificacion_aliado_propuesto = identificacion or str(
        900000000 + uuid4().int % 99999999
    )
    solicitud.tipo_aliado_propuesto = TipoAliado.UNIVERSIDAD.value
    solicitud.correo_aliado_propuesto = "formalizacion@example.com"
    db.commit()


def _proceso_listo_para_formalizar(client, db, escenario, identificacion=None):
    _preparar_contraparte_formalizacion(db, escenario, identificacion)
    proceso = _iniciar_proceso(
        client, escenario, ["FISICA"] * len(ROLES_ESPERADOS)
    )
    respuesta = _registrar_fisicas(
        client,
        escenario["convenio"].id,
        [firma["id"] for firma in proceso["firmas"]],
    )
    assert respuesta.status_code == 201
    return respuesta.json()


def _formalizar(client, escenario):
    return client.post(
        f"/api/convenios/{escenario['convenio'].id}/firmas/formalizar"
    )


def _obtener_documento_aprobado(client, convenio_id):
    return client.get(
        f"/api/convenios/{convenio_id}/firmas/documento-aprobado"
    )


def test_documento_aprobado_en_configuracion_usa_version_congelada(
    client, db, escenario_final
):
    proceso = _aprobar(client, escenario_final).json()
    convenio = escenario_final["convenio"]
    congelada = escenario_final["version"]
    contenido_congelado = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "V5"}]}
        ],
    }
    congelada.contenido = contenido_congelado
    posterior = VersionConvenio(
        convenio_id=convenio.id,
        numero=congelada.numero + 1,
        contenido={
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "V6 no aprobada"}],
                }
            ],
        },
        snapshot_metadata={},
        autor_id=escenario_final["gestor"].id,
        etapa_id=congelada.etapa_id,
        contexto=ContextoVersionConvenio.GUARDADO.value,
    )
    db.add(posterior)
    db.flush()
    convenio.version_actual = posterior.numero
    db.commit()

    respuesta = _obtener_documento_aprobado(client, convenio.id)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert proceso["estado"] == EstadoProcesoFirmasConvenio.CONFIGURACION.value
    assert datos["proceso_firmas_id"] == proceso["id"]
    assert datos["version_convenio_id"] == congelada.id
    assert datos["version_numero"] == congelada.numero
    assert datos["contenido"] == contenido_congelado
    assert datos["version_convenio_id"] != posterior.id


def test_documento_aprobado_rechaza_convenio_sin_proceso(
    client, escenario_final
):
    respuesta = _obtener_documento_aprobado(
        client, escenario_final["convenio"].id
    )

    assert respuesta.status_code == 409


def test_documento_aprobado_rechaza_version_ajena_sin_fallback(
    client, db, escenario_final, crear_convenio
):
    proceso = _aprobar(client, escenario_final).json()
    otro_convenio = crear_convenio(escenario_final["gestor"])
    version_ajena = db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == otro_convenio.id
        )
    )
    assert version_ajena is not None
    proceso_persistido = db.get(ProcesoFirmasConvenio, proceso["id"])
    assert proceso_persistido is not None
    proceso_persistido.version_convenio_id = version_ajena.id
    db.commit()

    respuesta = _obtener_documento_aprobado(
        client, escenario_final["convenio"].id
    )

    assert respuesta.status_code == 409


def test_administrador_puede_consultar_documento_aprobado(
    client, crear_usuario, entrar_como, escenario_final
):
    _aprobar(client, escenario_final)
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI))

    respuesta = _obtener_documento_aprobado(
        client, escenario_final["convenio"].id
    )

    assert respuesta.status_code == 200


@pytest.mark.parametrize(
    "codigo_rol",
    [CodigoRol.REVISOR_ORI, CodigoRol.SOLICITANTE_INTERNO],
)
def test_roles_sin_gestion_firmas_no_consultan_documento_aprobado(
    client, crear_usuario, entrar_como, escenario_final, codigo_rol
):
    _aprobar(client, escenario_final)
    entrar_como(crear_usuario(codigo_rol))

    respuesta = _obtener_documento_aprobado(
        client, escenario_final["convenio"].id
    )

    assert respuesta.status_code == 403


def test_usuario_sin_sesion_no_consulta_documento_aprobado(
    client, escenario_final
):
    _aprobar(client, escenario_final)
    client.cookies.clear()

    respuesta = _obtener_documento_aprobado(
        client, escenario_final["convenio"].id
    )

    assert respuesta.status_code == 401


def test_no_accede_revision_final_fuera_de_etapa(client, convenio_listo):
    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revision-final")
    assert respuesta.status_code == 409


def test_revision_final_usa_version_aprobada_no_version_actual(
    client, db, escenario_final
):
    convenio = escenario_final["convenio"]
    aprobada = escenario_final["version"]
    posterior = VersionConvenio(
        convenio_id=convenio.id,
        numero=aprobada.numero + 1,
        contenido={"type": "doc", "content": [{"type": "paragraph"}]},
        snapshot_metadata=aprobada.snapshot_metadata,
        autor_id=escenario_final["gestor"].id,
        etapa_id=convenio.etapa_actual_id,
        contexto=ContextoVersionConvenio.GUARDADO.value,
    )
    db.add(posterior)
    convenio.version_actual = posterior.numero
    db.commit()

    respuesta = client.get(f"/api/convenios/{convenio.id}/revision-final")

    assert respuesta.status_code == 200
    assert respuesta.json()["version_aprobada_contraparte"]["id"] == aprobada.id
    assert respuesta.json()["version_aprobada_contraparte"]["contenido"] == (
        aprobada.contenido
    )


def test_no_aprueba_con_observaciones_pendientes(client, db, escenario_final):
    db.add(
        ObservacionRevision(
            convenio_id=escenario_final["convenio"].id,
            historial_etapa_id=escenario_final["historial"].id,
            revision_convenio_id=escenario_final["revision_final"].id,
            origen=OrigenObservacionRevision.REVISION_FINAL_ORI.value,
            registrada_por_id=escenario_final["gestor"].id,
            responsable_id=escenario_final["gestor"].id,
            descripcion="Debe corregirse",
        )
    )
    db.commit()
    assert _aprobar(client, escenario_final).status_code == 409


@pytest.mark.parametrize("revision_indice", [0, 1])
def test_no_aprueba_si_juridicas_no_corresponden_a_misma_version(
    client, db, escenario_final, revision_indice
):
    revision = escenario_final["juridicas"][revision_indice]
    revision.version_resultado_id = None
    db.commit()
    assert _aprobar(client, escenario_final).status_code == 409


def test_devolver_crea_observaciones_y_regresa_a_elaboracion(
    client, db, escenario_final
):
    respuesta = client.post(
        f"/api/convenios/{escenario_final['convenio'].id}/revision-final/devolver",
        json={
            "expected_version": escenario_final["version"].numero,
            "observaciones": ["Ajustar cláusula final"],
        },
    )
    assert respuesta.status_code == 200
    db.expire_all()
    convenio = db.get(Convenio, escenario_final["convenio"].id)
    revision = db.get(RevisionConvenio, escenario_final["revision_final"].id)
    observacion = db.scalar(
        select(ObservacionRevision).where(
            ObservacionRevision.revision_convenio_id == revision.id
        )
    )
    assert convenio.etapa_actual.codigo == "ELABORACION"
    assert revision.resultado == "DEVUELTA"
    assert revision.version_resultado_id == escenario_final["version"].id
    assert observacion.origen == "REVISION_FINAL_ORI"
    assert db.scalar(
        select(func.count()).select_from(ProcesoFirmasConvenio).where(
            ProcesoFirmasConvenio.convenio_id == convenio.id
        )
    ) == 0


def test_devolver_exige_una_observacion(client, escenario_final):
    respuesta = client.post(
        f"/api/convenios/{escenario_final['convenio'].id}/revision-final/devolver",
        json={
            "expected_version": escenario_final["version"].numero,
            "observaciones": [],
        },
    )
    assert respuesta.status_code == 422


def test_aprobar_crea_proceso_y_exactamente_siete_firmas(
    client, db, escenario_final
):
    respuesta = _aprobar(client, escenario_final)
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["estado"] == "CONFIGURACION"
    assert datos["version_convenio_id"] == escenario_final["version"].id
    assert datos["revision_final_id"] == escenario_final["revision_final"].id
    assert len(datos["firmas"]) == 7
    assert [firma["rol_firmante"] for firma in datos["firmas"]] == ROLES_ESPERADOS
    assert [firma["orden"] for firma in datos["firmas"]] == list(range(1, 8))
    assert all(firma["estado"] == "PENDIENTE" for firma in datos["firmas"])
    assert datos["firmas"][-1]["parte"] == "UNIDAD_SOLICITANTE"
    db.expire_all()
    convenio = db.get(Convenio, escenario_final["convenio"].id)
    revision = db.get(RevisionConvenio, escenario_final["revision_final"].id)
    assert convenio.etapa_actual.codigo == "APROBACION_FIRMAS"
    assert convenio.estado == "EN_TRAMITE"
    assert revision.resultado == "APROBADA"
    assert revision.version_resultado_id == escenario_final["version"].id


def test_slot_solicitante_externo_no_infiere_identidad(client, db, escenario_final):
    solicitud = escenario_final["convenio"].solicitud
    solicitud.tipo_solicitante = TipoSolicitante.EXTERNO.value
    solicitud.solicitante_nombre = "Persona que radicó"
    solicitud.solicitante_cargo = "Gestora de la solicitud"
    solicitud.solicitante_correo = "solicitante@example.com"
    db.commit()

    respuesta = _aprobar(client, escenario_final)

    assert respuesta.status_code == 201
    firma = respuesta.json()["firmas"][6]
    assert firma["rol_firmante"] == "PARTE_SOLICITANTE"
    assert firma["parte"] == "REPRESENTANTE_LEGAL_ENTIDAD"
    assert firma["nombre_firmante"] is None
    assert firma["cargo_firmante"] is None
    assert firma["correo_firmante"] is None
    assert firma["usuario_id"] is None


def test_aprobar_es_idempotente_y_no_crea_segundo_proceso(
    client, db, escenario_final
):
    assert _aprobar(client, escenario_final).status_code == 201
    assert _aprobar(client, escenario_final).status_code == 409
    assert db.scalar(
        select(func.count()).select_from(ProcesoFirmasConvenio).where(
            ProcesoFirmasConvenio.convenio_id == escenario_final["convenio"].id
        )
    ) == 1


def test_aprobaciones_finales_concurrentes_crean_un_solo_proceso(
    db_engine,
):
    escenario = _crear_escenario_concurrente(db_engine)
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    barrera = Barrier(2)

    def aprobar() -> str:
        with fabrica() as sesion:
            gestor = sesion.get(Usuario, int(escenario["gestor_id"]))
            assert gestor is not None
            barrera.wait(timeout=10)
            try:
                ServicioFirmas(sesion).aprobar_revision_final(
                    int(escenario["convenio_id"]),
                    int(escenario["version_numero"]),
                    gestor,
                )
                return "APROBADA"
            except RevisionNoDisponible:
                return "CONFLICTO"

    try:
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(lambda _: aprobar(), range(2)))
        assert sorted(resultados) == ["APROBADA", "CONFLICTO"]

        with fabrica() as verificacion:
            convenio_id = int(escenario["convenio_id"])
            procesos = list(
                verificacion.scalars(
                    select(ProcesoFirmasConvenio).where(
                        ProcesoFirmasConvenio.convenio_id == convenio_id,
                        ProcesoFirmasConvenio.estado
                        == EstadoProcesoFirmasConvenio.CONFIGURACION.value,
                    )
                )
            )
            assert len(procesos) == 1
            assert verificacion.scalar(
                select(func.count())
                .select_from(FirmaConvenio)
                .where(FirmaConvenio.proceso_firmas_id == procesos[0].id)
            ) == 7
            assert verificacion.scalar(
                select(func.count())
                .select_from(HistorialEtapa)
                .where(
                    HistorialEtapa.convenio_id == convenio_id,
                    HistorialEtapa.etapa_origen_id
                    == int(escenario["etapa_final_id"]),
                    HistorialEtapa.etapa_destino_id
                    == int(escenario["etapa_firmas_id"]),
                )
            ) == 1
            revision = verificacion.scalar(
                select(RevisionConvenio).where(
                    RevisionConvenio.convenio_id == convenio_id,
                    RevisionConvenio.tipo == TipoRevisionConvenio.FINAL.value,
                )
            )
            assert revision is not None
            assert revision.estado == EstadoRevisionConvenio.RESUELTA.value
            assert revision.resultado == ResultadoRevisionConvenio.APROBADA.value
    finally:
        _limpiar_escenario_concurrente(db_engine, escenario)


def test_constraint_impide_segundo_proceso_activo(db, escenario_final):
    base = {
        "convenio_id": escenario_final["convenio"].id,
        "version_convenio_id": escenario_final["version"].id,
        "creado_por_id": escenario_final["gestor"].id,
        "estado": EstadoProcesoFirmasConvenio.CONFIGURACION.value,
    }
    primera = ProcesoFirmasConvenio(
        revision_final_id=escenario_final["revision_final"].id, **base
    )
    db.add(primera)
    db.commit()
    otra_revision = RevisionConvenio(
        convenio_id=escenario_final["convenio"].id,
        tipo=TipoRevisionConvenio.FINAL.value,
        version_convenio_id=escenario_final["version"].id,
        estado=EstadoRevisionConvenio.RESUELTA.value,
        resultado=ResultadoRevisionConvenio.APROBADA.value,
    )
    db.add(otra_revision)
    db.flush()
    db.add(ProcesoFirmasConvenio(revision_final_id=otra_revision.id, **base))
    with pytest.raises(IntegrityError):
        db.commit()


def test_configurar_electronica_exige_correo(client, escenario_final):
    proceso = _aprobar(client, escenario_final).json()
    firma_id = proceso["firmas"][0]["id"]
    respuesta = client.patch(
        f"/api/convenios/{escenario_final['convenio'].id}/firmas/{firma_id}",
        json={
            "nombre": "Ana Pérez",
            "cargo": "Directora",
            "modalidad": "ELECTRONICA",
        },
    )
    assert respuesta.status_code == 422


def test_configurar_fisica_permite_correo_opcional(client, escenario_final):
    proceso = _aprobar(client, escenario_final).json()
    firma_id = proceso["firmas"][0]["id"]
    respuesta = _configurar(
        client, escenario_final["convenio"].id, firma_id, modalidad="FISICA"
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["correo_firmante"] is None
    assert respuesta.json()["configurada"] is True


def test_no_reconfigura_firma_completada_aunque_proceso_siga_en_configuracion(
    client, db, escenario_final
):
    proceso = _aprobar(client, escenario_final).json()
    firma = db.get(FirmaConvenio, proceso["firmas"][0]["id"])
    assert firma is not None
    fecha_original = datetime.now(UTC)
    firma.nombre_firmante = "Identidad original"
    firma.cargo_firmante = "Cargo original"
    firma.correo_firmante = "original@example.com"
    firma.modalidad = "ELECTRONICA"
    firma.estado = EstadoFirmaConvenio.FIRMADA.value
    firma.fecha_firma = fecha_original
    db.commit()

    respuesta = client.patch(
        f"/api/convenios/{escenario_final['convenio'].id}/firmas/{firma.id}",
        json={
            "nombre": "Identidad reemplazada",
            "cargo": "Cargo reemplazado",
            "correo": "reemplazo@example.com",
            "modalidad": "FISICA",
        },
    )

    assert respuesta.status_code == 409
    db.expire_all()
    persistida = db.get(FirmaConvenio, firma.id)
    assert persistida is not None
    assert persistida.nombre_firmante == "Identidad original"
    assert persistida.cargo_firmante == "Cargo original"
    assert persistida.correo_firmante == "original@example.com"
    assert persistida.modalidad == "ELECTRONICA"
    assert persistida.estado == EstadoFirmaConvenio.FIRMADA.value
    assert persistida.fecha_firma == fecha_original
    assert persistida.documento_id is None


def test_iniciar_falla_con_configuracion_incompleta(client, escenario_final):
    _aprobar(client, escenario_final)
    respuesta = client.post(
        f"/api/convenios/{escenario_final['convenio'].id}/firmas/iniciar"
    )
    assert respuesta.status_code == 409


def test_iniciar_falla_si_solo_hay_seis_slots(client, db, escenario_final):
    proceso = _aprobar(client, escenario_final).json()
    firma = db.get(FirmaConvenio, proceso["firmas"][-1]["id"])
    db.delete(firma)
    db.commit()
    respuesta = client.post(
        f"/api/convenios/{escenario_final['convenio'].id}/firmas/iniciar"
    )
    assert respuesta.status_code == 409


def test_iniciar_funciona_con_siete_configuradas(client, escenario_final):
    proceso = _aprobar(client, escenario_final).json()
    for firma in proceso["firmas"]:
        assert _configurar(
            client, escenario_final["convenio"].id, firma["id"]
        ).status_code == 200
    respuesta = client.post(
        f"/api/convenios/{escenario_final['convenio'].id}/firmas/iniciar"
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "EN_CURSO"
    assert respuesta.json()["iniciado_en"] is not None


def test_no_modifica_firmante_despues_de_iniciar(client, escenario_final):
    proceso = _aprobar(client, escenario_final).json()
    for firma in proceso["firmas"]:
        _configurar(client, escenario_final["convenio"].id, firma["id"])
    client.post(f"/api/convenios/{escenario_final['convenio'].id}/firmas/iniciar")
    respuesta = _configurar(
        client, escenario_final["convenio"].id, proceso["firmas"][0]["id"]
    )
    assert respuesta.status_code == 409


def test_registra_firma_fisica_con_documento_y_fecha_sin_cerrar_proceso(
    client, db, escenario_final
):
    proceso = _iniciar_proceso(
        client, escenario_final, ["FISICA"] * len(ROLES_ESPERADOS)
    )
    firma_id = proceso["firmas"][0]["id"]

    respuesta = _registrar_fisicas(
        client, escenario_final["convenio"].id, [firma_id]
    )

    assert respuesta.status_code == 201
    datos = respuesta.json()
    registrada = next(firma for firma in datos["firmas"] if firma["id"] == firma_id)
    assert registrada["estado"] == "FIRMADA"
    assert registrada["fecha_firma"].startswith("2026-09-28")
    assert registrada["documento_id"] is not None
    assert registrada["documento"]["tipo"] == "CONVENIO_FIRMADO"
    assert registrada["documento"]["nombre_archivo"] == "convenio-firmado.pdf"
    assert datos["estado"] == "EN_CURSO"

    db.expire_all()
    firma = db.get(FirmaConvenio, firma_id)
    documento = db.get(Documento, registrada["documento_id"])
    convenio = db.get(Convenio, escenario_final["convenio"].id)
    assert firma is not None and documento is not None and convenio is not None
    assert firma.documento_id == documento.id
    assert firma.fecha_firma is not None
    assert documento.convenio_id == convenio.id
    assert documento.tipo == "CONVENIO_FIRMADO"
    assert convenio.estado == EstadoConvenio.EN_TRAMITE.value
    proceso_persistido = db.get(ProcesoFirmasConvenio, proceso["id"])
    assert proceso_persistido is not None
    assert proceso_persistido.estado == EstadoProcesoFirmasConvenio.EN_CURSO.value
    assert proceso_persistido.completado_en is None


def test_mismo_documento_acredita_dos_firmas_fisicas(
    client, db, escenario_final
):
    proceso = _iniciar_proceso(
        client, escenario_final, ["FISICA"] * len(ROLES_ESPERADOS)
    )
    firma_ids = [firma["id"] for firma in proceso["firmas"][:2]]

    respuesta = _registrar_fisicas(
        client, escenario_final["convenio"].id, firma_ids
    )

    assert respuesta.status_code == 201
    db.expire_all()
    firmas = [db.get(FirmaConvenio, firma_id) for firma_id in firma_ids]
    assert all(firma is not None for firma in firmas)
    assert firmas[0].documento_id == firmas[1].documento_id
    assert firmas[0].documento_id is not None
    assert db.scalar(
        select(func.count()).select_from(Documento).where(
            Documento.convenio_id == escenario_final["convenio"].id,
            Documento.tipo == "CONVENIO_FIRMADO",
        )
    ) == 1


def test_siete_firmas_fisicas_no_completan_proceso_ni_activan_convenio(
    client, db, escenario_final
):
    proceso = _iniciar_proceso(
        client, escenario_final, ["FISICA"] * len(ROLES_ESPERADOS)
    )
    firma_ids = [firma["id"] for firma in proceso["firmas"]]

    respuesta = _registrar_fisicas(
        client, escenario_final["convenio"].id, firma_ids
    )

    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert all(firma["estado"] == "FIRMADA" for firma in datos["firmas"])
    assert datos["estado"] == "EN_CURSO"
    db.expire_all()
    convenio = db.get(Convenio, escenario_final["convenio"].id)
    proceso_persistido = db.get(ProcesoFirmasConvenio, proceso["id"])
    assert convenio is not None and proceso_persistido is not None
    assert convenio.estado == EstadoConvenio.EN_TRAMITE.value
    assert proceso_persistido.estado == EstadoProcesoFirmasConvenio.EN_CURSO.value
    assert proceso_persistido.completado_en is None


def test_rechaza_ids_de_firma_duplicados(client, escenario_final):
    proceso = _iniciar_proceso(
        client, escenario_final, ["FISICA"] * len(ROLES_ESPERADOS)
    )
    firma_id = proceso["firmas"][0]["id"]
    respuesta = _registrar_fisicas(
        client, escenario_final["convenio"].id, [firma_id, firma_id]
    )
    assert respuesta.status_code == 422


def test_rechaza_firma_electronica_en_registro_fisico(client, escenario_final):
    proceso = _iniciar_proceso(
        client,
        escenario_final,
        ["ELECTRONICA", *(["FISICA"] * (len(ROLES_ESPERADOS) - 1))],
    )
    respuesta = _registrar_fisicas(
        client,
        escenario_final["convenio"].id,
        [proceso["firmas"][0]["id"]],
    )
    assert respuesta.status_code == 422


def test_rechaza_sobrescribir_firma_fisica_completada(client, escenario_final):
    proceso = _iniciar_proceso(
        client, escenario_final, ["FISICA"] * len(ROLES_ESPERADOS)
    )
    firma_id = proceso["firmas"][0]["id"]
    assert (
        _registrar_fisicas(
            client, escenario_final["convenio"].id, [firma_id]
        ).status_code
        == 201
    )
    respuesta = _registrar_fisicas(
        client, escenario_final["convenio"].id, [firma_id]
    )
    assert respuesta.status_code == 409


def test_rechaza_firma_de_otro_proceso(client, db, escenario_final):
    proceso = _iniciar_proceso(
        client, escenario_final, ["FISICA"] * len(ROLES_ESPERADOS)
    )
    revision_anterior = RevisionConvenio(
        convenio_id=escenario_final["convenio"].id,
        tipo=TipoRevisionConvenio.FINAL.value,
        version_convenio_id=escenario_final["version"].id,
        version_resultado_id=escenario_final["version"].id,
        estado=EstadoRevisionConvenio.RESUELTA.value,
        resultado=ResultadoRevisionConvenio.APROBADA.value,
    )
    db.add(revision_anterior)
    db.flush()
    proceso_anterior = ProcesoFirmasConvenio(
        convenio_id=escenario_final["convenio"].id,
        version_convenio_id=escenario_final["version"].id,
        revision_final_id=revision_anterior.id,
        creado_por_id=escenario_final["gestor"].id,
        estado=EstadoProcesoFirmasConvenio.CANCELADO.value,
    )
    db.add(proceso_anterior)
    db.flush()
    firma_ajena = FirmaConvenio(
        proceso_firmas_id=proceso_anterior.id,
        orden=1,
        rol_firmante=RolFirmanteConvenio.ADMINISTRADOR_ORI.value,
        parte="UNIVERSIDAD",
        nombre_firmante="Firma de proceso anterior",
        cargo_firmante="Cargo",
        modalidad=ModalidadFirma.FISICA.value,
        estado=EstadoFirmaConvenio.PENDIENTE.value,
    )
    db.add(firma_ajena)
    db.commit()

    respuesta = _registrar_fisicas(
        client, escenario_final["convenio"].id, [firma_ajena.id]
    )

    assert respuesta.status_code == 422
    db.expire_all()
    activa = db.get(ProcesoFirmasConvenio, proceso["id"])
    assert activa is not None and activa.estado == "EN_CURSO"


def test_rechaza_registro_fisico_fuera_de_proceso_en_curso(
    client, escenario_final
):
    proceso = _aprobar(client, escenario_final).json()
    firma_id = proceso["firmas"][0]["id"]
    assert (
        _configurar(
            client,
            escenario_final["convenio"].id,
            firma_id,
            modalidad="FISICA",
        ).status_code
        == 200
    )
    respuesta = _registrar_fisicas(
        client, escenario_final["convenio"].id, [firma_id]
    )
    assert respuesta.status_code == 409


def test_rechaza_registro_fisico_sin_firmas(client, escenario_final):
    _iniciar_proceso(client, escenario_final, ["FISICA"] * len(ROLES_ESPERADOS))
    respuesta = _registrar_fisicas(
        client, escenario_final["convenio"].id, []
    )
    assert respuesta.status_code == 422


def test_revisor_no_puede_registrar_firmas_fisicas(
    client, crear_usuario, entrar_como, escenario_final
):
    proceso = _iniciar_proceso(
        client, escenario_final, ["FISICA"] * len(ROLES_ESPERADOS)
    )
    revisor = crear_usuario(CodigoRol.REVISOR_ORI)
    entrar_como(revisor)

    respuesta = _registrar_fisicas(
        client,
        escenario_final["convenio"].id,
        [proceso["firmas"][0]["id"]],
    )

    assert respuesta.status_code == 403


def test_seis_de_siete_firmas_no_permiten_formalizar(
    client, db, escenario_final
):
    proceso = _proceso_listo_para_formalizar(client, db, escenario_final)
    firma = db.get(FirmaConvenio, proceso["firmas"][-1]["id"])
    assert firma is not None
    firma.estado = EstadoFirmaConvenio.PENDIENTE.value
    firma.fecha_firma = None
    db.commit()

    respuesta = _formalizar(client, escenario_final)

    assert respuesta.status_code == 409


def test_formalizar_cierra_proceso_y_activa_convenio_sin_nueva_version(
    client, db, escenario_final
):
    proceso = _proceso_listo_para_formalizar(client, db, escenario_final)
    for indice, firma_dato in enumerate(proceso["firmas"]):
        firma = db.get(FirmaConvenio, firma_dato["id"])
        assert firma is not None
        firma.fecha_firma = datetime(2026, 9, 20 + indice, tzinfo=UTC)
    db.commit()
    versiones_antes = db.scalar(
        select(func.count()).select_from(VersionConvenio).where(
            VersionConvenio.convenio_id == escenario_final["convenio"].id
        )
    )

    respuesta = _formalizar(client, escenario_final)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "COMPLETADO"
    assert datos["completado_en"] is not None
    assert datos["version_convenio_id"] == escenario_final["version"].id
    assert datos["version_numero"] == escenario_final["version"].numero
    db.expire_all()
    convenio = db.get(Convenio, escenario_final["convenio"].id)
    proceso_persistido = db.get(ProcesoFirmasConvenio, proceso["id"])
    assert convenio is not None and proceso_persistido is not None
    assert convenio.estado == EstadoConvenio.VIGENTE.value
    assert convenio.etapa_actual.codigo == "FIRMA_ARCHIVO_SEGUIMIENTO"
    assert convenio.fecha_firma.isoformat() == "2026-09-26"
    assert proceso_persistido.estado == EstadoProcesoFirmasConvenio.COMPLETADO.value
    assert proceso_persistido.completado_en is not None
    assert proceso_persistido.version_convenio_id == escenario_final["version"].id
    historial = db.scalar(
        select(HistorialEtapa)
        .where(
            HistorialEtapa.convenio_id == convenio.id,
            HistorialEtapa.etapa_destino_id == convenio.etapa_actual_id,
        )
        .order_by(HistorialEtapa.id.desc())
    )
    assert historial is not None
    assert historial.etapa_origen.codigo == "APROBACION_FIRMAS"
    assert historial.usuario_id == escenario_final["gestor"].id
    assert historial.responsable_id == escenario_final["gestor"].id
    assert historial.observacion == (
        "Formalización del convenio tras completar las siete firmas obligatorias"
    )
    assert db.scalar(
        select(func.count()).select_from(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio.id
        )
    ) == versiones_antes
    seguimiento = client.get(f"/api/convenios/{convenio.id}/firmas")
    assert seguimiento.status_code == 200
    assert seguimiento.json()["estado"] == "COMPLETADO"


def test_electronica_sin_png_hash_bloquea_formalizacion(
    client, db, escenario_final
):
    proceso = _proceso_listo_para_formalizar(client, db, escenario_final)
    firma = db.get(FirmaConvenio, proceso["firmas"][0]["id"])
    assert firma is not None
    firma.modalidad = ModalidadFirma.ELECTRONICA.value
    firma.correo_firmante = "electronica@example.com"
    firma.documento_id = None
    firma.firma_png = None
    firma.firma_sha256 = None
    db.commit()
    assert _formalizar(client, escenario_final).status_code == 409


def test_fisica_sin_documento_bloquea_formalizacion(
    client, db, escenario_final
):
    proceso = _proceso_listo_para_formalizar(client, db, escenario_final)
    firma = db.get(FirmaConvenio, proceso["firmas"][0]["id"])
    assert firma is not None
    firma.documento_id = None
    db.commit()
    assert _formalizar(client, escenario_final).status_code == 409


def test_documento_fisico_de_otro_convenio_bloquea_formalizacion(
    client, db, escenario_final, crear_convenio
):
    proceso = _proceso_listo_para_formalizar(client, db, escenario_final)
    otro_convenio = crear_convenio(escenario_final["gestor"])
    documento = Documento(
        convenio_id=otro_convenio.id,
        tipo="CONVENIO_FIRMADO",
        nombre_archivo="ajeno.pdf",
        ruta_almacenamiento=f"pruebas/{uuid4().hex}.pdf",
        tipo_mime="application/pdf",
        tamano_bytes=20,
        es_vigente=True,
        cargado_por_id=escenario_final["gestor"].id,
    )
    db.add(documento)
    db.flush()
    firma = db.get(FirmaConvenio, proceso["firmas"][0]["id"])
    assert firma is not None
    firma.documento_id = documento.id
    db.commit()
    assert _formalizar(client, escenario_final).status_code == 409


def test_documento_fisico_de_tipo_incorrecto_bloquea_formalizacion(
    client, db, escenario_final
):
    proceso = _proceso_listo_para_formalizar(client, db, escenario_final)
    firma = db.get(FirmaConvenio, proceso["firmas"][0]["id"])
    assert firma is not None and firma.documento_id is not None
    documento = db.get(Documento, firma.documento_id)
    assert documento is not None
    documento.tipo = "SOPORTE"
    db.commit()
    assert _formalizar(client, escenario_final).status_code == 409


def test_observaciones_pendientes_bloquean_formalizacion(
    client, db, escenario_final
):
    _proceso_listo_para_formalizar(client, db, escenario_final)
    db.add(
        ObservacionRevision(
            convenio_id=escenario_final["convenio"].id,
            historial_etapa_id=escenario_final["historial"].id,
            revision_convenio_id=escenario_final["revision_final"].id,
            origen=OrigenObservacionRevision.REVISION_FINAL_ORI.value,
            registrada_por_id=escenario_final["gestor"].id,
            responsable_id=escenario_final["gestor"].id,
            descripcion="Pendiente antes de formalizar",
            estado="PENDIENTE",
        )
    )
    db.commit()
    assert _formalizar(client, escenario_final).status_code == 409


def test_revision_final_no_aprobada_bloquea_formalizacion(
    client, db, escenario_final
):
    _proceso_listo_para_formalizar(client, db, escenario_final)
    revision = db.get(RevisionConvenio, escenario_final["revision_final"].id)
    assert revision is not None
    revision.resultado = ResultadoRevisionConvenio.DEVUELTA.value
    db.commit()
    assert _formalizar(client, escenario_final).status_code == 409


def test_revisor_no_puede_formalizar(
    client, db, crear_usuario, entrar_como, escenario_final
):
    _proceso_listo_para_formalizar(client, db, escenario_final)
    entrar_como(crear_usuario(CodigoRol.REVISOR_ORI))
    assert _formalizar(client, escenario_final).status_code == 403


def test_segunda_formalizacion_es_rechazada(client, db, escenario_final):
    _proceso_listo_para_formalizar(client, db, escenario_final)
    assert _formalizar(client, escenario_final).status_code == 200
    assert _formalizar(client, escenario_final).status_code == 409


def test_formalizacion_crea_y_asocia_aliado(client, db, escenario_final):
    identificacion = str(900000000 + uuid4().int % 99999999)
    _proceso_listo_para_formalizar(
        client, db, escenario_final, identificacion=identificacion
    )
    assert _formalizar(client, escenario_final).status_code == 200
    db.expire_all()
    convenio = db.get(Convenio, escenario_final["convenio"].id)
    aliado = db.scalar(
        select(Aliado).where(Aliado.identificacion == identificacion)
    )
    assert convenio is not None and aliado is not None
    assert convenio.aliado_id == aliado.id
    assert convenio.solicitud.aliado_id == aliado.id


@pytest.mark.parametrize("activo", [True, False])
def test_formalizacion_reutiliza_y_reactiva_aliado_si_es_necesario(
    client, db, escenario_final, activo
):
    identificacion = str(900000000 + uuid4().int % 99999999)
    aliado = Aliado(
        nombre="Aliado existente HU-15",
        tipo=TipoAliado.UNIVERSIDAD.value,
        tipo_identificacion=TipoIdentificacion.NIT.value,
        identificacion=identificacion,
        correo="anterior@example.com",
        activo=activo,
    )
    db.add(aliado)
    db.commit()
    _proceso_listo_para_formalizar(
        client, db, escenario_final, identificacion=identificacion
    )

    assert _formalizar(client, escenario_final).status_code == 200
    db.expire_all()
    convenio = db.get(Convenio, escenario_final["convenio"].id)
    persistido = db.get(Aliado, aliado.id)
    assert convenio is not None and persistido is not None
    assert convenio.aliado_id == aliado.id
    assert convenio.solicitud.aliado_id == aliado.id
    assert persistido.activo is True
    assert db.scalar(
        select(func.count()).select_from(Aliado).where(
            Aliado.tipo_identificacion == TipoIdentificacion.NIT.value,
            Aliado.identificacion == identificacion,
        )
    ) == 1


@pytest.mark.parametrize(
    "accion",
    [
        ("GET", "/revision-final"),
        ("POST", "/revision-final/aprobar"),
        ("POST", "/revision-final/devolver"),
        ("GET", "/firmas"),
        ("POST", "/firmas/enviar"),
        ("POST", "/firmas/iniciar"),
        ("POST", "/firmas/1/reenviar"),
    ],
)
def test_revisor_ori_no_puede_gestionar_revision_final_ni_firmas(
    client, crear_usuario, entrar_como, escenario_final, accion
):
    revisor = crear_usuario(CodigoRol.REVISOR_ORI)
    entrar_como(revisor)
    metodo, ruta = accion
    url = f"/api/convenios/{escenario_final['convenio'].id}{ruta}"
    datos = {
        "expected_version": escenario_final["version"].numero,
        "observaciones": ["No autorizado"],
    }
    respuesta = client.request(metodo, url, json=datos if metodo == "POST" else None)
    assert respuesta.status_code == 403


def test_estructura_invitacion_no_almacena_token_plano(db):
    columnas = InvitacionFirmaConvenio.__table__.columns
    assert "token_hash" in columnas
    assert "token" not in columnas


def test_todas_las_firmas_dependen_del_proceso_y_no_del_convenio():
    columnas = FirmaConvenio.__table__.columns
    assert "proceso_firmas_id" in columnas
    assert "convenio_id" not in columnas
    assert EstadoFirmaConvenio.PENDIENTE.value == "PENDIENTE"
    assert set(ROLES_ESPERADOS) == {rol.value for rol in RolFirmanteConvenio}


def _iniciar_con_invitaciones(
    client, correo_local, escenario_final, electronicas: int = 2
):
    proceso = _aprobar(client, escenario_final).json()
    for indice, firma in enumerate(proceso["firmas"]):
        modalidad = "ELECTRONICA" if indice < electronicas else "FISICA"
        respuesta = _configurar(
            client,
            escenario_final["convenio"].id,
            firma["id"],
            modalidad=modalidad,
        )
        assert respuesta.status_code == 200
    inicio = client.post(
        f"/api/convenios/{escenario_final['convenio'].id}/firmas/iniciar"
    )
    assert inicio.status_code == 200
    envio = client.post(
        f"/api/convenios/{escenario_final['convenio'].id}/firmas/enviar"
    )
    assert envio.status_code == 200
    assert len(correo_local.mensajes) == electronicas
    tokens = [_token_mensaje(mensaje) for mensaje in correo_local.mensajes]
    return envio.json(), tokens


def test_envio_crea_invitaciones_independientes_solo_para_electronicas(
    client, db, correo_local, escenario_final
):
    proceso, tokens = _iniciar_con_invitaciones(
        client, correo_local, escenario_final
    )

    assert len(tokens) == 2
    assert tokens[0] != tokens[1]
    assert all("#token=" in mensaje.texto for mensaje in correo_local.mensajes)
    assert all(not mensaje.cc for mensaje in correo_local.mensajes)
    assert all(
        "firma electrónica" in mensaje.texto.lower()
        and "elaboración de convenio" in mensaje.texto.lower()
        for mensaje in correo_local.mensajes
    )
    assert all(len(firma["invitaciones"]) == 1 for firma in proceso["firmas"][:2])
    assert all(not firma["invitaciones"] for firma in proceso["firmas"][2:])
    hashes = list(db.scalars(select(InvitacionFirmaConvenio.token_hash)))
    assert sha256(tokens[0].encode()).hexdigest() in hashes
    assert tokens[0] not in hashes


def test_envio_reporta_firmas_con_fallo_de_entrega(
    client, db, escenario_final
):
    proceso = _aprobar(client, escenario_final).json()
    for indice, firma in enumerate(proceso["firmas"]):
        modalidad = "ELECTRONICA" if indice == 0 else "FISICA"
        assert _configurar(
            client,
            escenario_final["convenio"].id,
            firma["id"],
            modalidad=modalidad,
        ).status_code == 200
    assert client.post(
        f"/api/convenios/{escenario_final['convenio'].id}/firmas/iniciar"
    ).status_code == 200

    class CorreoFallido:
        def enviar(self, mensaje) -> None:
            raise ErrorEnvioCorreo("fallo controlado")

    app.dependency_overrides[get_enviador_correo] = CorreoFallido
    respuesta = client.post(
        f"/api/convenios/{escenario_final['convenio'].id}/firmas/enviar"
    )

    assert respuesta.status_code == 502
    assert respuesta.json()["detail"]["firmas_fallidas"] == [
        proceso["firmas"][0]["id"]
    ]
    invitacion = db.scalar(
        select(InvitacionFirmaConvenio).where(
            InvitacionFirmaConvenio.firma_convenio_id
            == proceso["firmas"][0]["id"]
        )
    )
    assert invitacion is not None and invitacion.enviado_en is None


def test_acceso_valido_no_consume_y_no_expone_token_ni_hash(
    client, db, correo_local, escenario_final
):
    proceso, tokens = _iniciar_con_invitaciones(
        client, correo_local, escenario_final, electronicas=1
    )
    respuesta = client.post(
        "/api/public/firma-convenio/acceso", json={"token": tokens[0]}
    )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["nombre_firmante"] == proceso["firmas"][0]["nombre_firmante"]
    assert datos["contenido"] == escenario_final["version"].contenido
    assert "token" not in respuesta.text.lower()
    assert "hash" not in respuesta.text.lower()
    invitacion = db.scalar(
        select(InvitacionFirmaConvenio).where(
            InvitacionFirmaConvenio.token_hash
            == sha256(tokens[0].encode()).hexdigest()
        )
    )
    assert invitacion is not None and invitacion.utilizado_en is None


def test_token_invalido_es_rechazado(client):
    respuesta = client.post(
        "/api/public/firma-convenio/acceso", json={"token": "x" * 48}
    )
    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "ENLACE_INVALIDO"


@pytest.mark.parametrize(
    ("cambio", "codigo"),
    [
        ("expirada", "ENLACE_EXPIRADO"),
        ("revocada", "ENLACE_NO_DISPONIBLE"),
        ("utilizada", "FIRMA_YA_REGISTRADA"),
    ],
)
def test_estados_no_disponibles_del_token(
    client, db, correo_local, escenario_final, cambio, codigo
):
    _, tokens = _iniciar_con_invitaciones(
        client, correo_local, escenario_final, electronicas=1
    )
    invitacion = db.scalar(
        select(InvitacionFirmaConvenio).where(
            InvitacionFirmaConvenio.token_hash
            == sha256(tokens[0].encode()).hexdigest()
        )
    )
    assert invitacion is not None
    if cambio == "expirada":
        invitacion.expira_en = datetime.now(UTC) - timedelta(seconds=1)
    elif cambio == "revocada":
        invitacion.revocado_en = datetime.now(UTC)
    else:
        invitacion.utilizado_en = datetime.now(UTC)
    db.commit()

    respuesta = client.post(
        "/api/public/firma-convenio/acceso", json={"token": tokens[0]}
    )
    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == codigo


def test_firmar_consumo_atomico_guarda_evidencia_y_rechaza_replay(
    client, db, correo_local, escenario_final
):
    proceso, tokens = _iniciar_con_invitaciones(
        client, correo_local, escenario_final, electronicas=1
    )
    ruta = "/api/public/firma-convenio/firmar"
    respuesta = client.post(
        ruta,
        json={"token": tokens[0], "firma": FIRMA_PNG, "confirmacion": True},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "FIRMADA"
    db.expire_all()
    firma = db.get(FirmaConvenio, proceso["firmas"][0]["id"])
    assert firma is not None
    assert firma.estado == EstadoFirmaConvenio.FIRMADA.value
    assert firma.fecha_firma is not None
    assert firma.firma_png is not None
    assert firma.firma_sha256 == sha256(firma.firma_png).hexdigest()
    assert db.get(ProcesoFirmasConvenio, proceso["id"]).estado == "EN_CURSO"
    assert escenario_final["convenio"].estado == EstadoConvenio.EN_TRAMITE.value

    replay = client.post(
        ruta,
        json={"token": tokens[0], "firma": FIRMA_PNG, "confirmacion": True},
    )
    assert replay.status_code == 400
    assert replay.json()["detail"]["codigo"] == "FIRMA_YA_REGISTRADA"


def test_firmar_valida_confirmacion_png_y_tamano(
    client, correo_local, escenario_final
):
    _, tokens = _iniciar_con_invitaciones(
        client, correo_local, escenario_final, electronicas=1
    )
    ruta = "/api/public/firma-convenio/firmar"
    assert client.post(
        ruta,
        json={"token": tokens[0], "firma": FIRMA_PNG, "confirmacion": False},
    ).status_code == 422
    assert client.post(
        ruta,
        json={"token": tokens[0], "firma": "data:image/png;base64,%%%", "confirmacion": True},
    ).status_code == 422
    grande = "data:image/png;base64," + base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + b"x" * MAX_FIRMA_PNG_BYTES
    ).decode()
    assert client.post(
        ruta,
        json={"token": tokens[0], "firma": grande, "confirmacion": True},
    ).status_code == 422


def test_reenvio_revoca_token_anterior_sin_crear_otra_firma(
    client, db, correo_local, escenario_final
):
    proceso, tokens = _iniciar_con_invitaciones(
        client, correo_local, escenario_final, electronicas=1
    )
    firma_id = proceso["firmas"][0]["id"]
    conteo_antes = db.scalar(select(func.count()).select_from(FirmaConvenio))
    respuesta = client.post(
        f"/api/convenios/{escenario_final['convenio'].id}/firmas/{firma_id}/reenviar"
    )
    assert respuesta.status_code == 200
    token_nuevo = _token_mensaje(correo_local.mensajes[-1])
    assert token_nuevo != tokens[0]
    assert client.post(
        "/api/public/firma-convenio/acceso", json={"token": tokens[0]}
    ).json()["detail"]["codigo"] == "ENLACE_NO_DISPONIBLE"
    assert client.post(
        "/api/public/firma-convenio/acceso", json={"token": token_nuevo}
    ).status_code == 200
    assert db.scalar(select(func.count()).select_from(FirmaConvenio)) == conteo_antes


def test_tokens_independientes_firmar_una_no_afecta_otra(
    client, db, correo_local, escenario_final
):
    proceso, tokens = _iniciar_con_invitaciones(
        client, correo_local, escenario_final, electronicas=2
    )
    respuesta = client.post(
        "/api/public/firma-convenio/firmar",
        json={"token": tokens[0], "firma": FIRMA_PNG, "confirmacion": True},
    )
    assert respuesta.status_code == 200
    db.expire_all()
    primera = db.get(FirmaConvenio, proceso["firmas"][0]["id"])
    segunda = db.get(FirmaConvenio, proceso["firmas"][1]["id"])
    assert primera.estado == "FIRMADA"
    assert segunda.estado == "PENDIENTE"
    assert segunda.fecha_firma is None and segunda.firma_png is None
    assert client.post(
        "/api/public/firma-convenio/acceso", json={"token": tokens[1]}
    ).status_code == 200


def test_proceso_detenido_y_firma_fisica_bloquean_firma_electronica(
    client, db, correo_local, escenario_final
):
    proceso, tokens = _iniciar_con_invitaciones(
        client, correo_local, escenario_final, electronicas=1
    )
    entidad = db.get(ProcesoFirmasConvenio, proceso["id"])
    entidad.estado = EstadoProcesoFirmasConvenio.CONFIGURACION.value
    db.commit()
    respuesta = client.post(
        "/api/public/firma-convenio/firmar",
        json={"token": tokens[0], "firma": FIRMA_PNG, "confirmacion": True},
    )
    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "ENLACE_NO_DISPONIBLE"

    entidad.estado = EstadoProcesoFirmasConvenio.EN_CURSO.value
    firma = db.get(FirmaConvenio, proceso["firmas"][0]["id"])
    firma.modalidad = ModalidadFirma.FISICA.value
    db.commit()
    respuesta = client.post(
        "/api/public/firma-convenio/firmar",
        json={"token": tokens[0], "firma": FIRMA_PNG, "confirmacion": True},
    )
    assert respuesta.status_code == 400
    assert respuesta.json()["detail"]["codigo"] == "ENLACE_NO_DISPONIBLE"


def _crear_invitacion_concurrente(db_engine):
    escenario = _crear_escenario_concurrente(db_engine)
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    correo = CorreoLocal()
    with fabrica() as sesion:
        gestor = sesion.get(Usuario, int(escenario["gestor_id"]))
        proceso = ServicioFirmas(sesion).aprobar_revision_final(
            int(escenario["convenio_id"]),
            int(escenario["version_numero"]),
            gestor,
        )
        for indice, firma in enumerate(proceso.firmas):
            modalidad = (
                ModalidadFirma.ELECTRONICA
                if indice == 0
                else ModalidadFirma.FISICA
            )
            ServicioFirmas(sesion).configurar_firma(
                int(escenario["convenio_id"]),
                firma.id,
                f"Firmante {firma.id}",
                "Cargo institucional",
                "firma@example.com" if indice == 0 else None,
                modalidad,
            )
        ServicioFirmas(sesion).iniciar(int(escenario["convenio_id"]))
        proceso = ServicioFirmaElectronica(
            sesion, correo, FRONTEND_URL
        ).enviar_invitaciones(int(escenario["convenio_id"]), gestor)
        escenario["firma_id"] = proceso.firmas[0].id
    escenario["token"] = _token_mensaje(correo.mensajes[0])
    return escenario


def test_firmas_concurrentes_solo_registran_una_evidencia(db_engine):
    escenario = _crear_invitacion_concurrente(db_engine)
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    barrera = Barrier(2)

    def firmar() -> str:
        with fabrica() as sesion:
            barrera.wait(timeout=10)
            try:
                ServicioFirmaElectronica(sesion).firmar(
                    str(escenario["token"]), FIRMA_PNG, True
                )
                return "FIRMADA"
            except EnlaceFirmaConvenioError as exc:
                return exc.codigo

    try:
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(lambda _: firmar(), range(2)))
        assert sorted(resultados) == ["FIRMADA", "FIRMA_YA_REGISTRADA"]
        with fabrica() as verificacion:
            firma = verificacion.get(FirmaConvenio, int(escenario["firma_id"]))
            assert firma.estado == "FIRMADA"
            assert firma.firma_png is not None and firma.firma_sha256 is not None
            assert verificacion.scalar(
                select(func.count())
                .select_from(InvitacionFirmaConvenio)
                .where(
                    InvitacionFirmaConvenio.firma_convenio_id == firma.id,
                    InvitacionFirmaConvenio.utilizado_en.is_not(None),
                )
            ) == 1
    finally:
        _limpiar_escenario_concurrente(db_engine, escenario)


def test_firmar_vs_reenviar_concurrente_deja_un_resultado_coherente(db_engine):
    escenario = _crear_invitacion_concurrente(db_engine)
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    barrera = Barrier(2)

    def firmar() -> str:
        with fabrica() as sesion:
            barrera.wait(timeout=10)
            try:
                ServicioFirmaElectronica(sesion).firmar(
                    str(escenario["token"]), FIRMA_PNG, True
                )
                return "FIRMADA"
            except EnlaceFirmaConvenioError:
                return "RECHAZADA"

    def reenviar() -> str:
        with fabrica() as sesion:
            gestor = sesion.get(Usuario, int(escenario["gestor_id"]))
            barrera.wait(timeout=10)
            try:
                ServicioFirmaElectronica(
                    sesion, CorreoLocal(), FRONTEND_URL
                ).reenviar(
                    int(escenario["convenio_id"]),
                    int(escenario["firma_id"]),
                    gestor,
                )
                return "REENVIADA"
            except RevisionNoDisponible:
                return "RECHAZADA"

    try:
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            futuro_firma = ejecutor.submit(firmar)
            futuro_reenvio = ejecutor.submit(reenviar)
            resultados = {futuro_firma.result(), futuro_reenvio.result()}
        assert resultados in (
            {"FIRMADA", "RECHAZADA"},
            {"REENVIADA", "RECHAZADA"},
        )
        with fabrica() as verificacion:
            firma = verificacion.get(FirmaConvenio, int(escenario["firma_id"]))
            activas = verificacion.scalar(
                select(func.count())
                .select_from(InvitacionFirmaConvenio)
                .where(
                    InvitacionFirmaConvenio.firma_convenio_id == firma.id,
                    InvitacionFirmaConvenio.utilizado_en.is_(None),
                    InvitacionFirmaConvenio.revocado_en.is_(None),
                )
            )
            if firma.estado == "FIRMADA":
                assert activas == 0
            else:
                assert firma.estado == "PENDIENTE" and activas == 1
    finally:
        _limpiar_escenario_concurrente(db_engine, escenario)


def test_formalizaciones_concurrentes_producen_un_unico_cierre(db_engine):
    escenario = _crear_escenario_concurrente(db_engine)
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    with fabrica() as sesion:
        gestor = sesion.get(Usuario, int(escenario["gestor_id"]))
        assert gestor is not None
        proceso = ServicioFirmas(sesion).aprobar_revision_final(
            int(escenario["convenio_id"]),
            int(escenario["version_numero"]),
            gestor,
        )
        for firma in proceso.firmas:
            ServicioFirmas(sesion).configurar_firma(
                int(escenario["convenio_id"]),
                firma.id,
                f"Firmante {firma.id}",
                "Cargo institucional",
                None,
                ModalidadFirma.FISICA,
            )
        proceso = ServicioFirmas(sesion).iniciar(int(escenario["convenio_id"]))
        documento = Documento(
            convenio_id=int(escenario["convenio_id"]),
            tipo="CONVENIO_FIRMADO",
            nombre_archivo="concurrente.pdf",
            ruta_almacenamiento=f"pruebas/{uuid4().hex}.pdf",
            tipo_mime="application/pdf",
            tamano_bytes=20,
            es_vigente=True,
            cargado_por_id=gestor.id,
        )
        sesion.add(documento)
        sesion.flush()
        for firma in proceso.firmas:
            firma.estado = EstadoFirmaConvenio.FIRMADA.value
            firma.fecha_firma = datetime.now(UTC)
            firma.documento_id = documento.id
        sesion.commit()
        escenario["proceso_id"] = proceso.id

    barrera = Barrier(2)

    def formalizar() -> str:
        with fabrica() as sesion:
            gestor = sesion.get(Usuario, int(escenario["gestor_id"]))
            assert gestor is not None
            barrera.wait(timeout=10)
            try:
                ServicioFirmas(sesion).formalizar(
                    int(escenario["convenio_id"]), gestor
                )
                return "COMPLETADO"
            except RevisionNoDisponible:
                return "CONFLICTO"

    try:
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(lambda _: formalizar(), range(2)))
        assert sorted(resultados) == ["COMPLETADO", "CONFLICTO"]
        with fabrica() as verificacion:
            convenio = verificacion.get(Convenio, int(escenario["convenio_id"]))
            proceso = verificacion.get(
                ProcesoFirmasConvenio, int(escenario["proceso_id"])
            )
            assert convenio is not None and proceso is not None
            assert convenio.estado == EstadoConvenio.VIGENTE.value
            assert proceso.estado == EstadoProcesoFirmasConvenio.COMPLETADO.value
            assert verificacion.scalar(
                select(func.count()).select_from(HistorialEtapa).where(
                    HistorialEtapa.convenio_id == convenio.id,
                    HistorialEtapa.observacion
                    == "Formalización del convenio tras completar las siete firmas obligatorias",
                )
            ) == 1
            assert convenio.aliado_id is not None
            assert verificacion.scalar(
                select(func.count()).select_from(Aliado).where(
                    Aliado.id == convenio.aliado_id
                )
            ) == 1
    finally:
        _limpiar_escenario_concurrente(db_engine, escenario)
