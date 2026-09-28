from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.security import hash_contrasena
from backend.models.convenio import Convenio
from backend.models.enums import (
    ContextoVersionConvenio,
    EstadoConvenio,
    EstadoFirmaConvenio,
    EstadoProcesoFirmasConvenio,
    EstadoRevisionConvenio,
    EstadoSolicitud,
    OrigenObservacionRevision,
    ResultadoRevisionConvenio,
    RolFirmanteConvenio,
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


@pytest.mark.parametrize(
    "accion",
    [
        ("GET", "/revision-final"),
        ("POST", "/revision-final/aprobar"),
        ("POST", "/revision-final/devolver"),
        ("POST", "/firmas/iniciar"),
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
