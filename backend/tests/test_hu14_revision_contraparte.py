"""HU-14: revisión autenticada por el Solicitante dentro de ORI Manager."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, date, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.security import hash_contrasena
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import AlcanceConvenio, EstadoSolicitud, TipoSolicitante
from backend.models.historial_etapa import HistorialEtapa
from backend.models.invitacion_revision_contraparte import InvitacionRevisionContraparte
from backend.models.notificacion import Notificacion
from backend.models.observacion_revision import ObservacionRevision
from backend.models.respuesta_revision_contraparte import RespuestaRevisionContraparte
from backend.models.revision_convenio import RevisionConvenio
from backend.models.rol import Rol
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.models.version_convenio import VersionConvenio
from backend.schemas.convenio import ConvenioCrear, ConvenioElaboracionGuardar
from backend.services.convenios import RevisionNoDisponible, ServicioConvenios


def _contenido_corregido(contenido: dict) -> dict:
    nuevo = deepcopy(contenido)
    nuevo["content"].append({
        "type": "paragraph",
        "content": [{"type": "text", "text": "Corrección del nuevo ciclo"}],
    })
    return nuevo


def _habilitar(db, convenio, gestor, solicitante, revisor, crear_usuario):
    solicitud = db.get(SolicitudConvenio, convenio.solicitud_id)
    solicitud.solicitante_id = solicitante.id
    db.commit()
    ServicioConvenios(db).finalizar_elaboracion(convenio.id, gestor)
    primera = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id,
        RevisionConvenio.estado == "PENDIENTE",
    ))
    ServicioConvenios(db).aprobar(
        convenio.id, primera.id, convenio.version_actual, revisor
    )
    segunda = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id,
        RevisionConvenio.estado == "PENDIENTE",
    ))
    otro = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    ServicioConvenios(db).aprobar(
        convenio.id, segunda.id, convenio.version_actual, otro
    )
    db.refresh(convenio)
    return db.scalar(select(VersionConvenio).where(
        VersionConvenio.convenio_id == convenio.id,
        VersionConvenio.numero == convenio.version_actual,
    ))


def _enviar(client, entrar_como, gestor, convenio) -> dict:
    entrar_como(gestor)
    respuesta = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _crear_escenario_concurrente(db_engine) -> dict[str, int]:
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    identificador = uuid4().hex
    with fabrica() as sesion:
        def crear_usuario(
            codigo_rol: CodigoRol,
            tipo_usuario: TipoUsuario = TipoUsuario.INTERNO,
        ) -> Usuario:
            rol = sesion.scalar(select(Rol).where(Rol.codigo == codigo_rol.value))
            usuario = Usuario(
                correo=f"hu14-concurrencia-{uuid4().hex}@example.com",
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

        gestor = crear_usuario(CodigoRol.GESTOR_ORI)
        solicitante = crear_usuario(CodigoRol.SOLICITANTE_INTERNO)
        revisor = crear_usuario(CodigoRol.REVISOR_ORI)
        solicitud = SolicitudConvenio(
            consecutivo=f"H14C-{identificador}",
            tipo_solicitante=TipoSolicitante.INTERNO.value,
            solicitante_id=solicitante.id,
            objeto="Solicitud para concurrencia HU-14",
            justificacion="Validar decisiones autenticadas concurrentes",
            vigencia_estimada="24 meses",
            estado=EstadoSolicitud.APROBADA.value,
            nombre_aliado_propuesto="Universidad Contraparte",
            correo_aliado_propuesto="convenios@contraparte.example",
        )
        sesion.add(solicitud)
        sesion.commit()
        tipo = sesion.scalar(
            select(TipoConvenio).where(TipoConvenio.codigo == "MARCO")
        )
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
        version = _habilitar(
            sesion, convenio, gestor, solicitante, revisor, crear_usuario
        )
        revision = ServicioConvenios(sesion).enviar_a_contraparte(
            convenio.id, convenio.version_actual, gestor
        )
        usuarios = list(sesion.scalars(select(Usuario.id).where(
            Usuario.correo.like("hu14-concurrencia-%@example.com")
        )))
        return {
            "convenio_id": convenio.id,
            "solicitud_id": solicitud.id,
            "revision_id": revision.id,
            "solicitante_id": solicitante.id,
            "version_numero": version.numero,
            "usuario_ids": usuarios,
        }


def _limpiar_escenario_concurrente(db_engine, escenario: dict) -> None:
    fabrica = sessionmaker(bind=db_engine)
    with fabrica() as sesion:
        convenio_id = escenario["convenio_id"]
        sesion.execute(delete(ObservacionRevision).where(
            ObservacionRevision.convenio_id == convenio_id
        ))
        sesion.execute(delete(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_id
        ))
        sesion.execute(delete(HistorialEtapa).where(
            HistorialEtapa.convenio_id == convenio_id
        ))
        sesion.execute(delete(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio_id
        ))
        sesion.execute(delete(Documento).where(
            (Documento.convenio_id == convenio_id)
            | (Documento.solicitud_id == escenario["solicitud_id"])
        ))
        sesion.execute(delete(Auditoria).where(
            Auditoria.usuario_id.in_(escenario["usuario_ids"])
        ))
        sesion.execute(delete(Notificacion).where(
            Notificacion.usuario_id.in_(escenario["usuario_ids"])
        ))
        sesion.execute(delete(Convenio).where(Convenio.id == convenio_id))
        sesion.execute(delete(SolicitudConvenio).where(
            SolicitudConvenio.id == escenario["solicitud_id"]
        ))
        sesion.execute(delete(Usuario).where(
            Usuario.id.in_(escenario["usuario_ids"])
        ))
        sesion.commit()


def test_envio_asigna_solicitante_y_no_crea_registros_legacy(
    db, client, gestor, solicitante, revisor, crear_usuario, entrar_como,
    convenio_listo,
) -> None:
    version = _habilitar(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    cuerpo = _enviar(client, entrar_como, gestor, convenio_listo)

    revision = db.get(RevisionConvenio, cuerpo["id"])
    assert (revision.tipo, revision.estado, revision.resultado) == (
        "CONTRAPARTE", "PENDIENTE", None
    )
    assert revision.responsable_id == solicitante.id
    assert revision.creada_por_id == gestor.id
    assert revision.version_convenio_id == version.id
    assert revision.version_resultado_id is None
    assert revision.creado_en is not None
    assert convenio_listo.etapa_actual.codigo == "REVISION_CONTRAPARTE"
    assert not db.scalars(select(InvitacionRevisionContraparte).where(
        InvitacionRevisionContraparte.revision_convenio_id == revision.id
    )).all()
    assert db.scalar(select(Auditoria.id).where(
        Auditoria.entidad == "revision_convenio",
        Auditoria.registro_id == revision.id,
        Auditoria.accion == "INSERT",
    )) is not None


def test_envio_sin_avales_sin_solicitante_y_duplicado_no_crea_otro_ciclo(
    db, client, gestor, solicitante, revisor, crear_usuario, entrar_como,
    crear_convenio, convenio_listo, monkeypatch,
) -> None:
    sin_avales = crear_convenio(gestor)
    entrar_como(gestor)
    assert client.post(
        f"/api/convenios/{sin_avales.id}/revision-contraparte/enviar",
        json={"expected_version": sin_avales.version_actual},
    ).status_code == 409

    _habilitar(db, convenio_listo, gestor, solicitante, revisor, crear_usuario)
    scalar_real = db.scalar

    def ocultar_solicitud(consulta, *args, **kwargs):
        if any(
            descripcion.get("entity") is SolicitudConvenio
            for descripcion in consulta.column_descriptions
        ):
            return None
        return scalar_real(consulta, *args, **kwargs)

    monkeypatch.setattr(db, "scalar", ocultar_solicitud)
    with pytest.raises(RevisionNoDisponible, match="Solicitante asociado"):
        ServicioConvenios(db).enviar_a_contraparte(
            convenio_listo.id, convenio_listo.version_actual, gestor
        )
    monkeypatch.setattr(db, "scalar", scalar_real)
    assert not db.scalars(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio_listo.id,
        RevisionConvenio.tipo == "CONTRAPARTE",
    )).all()

    _enviar(client, entrar_como, gestor, convenio_listo)
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/revision-contraparte/enviar",
        json={"expected_version": convenio_listo.version_actual},
    ).status_code == 409
    assert db.scalar(select(func.count()).select_from(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio_listo.id,
        RevisionConvenio.tipo == "CONTRAPARTE",
    )) == 1


def test_bandeja_y_detalle_respetan_ownership(
    db, client, gestor, solicitante, revisor, crear_usuario, entrar_como,
    convenio_listo,
) -> None:
    version = _habilitar(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    enviada = _enviar(client, entrar_como, gestor, convenio_listo)
    otro = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)

    entrar_como(solicitante)
    pendientes = client.get("/api/convenios/revisiones-contraparte/pendientes")
    assert pendientes.status_code == 200
    assert [item["revision_id"] for item in pendientes.json()] == [enviada["id"]]
    assert pendientes.json()[0]["version_numero"] == version.numero
    assert pendientes.json()[0]["enviada_por"]["id"] == gestor.id
    detalle = client.get(
        f"/api/convenios/revisiones-contraparte/{enviada['id']}"
    )
    assert detalle.status_code == 200
    assert detalle.json()["version_recibida"]["id"] == version.id
    assert detalle.json()["version_recibida"]["contenido"] == version.contenido

    entrar_como(otro)
    assert client.get(
        "/api/convenios/revisiones-contraparte/pendientes"
    ).json() == []
    assert client.get(
        f"/api/convenios/revisiones-contraparte/{enviada['id']}"
    ).status_code == 404


def test_aprobacion_owner_crea_revision_final_y_otro_solicitante_no_decide(
    db, client, gestor, solicitante, revisor, crear_usuario, entrar_como,
    convenio_listo,
) -> None:
    version = _habilitar(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    enviada = _enviar(client, entrar_como, gestor, convenio_listo)
    otro = crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)
    entrar_como(otro)
    assert client.post(
        f"/api/convenios/revisiones-contraparte/{enviada['id']}/aprobar",
        json={"expected_version": version.numero},
    ).status_code == 404
    assert db.get(RevisionConvenio, enviada["id"]).estado == "PENDIENTE"

    entrar_como(solicitante)
    respuesta = client.post(
        f"/api/convenios/revisiones-contraparte/{enviada['id']}/aprobar",
        json={"expected_version": version.numero},
    )
    assert respuesta.status_code == 200, respuesta.text
    db.expire_all()
    revision = db.get(RevisionConvenio, enviada["id"])
    convenio = db.get(type(convenio_listo), convenio_listo.id)
    final = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id,
        RevisionConvenio.tipo == "FINAL",
        RevisionConvenio.estado == "PENDIENTE",
    ))
    assert revision.resultado == "APROBADA"
    assert revision.resuelta_por_id == solicitante.id
    assert revision.resuelta_en is not None
    assert revision.version_resultado_id == version.id
    assert convenio.etapa_actual.codigo == "REVISION_FINAL"
    assert final.version_convenio_id == version.id
    assert final.responsable_id == gestor.id
    assert final.creada_por_id == gestor.id
    assert db.scalar(select(RespuestaRevisionContraparte.id).where(
        RespuestaRevisionContraparte.revision_convenio_id == revision.id
    )) is None
    transicion = db.get(HistorialEtapa, final.historial_etapa_id)
    assert transicion.usuario_id == solicitante.id
    assert transicion.responsable_id == gestor.id


def test_devolucion_vacia_no_cambia_y_valida_registra_actor_real(
    db, client, gestor, solicitante, revisor, crear_usuario, entrar_como,
    convenio_listo,
) -> None:
    version = _habilitar(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    enviada = _enviar(client, entrar_como, gestor, convenio_listo)
    entrar_como(solicitante)
    historiales_antes = db.scalar(
        select(func.count()).select_from(HistorialEtapa).where(
            HistorialEtapa.convenio_id == convenio_listo.id
        )
    )
    assert client.post(
        f"/api/convenios/revisiones-contraparte/{enviada['id']}/devolver",
        json={"expected_version": version.numero, "observaciones": []},
    ).status_code == 422
    db.expire_all()
    revision = db.get(RevisionConvenio, enviada["id"])
    assert (revision.estado, revision.resultado) == ("PENDIENTE", None)
    assert not revision.observaciones
    assert db.scalar(select(func.count()).select_from(HistorialEtapa).where(
        HistorialEtapa.convenio_id == convenio_listo.id
    )) == historiales_antes

    respuesta = client.post(
        f"/api/convenios/revisiones-contraparte/{enviada['id']}/devolver",
        json={
            "expected_version": version.numero,
            "observaciones": ["  Ajustar el alcance contractual  "],
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    db.expire_all()
    revision = db.get(RevisionConvenio, enviada["id"])
    observacion = db.scalar(select(ObservacionRevision).where(
        ObservacionRevision.revision_convenio_id == revision.id
    ))
    convenio = db.get(type(convenio_listo), convenio_listo.id)
    assert revision.resultado == "DEVUELTA"
    assert revision.resuelta_por_id == solicitante.id
    assert revision.version_resultado_id == version.id
    assert observacion.descripcion == "Ajustar el alcance contractual"
    assert observacion.registrada_por_id == solicitante.id
    assert observacion.responsable_id == gestor.id
    assert convenio.etapa_actual.codigo == "ELABORACION"
    assert not db.scalars(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id,
        RevisionConvenio.tipo == "FINAL",
    )).all()


def test_correccion_y_dos_avales_crean_nuevo_ciclo_sin_sobrescribir_anterior(
    db, client, gestor, solicitante, revisor, crear_usuario, entrar_como,
    convenio_listo,
) -> None:
    version_v1 = _habilitar(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    primera = _enviar(client, entrar_como, gestor, convenio_listo)
    entrar_como(solicitante)
    devuelta = client.post(
        f"/api/convenios/revisiones-contraparte/{primera['id']}/devolver",
        json={
            "expected_version": version_v1.numero,
            "observaciones": ["Corregir antes de un nuevo envío"],
        },
    )
    observacion_id = devuelta.json()["observaciones"][0]["id"]
    ServicioConvenios(db).atender_observacion(
        convenio_listo.id, observacion_id, "Corregido", gestor
    )
    elaboracion = ServicioConvenios(db).obtener_para_elaboracion(convenio_listo.id)
    ServicioConvenios(db).guardar_elaboracion(
        convenio_listo.id,
        ConvenioElaboracionGuardar(
            contenido=_contenido_corregido(elaboracion.contenido),
            expected_version=elaboracion.version_actual,
        ),
        gestor,
    )
    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    nueva_rj1 = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio_listo.id,
        RevisionConvenio.estado == "PENDIENTE",
    ))
    revisor_a = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    ServicioConvenios(db).aprobar(
        convenio_listo.id, nueva_rj1.id, convenio_listo.version_actual, revisor_a
    )
    nueva_rj2 = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio_listo.id,
        RevisionConvenio.estado == "PENDIENTE",
    ))
    revisor_b = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    ServicioConvenios(db).aprobar(
        convenio_listo.id, nueva_rj2.id, convenio_listo.version_actual, revisor_b
    )
    segunda = _enviar(client, entrar_como, gestor, convenio_listo)

    db.expire_all()
    anterior = db.get(RevisionConvenio, primera["id"])
    nuevo = db.get(RevisionConvenio, segunda["id"])
    assert anterior.resultado == "DEVUELTA"
    assert anterior.version_convenio_id == version_v1.id
    assert anterior.resuelta_por_id == solicitante.id
    assert nuevo.id != anterior.id
    assert (nuevo.estado, nuevo.resultado) == ("PENDIENTE", None)
    assert nuevo.responsable_id == solicitante.id
    assert nuevo.version_convenio_id != version_v1.id


@pytest.mark.parametrize("accion", ["acceso", "aprobar", "devolver"])
def test_endpoints_publicos_no_existen(client, accion) -> None:
    assert client.post(f"/api/public/revision-contraparte/{accion}").status_code == 404


def test_fallo_commit_revierte_aprobacion_autenticada(
    db, gestor, solicitante, revisor, crear_usuario, convenio_listo, monkeypatch
) -> None:
    version = _habilitar(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision = ServicioConvenios(db).enviar_a_contraparte(
        convenio_listo.id, convenio_listo.version_actual, gestor
    )

    def fallar_commit() -> None:
        raise SQLAlchemyError("fallo simulado")

    monkeypatch.setattr(db, "commit", fallar_commit)
    with pytest.raises(SQLAlchemyError):
        ServicioConvenios(db).aprobar_revision_contraparte(
            revision.id, version.numero, solicitante
        )
    db.expire_all()
    persistida = db.get(RevisionConvenio, revision.id)
    convenio = db.get(type(convenio_listo), convenio_listo.id)
    assert (persistida.estado, persistida.resultado) == ("PENDIENTE", None)
    assert persistida.resuelta_por_id is None
    assert persistida.version_resultado_id is None
    assert convenio.etapa_actual.codigo == "REVISION_CONTRAPARTE"
    assert not db.scalars(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id,
        RevisionConvenio.tipo == "FINAL",
    )).all()


def test_decisiones_autenticadas_concurrentes_solo_permiten_un_resultado(
    db_engine,
) -> None:
    escenario = _crear_escenario_concurrente(db_engine)
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    barrera = Barrier(2)

    def decidir(accion: str) -> tuple[str, str]:
        with fabrica() as sesion:
            actor = sesion.get(Usuario, escenario["solicitante_id"])
            barrera.wait(timeout=10)
            try:
                servicio = ServicioConvenios(sesion)
                if accion == "aprobar":
                    servicio.aprobar_revision_contraparte(
                        escenario["revision_id"],
                        escenario["version_numero"],
                        actor,
                    )
                else:
                    servicio.devolver_revision_contraparte(
                        escenario["revision_id"],
                        escenario["version_numero"],
                        ["Ajustar antes de continuar"],
                        actor,
                    )
                return "ok", accion
            except RevisionNoDisponible as exc:
                return "rechazada", str(exc)

    try:
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(decidir, ["aprobar", "devolver"]))

        assert [estado for estado, _ in resultados].count("ok") == 1
        assert [estado for estado, _ in resultados].count("rechazada") == 1
        with fabrica() as verificacion:
            persistida = verificacion.get(
                RevisionConvenio, escenario["revision_id"]
            )
            convenio = verificacion.get(Convenio, escenario["convenio_id"])
            assert persistida.estado == "RESUELTA"
            assert persistida.resultado in {"APROBADA", "DEVUELTA"}
            assert verificacion.scalar(
                select(func.count()).select_from(HistorialEtapa).where(
                    HistorialEtapa.convenio_id == convenio.id,
                    HistorialEtapa.observacion.in_([
                        "Aprobación del Solicitante en revisión de contraparte",
                        "Devolución del Solicitante en revisión de contraparte",
                    ]),
                )
            ) == 1
            finales = verificacion.scalar(
                select(func.count()).select_from(RevisionConvenio).where(
                    RevisionConvenio.convenio_id == convenio.id,
                    RevisionConvenio.tipo == "FINAL",
                )
            )
            observaciones = verificacion.scalar(
                select(func.count()).select_from(ObservacionRevision).where(
                    ObservacionRevision.revision_convenio_id == persistida.id
                )
            )
            if persistida.resultado == "APROBADA":
                assert convenio.etapa_actual.codigo == "REVISION_FINAL"
                assert (finales, observaciones) == (1, 0)
            else:
                assert convenio.etapa_actual.codigo == "ELABORACION"
                assert (finales, observaciones) == (0, 1)
    finally:
        _limpiar_escenario_concurrente(db_engine, escenario)
