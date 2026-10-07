"""Recorrido canónico completo del Sprint 2 exclusivamente mediante APIs."""

import base64
import struct
import zlib
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.enums import EstadoFirmaConvenio
from backend.models.firma_convenio import FirmaConvenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.version_convenio import VersionConvenio


def _datos_solicitud(tipo_convenio_id: int, unico: str) -> dict[str, object]:
    return {
        "nombre_aliado_propuesto": f"Universidad E2E {unico}",
        "tipo_identificacion_aliado_propuesto": "NIT",
        "identificacion_aliado_propuesto": f"9{unico[:15]}",
        "tipo_aliado_propuesto": "UNIVERSIDAD",
        "correo_aliado_propuesto": f"convenios-{unico}@example.com",
        "pais_aliado_propuesto": "Colombia",
        "ciudad_aliado_propuesto": "Cali",
        "telefono_aliado_propuesto": "6025550101",
        "direccion_aliado_propuesto": "Calle 1 # 2-3",
        "sector_economico_aliado_propuesto": "Educación",
        "contacto_contraparte_nombre": "Ana Contraparte",
        "contacto_contraparte_cargo": "Directora de Cooperación",
        "contacto_contraparte_telefono": "3001234567",
        "contacto_contraparte_correo": f"contacto-{unico}@example.com",
        "tipo_convenio_id": tipo_convenio_id,
        "justificacion": "Fortalecer la cooperación académica internacional",
        "objeto": "Desarrollar actividades de cooperación académica",
        "actividades_por_parte": "Intercambios y proyectos conjuntos",
        "metas_esperadas": "Dos proyectos conjuntos durante la vigencia",
        "implicacion_financiera": "Sin erogación presupuestal inicial",
        "vigencia_estimada": "24 meses",
        "requisitos_renovacion": "Evaluación y acuerdo escrito",
        "supervisor_usb_nombre": "Carlos Supervisor",
        "supervisor_usb_cargo": "Coordinador ORI",
        "supervisor_usb_telefono": "6025550202",
        "supervisor_usb_correo": f"supervisor-usb-{unico}@example.com",
        "supervisor_contraparte_nombre": "María Supervisora",
        "supervisor_contraparte_cargo": "Coordinadora Internacional",
        "supervisor_contraparte_telefono": "3005550303",
        "supervisor_contraparte_correo": f"supervisor-ext-{unico}@example.com",
    }


def _anadir_parrafo(contenido: dict, texto: str) -> dict:
    actualizado = deepcopy(contenido)
    actualizado.setdefault("content", []).append(
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": texto}],
        }
    )
    return actualizado


def _token_de_correo(mensaje) -> str:
    marcador = "/firma-convenio#token="
    assert marcador in mensaje.texto
    return mensaje.texto.split(marcador, 1)[1].splitlines()[0]


def _firma_png() -> str:
    def chunk(tipo: bytes, datos: bytes) -> bytes:
        crc = zlib.crc32(tipo)
        crc = zlib.crc32(datos, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", 2, 1, 8, 6, 0, 0, 0)
    filas = b"\x00" + b"\x00\x00\x00\xff" * 2
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(filas))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode()


def _revision_juridica_pendiente(client, convenio_id: int) -> dict:
    respuesta = client.get("/api/convenios/revisiones-juridicas/pendientes")
    assert respuesta.status_code == 200, respuesta.text
    coincidencias = [
        item for item in respuesta.json() if item["convenio_id"] == convenio_id
    ]
    assert len(coincidencias) == 1
    return coincidencias[0]


def _es_subsecuencia(valores: list[str], esperados: list[str]) -> bool:
    posicion = 0
    for valor in valores:
        if posicion < len(esperados) and valor == esperados[posicion]:
            posicion += 1
    return posicion == len(esperados)


def test_e2e_flujo_canonico_sprint2_por_api(
    client, db, crear_usuario, entrar_como, correo_local
) -> None:
    unico = uuid4().hex
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    assert tipo is not None
    solicitante = crear_usuario(
        CodigoRol.SOLICITANTE_EXTERNO,
        TipoUsuario.EXTERNO,
        correo=f"solicitante-e2e-{unico}@example.com",
    )
    solicitante.documento_identidad = f"CE-{unico[:20]}"
    solicitante.entidad_externa = f"Fundación E2E {unico[:8]}"
    gestor = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    revisor_a = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    revisor_b = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    administrador = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    db.commit()

    # Fases 1-2: solicitud, radicación, devolución, corrección y re-radicación.
    entrar_como(solicitante)
    creada = client.post("/api/solicitudes", json=_datos_solicitud(tipo.id, unico))
    assert creada.status_code == 201, creada.text
    solicitud_id = creada.json()["id"]
    assert creada.json()["solicitante_id"] == solicitante.id
    soporte = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": "RUT"},
        files={
            "archivo": (
                "rut-inicial.pdf",
                b"%PDF-1.4 soporte inicial E2E",
                "application/pdf",
            )
        },
    )
    assert soporte.status_code == 201, soporte.text
    radicada = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert radicada.status_code == 200, radicada.text
    assert radicada.json()["estado"] == "RADICADA"
    assert db.scalar(
        select(Convenio).where(Convenio.solicitud_id == solicitud_id)
    ) is None

    entrar_como(gestor)
    recibida = client.get(f"/api/solicitudes/recibidas/{solicitud_id}")
    assert recibida.status_code == 200, recibida.text
    devuelta = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/devolver",
        json={"observaciones": "Corregir el objeto y reemplazar el soporte RUT"},
    )
    assert devuelta.status_code == 200, devuelta.text
    assert devuelta.json()["estado"] == "DEVUELTA"
    assert "reemplazar" in devuelta.json()["observaciones_devolucion"]
    assert db.scalar(
        select(Convenio).where(Convenio.solicitud_id == solicitud_id)
    ) is None

    entrar_como(solicitante)
    propia = client.get(f"/api/solicitudes/{solicitud_id}")
    assert propia.status_code == 200, propia.text
    assert propia.json()["observaciones_devolucion"] == (
        devuelta.json()["observaciones_devolucion"]
    )
    corregida = client.patch(
        f"/api/solicitudes/{solicitud_id}",
        json={"objeto": "Objeto corregido y validado para el flujo E2E"},
    )
    assert corregida.status_code == 200, corregida.text
    eliminado = client.delete(
        f"/api/solicitudes/{solicitud_id}/documentos/{soporte.json()['id']}"
    )
    assert eliminado.status_code == 204, eliminado.text
    db.expire_all()
    reemplazo = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": "RUT"},
        files={
            "archivo": (
                "rut-corregido.pdf",
                b"%PDF-1.4 soporte corregido E2E",
                "application/pdf",
            )
        },
    )
    assert reemplazo.status_code == 201, reemplazo.text
    reradicada = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert reradicada.status_code == 200, reradicada.text
    assert reradicada.json()["estado"] == "RADICADA"
    assert reradicada.json()["observaciones_devolucion"] == (
        devuelta.json()["observaciones_devolucion"]
    )
    assert db.scalar(
        select(Convenio).where(Convenio.solicitud_id == solicitud_id)
    ) is None

    # Fases 3-4: aceptación, inicio, edición versionada y finalización.
    entrar_como(gestor)
    aceptada = client.post(f"/api/solicitudes/recibidas/{solicitud_id}/aceptar")
    assert aceptada.status_code == 200, aceptada.text
    assert aceptada.json()["estado"] == "APROBADA"
    assert db.scalar(
        select(Convenio).where(Convenio.solicitud_id == solicitud_id)
    ) is None
    iniciada = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/iniciar-elaboracion"
    )
    assert iniciada.status_code == 200, iniciada.text
    convenio_id = iniciada.json()["id"]
    assert iniciada.json()["estado"] == "EN_TRAMITE"
    assert iniciada.json()["solicitud_id"] == solicitud_id
    db.expire_all()
    assert db.get(Convenio, convenio_id).etapa_actual.codigo == "ELABORACION"
    assert db.scalar(
        select(func.count()).select_from(Convenio).where(
            Convenio.solicitud_id == solicitud_id
        )
    ) == 1

    elaboracion = client.get(f"/api/convenios/{convenio_id}/elaboracion")
    assert elaboracion.status_code == 200, elaboracion.text
    contenido_editado = _anadir_parrafo(
        elaboracion.json()["contenido"], "Edición inicial reconocible del E2E"
    )
    guardada = client.patch(
        f"/api/convenios/{convenio_id}/elaboracion",
        json={
            "contenido": contenido_editado,
            "expected_version": elaboracion.json()["version_actual"],
            "tipo_convenio_id": tipo.id,
            "objeto": "Convenio canónico completo del Sprint 2",
            "alcance": "INSTITUCIONAL",
            "implicacion_financiera": "Sin erogación presupuestal",
            "duracion_meses": 24,
        },
    )
    assert guardada.status_code == 200, guardada.text
    assert guardada.json()["version_actual"] > elaboracion.json()["version_actual"]
    finalizada = client.post(
        f"/api/convenios/{convenio_id}/elaboracion/finalizar",
        json={"expected_version": guardada.json()["version_actual"]},
    )
    assert finalizada.status_code == 200, finalizada.text
    db.expire_all()
    assert db.get(Convenio, convenio_id).etapa_actual.codigo == (
        "REVISION_AVAL_JURIDICO"
    )
    # Fases 5-6: RJ1 aprueba; RJ2 edita y no puede mezclar versiones.
    entrar_como(revisor_a)
    rj1_ronda1 = _revision_juridica_pendiente(client, convenio_id)
    assert (rj1_ronda1["instancia_juridica"], rj1_ronda1["numero_ronda"]) == (1, 1)
    detalle_rj1 = client.get(f"/api/convenios/{convenio_id}/revision")
    assert detalle_rj1.status_code == 200, detalle_rj1.text
    aprobacion_rj1 = client.post(
        f"/api/convenios/{convenio_id}/revisiones/{rj1_ronda1['revision_id']}/aprobar",
        json={"expected_version": detalle_rj1.json()["version_actual"]["numero"]},
    )
    assert aprobacion_rj1.status_code == 200, aprobacion_rj1.text
    assert aprobacion_rj1.json()["resultado"] == "APROBADA"
    assert aprobacion_rj1.json()["version_resultado_id"] is not None
    assert not any(
        item["convenio_id"] == convenio_id
        for item in client.get(
            "/api/convenios/revisiones-juridicas/pendientes"
        ).json()
    )

    entrar_como(revisor_b)
    rj2_ronda1 = _revision_juridica_pendiente(client, convenio_id)
    assert (rj2_ronda1["instancia_juridica"], rj2_ronda1["numero_ronda"]) == (2, 1)
    detalle_rj2 = client.get(f"/api/convenios/{convenio_id}/revision")
    assert detalle_rj2.status_code == 200, detalle_rj2.text
    version_avalada_rj1 = aprobacion_rj1.json()["version_resultado_id"]
    edicion_rj2 = client.patch(
        f"/api/convenios/{convenio_id}/revisiones/{rj2_ronda1['revision_id']}/contenido",
        json={
            "contenido": _anadir_parrafo(
                detalle_rj2.json()["version_actual"]["contenido"],
                "Cambio realizado durante RJ2 en E2E",
            ),
            "expected_version": detalle_rj2.json()["version_actual"]["numero"],
        },
    )
    assert edicion_rj2.status_code == 200, edicion_rj2.text
    assert edicion_rj2.json()["id"] != version_avalada_rj1
    mezcla = client.post(
        f"/api/convenios/{convenio_id}/revisiones/{rj2_ronda1['revision_id']}/aprobar",
        json={"expected_version": edicion_rj2.json()["numero"]},
    )
    assert mezcla.status_code == 409, mezcla.text
    assert "reiniciar" in mezcla.text.lower()
    db.expire_all()
    primera_historica = db.get(RevisionConvenio, rj1_ronda1["revision_id"])
    segunda_pendiente = db.get(RevisionConvenio, rj2_ronda1["revision_id"])
    convenio = db.get(Convenio, convenio_id)
    assert primera_historica.resultado == "APROBADA"
    assert primera_historica.version_resultado_id == version_avalada_rj1
    assert segunda_pendiente.estado == "PENDIENTE"
    assert segunda_pendiente.version_resultado_id is None
    assert convenio.etapa_actual.codigo == "REVISION_AVAL_JURIDICO"
    assert not db.scalars(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_id,
            RevisionConvenio.tipo == "CONTRAPARTE",
        )
    ).all()

    # Fases 7-8: devolución, corrección adicional y nueva ronda consistente.
    devolucion_rj2 = client.post(
        f"/api/convenios/{convenio_id}/revisiones/{rj2_ronda1['revision_id']}/devolver",
        json={
            "expected_version": edicion_rj2.json()["numero"],
            "observaciones": [
                "El contenido cambió después del primer aval y requiere una nueva ronda jurídica."
            ],
        },
    )
    assert devolucion_rj2.status_code == 200, devolucion_rj2.text
    assert devolucion_rj2.json()["resultado"] == "DEVUELTA"
    db.expire_all()
    assert db.get(Convenio, convenio_id).etapa_actual.codigo == "ELABORACION"

    entrar_como(gestor)
    historial_api = client.get(f"/api/convenios/{convenio_id}/revisiones")
    assert historial_api.status_code == 200, historial_api.text
    revision_devuelta = next(
        item
        for item in historial_api.json()["revisiones"]
        if item["id"] == rj2_ronda1["revision_id"]
    )
    assert len(revision_devuelta["observaciones"]) == 1
    observacion_id = revision_devuelta["observaciones"][0]["id"]
    atendida = client.patch(
        f"/api/convenios/{convenio_id}/observaciones/{observacion_id}/atender",
        json={"respuesta": "Se incorporó el cambio y se preparará una nueva versión."},
    )
    assert atendida.status_code == 200, atendida.text
    assert atendida.json()["estado"] == "ATENDIDA"
    elaboracion_corregida = client.get(f"/api/convenios/{convenio_id}/elaboracion")
    assert elaboracion_corregida.status_code == 200, elaboracion_corregida.text
    correccion = client.patch(
        f"/api/convenios/{convenio_id}/elaboracion",
        json={
            "contenido": _anadir_parrafo(
                elaboracion_corregida.json()["contenido"],
                "Corrección posterior a la devolución de RJ2 en E2E",
            ),
            "expected_version": elaboracion_corregida.json()["version_actual"],
        },
    )
    assert correccion.status_code == 200, correccion.text
    version_consistente = correccion.json()["version_actual"]
    assert version_consistente > edicion_rj2.json()["numero"]
    nueva_ronda = client.post(
        f"/api/convenios/{convenio_id}/elaboracion/finalizar",
        json={"expected_version": version_consistente},
    )
    assert nueva_ronda.status_code == 200, nueva_ronda.text

    entrar_como(revisor_a)
    rj1_ronda2 = _revision_juridica_pendiente(client, convenio_id)
    assert (rj1_ronda2["instancia_juridica"], rj1_ronda2["numero_ronda"]) == (1, 2)
    assert rj1_ronda2["version_numero"] == version_consistente
    aprobada_rj1_ronda2 = client.post(
        f"/api/convenios/{convenio_id}/revisiones/{rj1_ronda2['revision_id']}/aprobar",
        json={"expected_version": version_consistente},
    )
    assert aprobada_rj1_ronda2.status_code == 200, aprobada_rj1_ronda2.text

    entrar_como(revisor_b)
    rj2_ronda2 = _revision_juridica_pendiente(client, convenio_id)
    assert (rj2_ronda2["instancia_juridica"], rj2_ronda2["numero_ronda"]) == (2, 2)
    aprobada_rj2_ronda2 = client.post(
        f"/api/convenios/{convenio_id}/revisiones/{rj2_ronda2['revision_id']}/aprobar",
        json={"expected_version": version_consistente},
    )
    assert aprobada_rj2_ronda2.status_code == 200, aprobada_rj2_ronda2.text
    assert aprobada_rj1_ronda2.json()["version_resultado_id"] == (
        aprobada_rj2_ronda2.json()["version_resultado_id"]
    )
    version_aprobada_id = aprobada_rj2_ronda2.json()["version_resultado_id"]
    db.expire_all()
    assert db.get(Convenio, convenio_id).etapa_actual.codigo == "REVISION_CONTRAPARTE"

    # Fases 9-10: envío y decisión autenticada del Solicitante propietario.
    entrar_como(gestor)
    enviada = client.post(
        f"/api/convenios/{convenio_id}/revision-contraparte/enviar",
        json={"expected_version": version_consistente},
    )
    assert enviada.status_code == 201, enviada.text
    revision_contraparte_id = enviada.json()["id"]
    assert enviada.json()["estado"] == "PENDIENTE"
    assert enviada.json()["responsable"]["id"] == solicitante.id

    entrar_como(solicitante)
    pendientes = client.get("/api/convenios/revisiones-contraparte/pendientes")
    assert pendientes.status_code == 200, pendientes.text
    assert revision_contraparte_id in {
        item["revision_id"] for item in pendientes.json()
    }
    detalle_contraparte = client.get(
        f"/api/convenios/revisiones-contraparte/{revision_contraparte_id}"
    )
    assert detalle_contraparte.status_code == 200, detalle_contraparte.text
    assert detalle_contraparte.json()["version_recibida"]["id"] == version_aprobada_id
    contenido_aprobado = detalle_contraparte.json()["version_recibida"]["contenido"]
    decision_contraparte = client.post(
        f"/api/convenios/revisiones-contraparte/{revision_contraparte_id}/aprobar",
        json={"expected_version": version_consistente},
    )
    assert decision_contraparte.status_code == 200, decision_contraparte.text
    assert decision_contraparte.json()["resultado"] == "APROBADA"
    assert decision_contraparte.json()["version_resultado_id"] == version_aprobada_id
    pendientes_despues = client.get(
        "/api/convenios/revisiones-contraparte/pendientes"
    )
    assert revision_contraparte_id not in {
        item["revision_id"] for item in pendientes_despues.json()
    }
    db.expire_all()
    assert db.get(Convenio, convenio_id).etapa_actual.codigo == "REVISION_FINAL"

    # Fases 11-12: revisión final y documento aprobado congelado.
    entrar_como(administrador)
    revision_final = client.get(f"/api/convenios/{convenio_id}/revision-final")
    assert revision_final.status_code == 200, revision_final.text
    datos_final = revision_final.json()
    assert datos_final["version_aprobada_contraparte"]["id"] == version_aprobada_id
    assert datos_final["revision_contraparte"]["version_resultado_id"] == (
        version_aprobada_id
    )
    assert {
        item["version_resultado_id"] for item in datos_final["revisiones_juridicas"]
    } == {version_aprobada_id}
    assert not datos_final["observaciones_pendientes"]
    aprobacion_final = client.post(
        f"/api/convenios/{convenio_id}/revision-final/aprobar",
        json={"expected_version": version_consistente},
    )
    assert aprobacion_final.status_code == 201, aprobacion_final.text
    proceso = aprobacion_final.json()
    proceso_id = proceso["id"]
    assert proceso["estado"] == "CONFIGURACION"
    assert proceso["version_convenio_id"] == version_aprobada_id
    assert len(proceso["firmas"]) == 7
    assert all(
        firma["estado"] == "PENDIENTE"
        and firma["documento_id"] is None
        and firma["fecha_firma"] is None
        for firma in proceso["firmas"]
    )
    documento_aprobado = client.get(
        f"/api/convenios/{convenio_id}/firmas/documento-aprobado"
    )
    assert documento_aprobado.status_code == 200, documento_aprobado.text
    assert documento_aprobado.json()["version_convenio_id"] == version_aprobada_id
    assert documento_aprobado.json()["contenido"] == contenido_aprobado

    # Fases 13-15: dos firmas electrónicas y cinco físicas por APIs reales.
    for indice, firma in enumerate(proceso["firmas"]):
        electronica = indice < 2
        configurada = client.patch(
            f"/api/convenios/{convenio_id}/firmas/{firma['id']}",
            json={
                "nombre": f"Firmante E2E {indice + 1}",
                "cargo": f"Cargo institucional {indice + 1}",
                "modalidad": "ELECTRONICA" if electronica else "FISICA",
                "correo": f"firma-{indice}-{unico}@example.com" if electronica else None,
            },
        )
        assert configurada.status_code == 200, configurada.text
        assert configurada.json()["configurada"] is True
    iniciado = client.post(f"/api/convenios/{convenio_id}/firmas/iniciar")
    assert iniciado.status_code == 200, iniciado.text
    assert iniciado.json()["estado"] == "EN_CURSO"
    assert all(firma["configurada"] for firma in iniciado.json()["firmas"])

    mensajes_antes = len(correo_local.mensajes)
    envio_firmas = client.post(f"/api/convenios/{convenio_id}/firmas/enviar")
    assert envio_firmas.status_code == 200, envio_firmas.text
    mensajes_firma = correo_local.mensajes[mensajes_antes:]
    assert len(mensajes_firma) == 2
    tokens = [_token_de_correo(mensaje) for mensaje in mensajes_firma]
    assert len(set(tokens)) == 2
    firma_png = _firma_png()
    for token in tokens:
        acceso = client.post(
            "/api/public/firma-convenio/acceso", json={"token": token}
        )
        assert acceso.status_code == 200, acceso.text
        assert acceso.json()["contenido"] == contenido_aprobado
        firmada = client.post(
            "/api/public/firma-convenio/firmar",
            json={"token": token, "firma": firma_png, "confirmacion": True},
        )
        assert firmada.status_code == 200, firmada.text
        assert firmada.json()["estado"] == "FIRMADA"
        assert firmada.json()["fecha_firma"] is not None
        repetida = client.post(
            "/api/public/firma-convenio/firmar",
            json={"token": token, "firma": firma_png, "confirmacion": True},
        )
        assert repetida.status_code == 400, repetida.text

    seguimiento = client.get(f"/api/convenios/{convenio_id}/firmas")
    assert seguimiento.status_code == 200, seguimiento.text
    fisicas = [
        firma for firma in seguimiento.json()["firmas"] if firma["modalidad"] == "FISICA"
    ]
    assert len(fisicas) == 5
    partes = [("firma_ids", (None, str(firma["id"]))) for firma in fisicas]
    partes.extend(
        [
            ("fecha_firma", (None, datetime.now(UTC).date().isoformat())),
            (
                "archivo",
                (
                    "convenio-firmado-e2e.pdf",
                    b"%PDF-1.4 convenio firmado E2E",
                    "application/pdf",
                ),
            ),
        ]
    )
    fisicas_registradas = client.post(
        f"/api/convenios/{convenio_id}/firmas/fisicas", files=partes
    )
    assert fisicas_registradas.status_code == 201, fisicas_registradas.text
    assert fisicas_registradas.json()["estado"] == "EN_CURSO"
    assert all(
        firma["estado"] == "FIRMADA" and firma["fecha_firma"] is not None
        for firma in fisicas_registradas.json()["firmas"]
    )
    assert all(firma["documento_id"] is not None for firma in fisicas_registradas.json()["firmas"] if firma["modalidad"] == "FISICA")

    # Fases 16-17: formalización y tablero operativo final.
    formalizada = client.post(f"/api/convenios/{convenio_id}/firmas/formalizar")
    assert formalizada.status_code == 200, formalizada.text
    assert formalizada.json()["estado"] == "COMPLETADO"
    assert formalizada.json()["completado_en"] is not None
    db.expire_all()
    convenio_final = db.get(Convenio, convenio_id)
    assert convenio_final.estado == "VIGENTE"
    assert convenio_final.etapa_actual.codigo == "FIRMA_ARCHIVO_SEGUIMIENTO"
    assert convenio_final.fecha_firma is not None
    assert convenio_final.aliado_id is not None

    tablero_admin = client.get("/api/convenios/tablero")
    assert tablero_admin.status_code == 200, tablero_admin.text
    tarjetas = [
        item for item in tablero_admin.json()["convenios"] if item["id"] == convenio_id
    ]
    assert len(tarjetas) == 1
    tarjeta = tarjetas[0]
    assert tarjeta["estado"] == "VIGENTE"
    assert tarjeta["etapa_actual"]["codigo"] == "FIRMA_ARCHIVO_SEGUIMIENTO"
    assert tarjeta["etapa_actual"]["area_responsable"] == "ORI"
    assert tarjeta["puede_ver_detalle"] is True
    entrar_como(gestor)
    tablero_gestor = client.get("/api/convenios/tablero")
    assert tablero_gestor.status_code == 200, tablero_gestor.text
    assert next(
        item for item in tablero_gestor.json()["convenios"] if item["id"] == convenio_id
    )["puede_ver_detalle"] is True
    entrar_como(solicitante)
    assert client.get("/api/convenios/tablero").status_code == 403

    # Fase 18: invariantes históricas, consultadas sin producir transiciones.
    db.expire_all()
    estados_solicitud = list(
        db.scalars(
            select(Auditoria.valor_nuevo)
            .where(
                Auditoria.entidad == "solicitud",
                Auditoria.registro_id == solicitud_id,
                Auditoria.campo == "estado",
            )
            .order_by(Auditoria.id)
        )
    )
    assert radicada.json()["estado"] == "RADICADA"
    assert reradicada.json()["estado"] == "RADICADA"
    assert _es_subsecuencia(estados_solicitud, ["DEVUELTA", "APROBADA"])
    solicitud = db.get(SolicitudConvenio, solicitud_id)
    assert solicitud.solicitante_id == solicitante.id
    assert db.scalar(
        select(func.count()).select_from(Convenio).where(
            Convenio.solicitud_id == solicitud_id
        )
    ) == 1

    versiones = list(
        db.scalars(
            select(VersionConvenio)
            .where(VersionConvenio.convenio_id == convenio_id)
            .order_by(VersionConvenio.numero)
        )
    )
    numeros = [version.numero for version in versiones]
    assert numeros == sorted(set(numeros))
    assert db.get(ProcesoFirmasConvenio, proceso_id).version_convenio_id == (
        version_aprobada_id
    )

    revisiones = list(
        db.scalars(
            select(RevisionConvenio)
            .where(RevisionConvenio.convenio_id == convenio_id)
            .order_by(RevisionConvenio.id)
        )
    )
    juridicas = [item for item in revisiones if item.tipo == "JURIDICA"]
    assert len(juridicas) == 4
    primera_ronda = [item for item in juridicas if item.numero_ronda == 1]
    segunda_ronda = [item for item in juridicas if item.numero_ronda == 2]
    assert {(item.instancia_juridica, item.resultado) for item in primera_ronda} == {
        (1, "APROBADA"),
        (2, "DEVUELTA"),
    }
    primera_por_instancia = {
        item.instancia_juridica: item for item in primera_ronda
    }
    assert primera_por_instancia[1].version_resultado_id != (
        primera_por_instancia[2].version_resultado_id
    )
    assert {item.resultado for item in segunda_ronda} == {"APROBADA"}
    assert {item.version_resultado_id for item in segunda_ronda} == {
        version_aprobada_id
    }
    assert {item.resuelta_por_id for item in primera_ronda} == {
        revisor_a.id,
        revisor_b.id,
    }
    assert {item.resuelta_por_id for item in segunda_ronda} == {
        revisor_a.id,
        revisor_b.id,
    }
    contraparte_db = db.get(RevisionConvenio, revision_contraparte_id)
    assert contraparte_db.resultado == "APROBADA"
    assert contraparte_db.resuelta_por_id == solicitante.id
    assert contraparte_db.version_resultado_id == version_aprobada_id
    final_db = next(item for item in revisiones if item.tipo == "FINAL")
    assert final_db.resultado == "APROBADA"
    assert final_db.version_resultado_id == version_aprobada_id

    proceso_db = db.get(ProcesoFirmasConvenio, proceso_id)
    firmas_db = list(
        db.scalars(
            select(FirmaConvenio)
            .where(FirmaConvenio.proceso_firmas_id == proceso_id)
            .order_by(FirmaConvenio.orden)
        )
    )
    assert proceso_db.estado == "COMPLETADO"
    assert len(firmas_db) == 7
    assert sum(firma.modalidad == "ELECTRONICA" for firma in firmas_db) == 2
    assert sum(firma.modalidad == "FISICA" for firma in firmas_db) == 5
    assert all(firma.estado == EstadoFirmaConvenio.FIRMADA.value for firma in firmas_db)
    assert all(
        firma.firma_png is not None and firma.firma_sha256 is not None
        for firma in firmas_db
        if firma.modalidad == "ELECTRONICA"
    )
    assert all(
        firma.documento_id is not None
        for firma in firmas_db
        if firma.modalidad == "FISICA"
    )

    transiciones = [
        f"{item.etapa_origen.codigo if item.etapa_origen else 'NINGUNA'}"
        f"->{item.etapa_destino.codigo}"
        for item in db.scalars(
            select(HistorialEtapa)
            .where(HistorialEtapa.convenio_id == convenio_id)
            .order_by(HistorialEtapa.id)
        )
    ]
    assert _es_subsecuencia(
        transiciones,
        [
            "ELABORACION->REVISION_AVAL_JURIDICO",
            "REVISION_AVAL_JURIDICO->ELABORACION",
            "ELABORACION->REVISION_AVAL_JURIDICO",
            "REVISION_AVAL_JURIDICO->REVISION_CONTRAPARTE",
            "REVISION_CONTRAPARTE->REVISION_FINAL",
            "REVISION_FINAL->APROBACION_FIRMAS",
            "APROBACION_FIRMAS->FIRMA_ARCHIVO_SEGUIMIENTO",
        ],
    )
    assert datetime.now(UTC) >= proceso_db.completado_en
