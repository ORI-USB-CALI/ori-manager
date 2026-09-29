"""HU-13: edición, observaciones y doble aprobación jurídica."""

from copy import deepcopy

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.enums import ContextoVersionConvenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.convenios import ServicioConvenios


def _abrir(db, convenio, gestor) -> RevisionConvenio:
    ServicioConvenios(db).finalizar_elaboracion(convenio.id, gestor)
    return db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )


def _contenido_editado(contenido: dict, texto: str) -> dict:
    nuevo = deepcopy(contenido)
    nuevo["content"].append(
        {"type": "paragraph", "content": [{"type": "text", "text": texto}]}
    )
    return nuevo


def test_revisor_edita_versionado_y_version_recibida_permanece_fija(
    client, db, gestor, revisor, convenio_listo, entrar_como
) -> None:
    revision = _abrir(db, convenio_listo, gestor)
    version_recibida_id = revision.version_convenio_id
    solicitud = db.get(SolicitudConvenio, convenio_listo.solicitud_id)
    solicitud_original = (solicitud.objeto, solicitud.actualizado_en)
    entrar_como(revisor)
    consulta = client.get(f"/api/convenios/{convenio_listo.id}/revision").json()
    version = consulta["version_actual"]
    contenido = _contenido_editado(version["contenido"], "Ajuste del Revisor ORI")

    respuesta = client.patch(
        f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/contenido",
        json={"contenido": contenido, "expected_version": version["numero"]},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["numero"] == version["numero"] + 1
    db.refresh(revision)
    db.refresh(convenio_listo)
    db.refresh(solicitud)
    assert revision.version_convenio_id == version_recibida_id
    assert revision.version_resultado_id is None
    assert convenio_listo.version_actual == respuesta.json()["numero"]
    creada = db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio_listo.id,
            VersionConvenio.numero == convenio_listo.version_actual,
        )
    )
    assert creada.contexto == ContextoVersionConvenio.CORRECCION_REVISION
    assert creada.autor_id == revisor.id
    assert (solicitud.objeto, solicitud.actualizado_en) == solicitud_original

    conflicto = client.patch(
        f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/contenido",
        json={"contenido": contenido, "expected_version": version["numero"]},
    )
    assert conflicto.status_code == 409


def test_edicion_y_observacion_independiente_exigen_permiso_revisar(
    client, db, gestor, convenio_listo, entrar_como
) -> None:
    revision = _abrir(db, convenio_listo, gestor)
    contenido = db.get(VersionConvenio, revision.version_convenio_id).contenido
    ruta = f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}"

    assert client.patch(
        f"{ruta}/contenido",
        json={"contenido": contenido, "expected_version": convenio_listo.version_actual},
    ).status_code == 403
    assert client.post(
        f"{ruta}/observaciones", json={"descripcion": "Corregir cláusula"}
    ).status_code == 403


def test_observacion_independiente_bloquea_aprobacion_y_habilita_devolucion(
    client, db, gestor, revisor, convenio_listo, entrar_como
) -> None:
    revision = _abrir(db, convenio_listo, gestor)
    entrar_como(revisor)
    base = f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}"
    observacion = client.post(
        f"{base}/observaciones", json={"descripcion": "  Corregir cláusula quinta  "}
    )
    assert observacion.status_code == 201
    assert observacion.json()["descripcion"] == "Corregir cláusula quinta"
    assert observacion.json()["registrada_por"]["id"] == revisor.id

    assert client.post(
        f"{base}/aprobar",
        json={"expected_version": convenio_listo.version_actual},
    ).status_code == 409
    devolucion = client.post(
        f"{base}/devolver",
        json={"expected_version": convenio_listo.version_actual, "observaciones": []},
    )
    assert devolucion.status_code == 200
    assert devolucion.json()["resultado"] == "DEVUELTA"
    assert devolucion.json()["version_resultado_id"] is not None
    db.refresh(convenio_listo)
    assert convenio_listo.etapa_actual.codigo == "ELABORACION"


def test_devolver_sin_observaciones_no_resuelve_revision(
    client, db, gestor, revisor, convenio_listo, entrar_como
) -> None:
    revision = _abrir(db, convenio_listo, gestor)
    entrar_como(revisor)
    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/devolver",
        json={"expected_version": convenio_listo.version_actual, "observaciones": []},
    )
    assert respuesta.status_code == 422
    db.refresh(revision)
    assert revision.estado == "PENDIENTE"
    assert revision.version_resultado_id is None


def test_aprobar_rj1_crea_una_sola_rj2_y_no_avanza_etapa(
    client, db, gestor, revisor, convenio_listo, entrar_como
) -> None:
    primera = _abrir(db, convenio_listo, gestor)
    entrar_como(revisor)
    ruta = f"/api/convenios/{convenio_listo.id}/revisiones/{primera.id}/aprobar"
    respuesta = client.post(
        ruta, json={"expected_version": convenio_listo.version_actual}
    )
    assert respuesta.status_code == 200
    assert client.post(
        ruta, json={"expected_version": convenio_listo.version_actual}
    ).status_code == 409

    revisiones = list(
        db.scalars(
            select(RevisionConvenio)
            .where(RevisionConvenio.convenio_id == convenio_listo.id)
            .order_by(RevisionConvenio.instancia_juridica)
        )
    )
    assert len(revisiones) == 2
    primera, segunda = revisiones
    assert (primera.instancia_juridica, primera.numero_ronda) == (1, 1)
    assert primera.resultado == "APROBADA"
    assert primera.resuelta_por_id == revisor.id
    assert primera.resuelta_en is not None
    assert primera.version_resultado_id == segunda.version_convenio_id
    assert segunda.instancia_juridica == 2
    assert segunda.estado == "PENDIENTE"
    db.refresh(convenio_listo)
    assert convenio_listo.etapa_actual.codigo == "REVISION_AVAL_JURIDICO"


def test_rj2_exige_otro_revisor_y_solo_entonces_habilita_contraparte(
    client, db, gestor, revisor, crear_usuario, convenio_listo, entrar_como
) -> None:
    primera = _abrir(db, convenio_listo, gestor)
    entrar_como(revisor)
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{primera.id}/aprobar",
        json={"expected_version": convenio_listo.version_actual},
    ).status_code == 200
    segunda = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    ruta = f"/api/convenios/{convenio_listo.id}/revisiones/{segunda.id}/aprobar"
    assert client.post(
        ruta, json={"expected_version": convenio_listo.version_actual}
    ).status_code == 409

    otro = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    entrar_como(otro)
    assert client.post(
        ruta, json={"expected_version": convenio_listo.version_actual}
    ).status_code == 200
    db.refresh(convenio_listo)
    db.refresh(segunda)
    assert segunda.resuelta_por_id == otro.id
    assert segunda.version_resultado_id is not None
    assert convenio_listo.etapa_actual.codigo == "REVISION_CONTRAPARTE"
    assert not db.scalars(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.tipo == "CONTRAPARTE",
        )
    ).all()


def test_rj2_no_puede_aprobar_una_version_distinta_a_la_avalada_por_rj1(
    client, db, gestor, revisor, crear_usuario, convenio_listo, entrar_como
) -> None:
    primera = _abrir(db, convenio_listo, gestor)
    entrar_como(revisor)
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{primera.id}/aprobar",
        json={"expected_version": convenio_listo.version_actual},
    ).status_code == 200
    segunda = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    version_avalada_rj1 = primera.version_resultado_id
    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    entrar_como(otro_revisor)
    contenido_v1 = db.get(VersionConvenio, version_avalada_rj1).contenido
    edicion = client.patch(
        f"/api/convenios/{convenio_listo.id}/revisiones/{segunda.id}/contenido",
        json={
            "contenido": _contenido_editado(contenido_v1, "Cambio realizado en RJ2"),
            "expected_version": convenio_listo.version_actual,
        },
    )
    assert edicion.status_code == 200
    version_v2 = edicion.json()["id"]
    db.refresh(convenio_listo)
    db.refresh(primera)
    db.refresh(segunda)
    assert convenio_listo.version_actual == edicion.json()["numero"]
    assert primera.version_resultado_id == version_avalada_rj1
    assert primera.version_resultado_id != version_v2
    assert segunda.estado == "PENDIENTE"
    assert segunda.resultado is None
    assert segunda.version_resultado_id is None

    historial_antes = db.scalar(
        select(func.count()).select_from(HistorialEtapa).where(
            HistorialEtapa.convenio_id == convenio_listo.id
        )
    )
    auditorias_antes = db.scalar(
        select(func.count()).select_from(Auditoria).where(
            Auditoria.entidad == "revision_convenio",
            Auditoria.registro_id == segunda.id,
        )
    )
    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{segunda.id}/aprobar",
        json={"expected_version": convenio_listo.version_actual},
    )

    assert respuesta.status_code == 409
    assert "requiere reiniciar la revisión jurídica" in respuesta.json()["detail"]
    db.expire_all()
    convenio = db.get(type(convenio_listo), convenio_listo.id)
    segunda = db.get(RevisionConvenio, segunda.id)
    assert segunda.estado == "PENDIENTE"
    assert segunda.resultado is None
    assert segunda.resuelta_por_id is None
    assert segunda.resuelta_en is None
    assert segunda.version_resultado_id is None
    assert convenio.etapa_actual.codigo == "REVISION_AVAL_JURIDICO"
    assert db.scalar(
        select(func.count()).select_from(HistorialEtapa).where(
            HistorialEtapa.convenio_id == convenio.id
        )
    ) == historial_antes
    assert db.scalar(
        select(func.count()).select_from(Auditoria).where(
            Auditoria.entidad == "revision_convenio",
            Auditoria.registro_id == segunda.id,
        )
    ) == auditorias_antes


def test_rj2_editada_devuelta_reenvia_v2_y_nueva_ronda_avala_la_misma_version(
    client, db, gestor, revisor, crear_usuario, convenio_listo, entrar_como
) -> None:
    primera_ronda_rj1 = _abrir(db, convenio_listo, gestor)
    entrar_como(revisor)
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/"
        f"{primera_ronda_rj1.id}/aprobar",
        json={"expected_version": convenio_listo.version_actual},
    ).status_code == 200
    primera_ronda_rj2 = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    segundo_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    entrar_como(segundo_revisor)
    version_v1 = db.get(
        VersionConvenio, primera_ronda_rj1.version_resultado_id
    )
    edicion = client.patch(
        f"/api/convenios/{convenio_listo.id}/revisiones/"
        f"{primera_ronda_rj2.id}/contenido",
        json={
            "contenido": _contenido_editado(
                version_v1.contenido, "Corrección creada durante RJ2"
            ),
            "expected_version": convenio_listo.version_actual,
        },
    )
    assert edicion.status_code == 200
    version_v2_id = edicion.json()["id"]
    numero_v2 = edicion.json()["numero"]
    devolucion = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/"
        f"{primera_ronda_rj2.id}/devolver",
        json={
            "expected_version": numero_v2,
            "observaciones": ["Validar la corrección incorporada en V2"],
        },
    )
    assert devolucion.status_code == 200
    assert devolucion.json()["version_resultado_id"] == version_v2_id
    observacion_id = devolucion.json()["observaciones"][0]["id"]

    entrar_como(gestor)
    assert client.patch(
        f"/api/convenios/{convenio_listo.id}/observaciones/"
        f"{observacion_id}/atender",
        json={"respuesta": "La corrección V2 fue verificada"},
    ).status_code == 200
    reenvio = client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    )
    assert reenvio.status_code == 200
    db.refresh(convenio_listo)
    assert convenio_listo.version_actual == numero_v2
    nueva_rj1 = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    assert (nueva_rj1.numero_ronda, nueva_rj1.instancia_juridica) == (2, 1)
    assert nueva_rj1.version_convenio_id == version_v2_id

    entrar_como(revisor)
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{nueva_rj1.id}/aprobar",
        json={"expected_version": numero_v2},
    ).status_code == 200
    nueva_rj2 = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    tercer_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    entrar_como(tercer_revisor)
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{nueva_rj2.id}/aprobar",
        json={"expected_version": numero_v2},
    ).status_code == 200

    db.refresh(nueva_rj1)
    db.refresh(nueva_rj2)
    db.refresh(convenio_listo)
    assert nueva_rj1.version_resultado_id == version_v2_id
    assert nueva_rj2.version_resultado_id == version_v2_id
    assert convenio_listo.etapa_actual.codigo == "REVISION_CONTRAPARTE"
    assert db.scalar(
        select(func.count()).select_from(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.tipo == "JURIDICA",
        )
    ) == 4


def test_revisor_de_rj1_no_puede_consultar_ni_mutar_rj2(
    client, db, gestor, revisor, crear_usuario, convenio_listo, entrar_como
) -> None:
    primera = _abrir(db, convenio_listo, gestor)
    entrar_como(revisor)
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{primera.id}/aprobar",
        json={"expected_version": convenio_listo.version_actual},
    ).status_code == 200
    segunda = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    tarjeta = next(
        item
        for item in client.get("/api/convenios/tablero").json()["convenios"]
        if item["id"] == convenio_listo.id
    )
    assert tarjeta["puede_ver_detalle"] is False

    contenido_actual = db.scalar(
        select(VersionConvenio.contenido).where(
            VersionConvenio.convenio_id == convenio_listo.id,
            VersionConvenio.numero == convenio_listo.version_actual,
        )
    )
    contenido_editado = _contenido_editado(
        contenido_actual, "Intento no autorizado en RJ2"
    )

    def contar(model) -> int:
        return db.scalar(
            select(func.count()).select_from(model).where(
                model.convenio_id == convenio_listo.id
            )
        )

    estado_antes = (
        contar(VersionConvenio),
        contar(ObservacionRevision),
        contar(HistorialEtapa),
        db.scalar(
            select(func.count()).select_from(Auditoria).where(
                Auditoria.entidad == "revision_convenio",
                Auditoria.registro_id == segunda.id,
            )
        ),
        segunda.estado,
        segunda.resultado,
        convenio_listo.etapa_actual_id,
    )
    base = f"/api/convenios/{convenio_listo.id}/revisiones/{segunda.id}"
    respuestas = (
        client.patch(
            f"{base}/contenido",
            json={
                "contenido": contenido_editado,
                "expected_version": convenio_listo.version_actual,
            },
        ),
        client.post(
            f"{base}/observaciones",
            json={"descripcion": "Intento no autorizado"},
        ),
        client.post(
            f"{base}/devolver",
            json={
                "expected_version": convenio_listo.version_actual,
                "observaciones": ["Intento no autorizado"],
            },
        ),
        client.post(
            f"{base}/aprobar",
            json={"expected_version": convenio_listo.version_actual},
        ),
    )
    assert all(respuesta.status_code == 409 for respuesta in respuestas)

    db.expire_all()
    segunda = db.get(RevisionConvenio, segunda.id)
    convenio = db.get(type(convenio_listo), convenio_listo.id)
    estado_despues = (
        contar(VersionConvenio),
        contar(ObservacionRevision),
        contar(HistorialEtapa),
        db.scalar(
            select(func.count()).select_from(Auditoria).where(
                Auditoria.entidad == "revision_convenio",
                Auditoria.registro_id == segunda.id,
            )
        ),
        segunda.estado,
        segunda.resultado,
        convenio.etapa_actual_id,
    )
    assert estado_despues == estado_antes

    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    entrar_como(otro_revisor)
    assert client.get(f"/api/convenios/{convenio.id}/revision").status_code == 200
    assert client.patch(
        f"{base}/contenido",
        json={
            "contenido": contenido_editado,
            "expected_version": convenio.version_actual,
        },
    ).status_code == 200
    assert client.post(
        f"{base}/observaciones",
        json={"descripcion": "Observación válida de otro Revisor"},
    ).status_code == 201


def test_devolucion_exige_nueva_version_y_reinicia_desde_rj1_ronda_siguiente(
    client, db, gestor, revisor, convenio_listo, entrar_como
) -> None:
    primera = _abrir(db, convenio_listo, gestor)
    entrar_como(revisor)
    devolucion = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{primera.id}/devolver",
        json={
            "expected_version": convenio_listo.version_actual,
            "observaciones": ["Ajustar el documento"],
        },
    )
    observacion_id = devolucion.json()["observaciones"][0]["id"]
    version_devuelta = devolucion.json()["version_resultado_id"]
    entrar_como(gestor)
    assert client.patch(
        f"/api/convenios/{convenio_listo.id}/observaciones/{observacion_id}/atender",
        json={"respuesta": "Atendida"},
    ).status_code == 200
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    ).status_code == 409

    elaboracion = client.get(
        f"/api/convenios/{convenio_listo.id}/elaboracion"
    ).json()
    contenido = _contenido_editado(elaboracion["contenido"], "Corrección del Gestor")
    assert client.patch(
        f"/api/convenios/{convenio_listo.id}/elaboracion",
        json={"contenido": contenido, "expected_version": elaboracion["version_actual"]},
    ).status_code == 200
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    ).status_code == 200

    nueva = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    db.refresh(primera)
    assert primera.version_resultado_id == version_devuelta
    assert (nueva.numero_ronda, nueva.instancia_juridica) == (2, 1)
    assert nueva.version_convenio_id != primera.version_resultado_id


def test_fallo_al_crear_rj2_revierte_aprobacion(
    db, gestor, revisor, convenio_listo, monkeypatch
) -> None:
    primera = _abrir(db, convenio_listo, gestor)
    flush_real = db.flush
    llamadas = 0

    def fallar(*args, **kwargs):
        nonlocal llamadas
        llamadas += 1
        if llamadas == 1:
            raise SQLAlchemyError("fallo simulado")
        return flush_real(*args, **kwargs)

    monkeypatch.setattr(db, "flush", fallar)
    with pytest.raises(SQLAlchemyError):
        ServicioConvenios(db).aprobar(
            convenio_listo.id,
            primera.id,
            convenio_listo.version_actual,
            revisor,
        )
    db.expire_all()
    persistida = db.get(RevisionConvenio, primera.id)
    assert persistida.estado == "PENDIENTE"
    assert persistida.resultado is None


def test_fallo_en_transicion_a_contraparte_revierte_aprobacion_rj2(
    db, gestor, revisor, crear_usuario, convenio_listo, monkeypatch
) -> None:
    primera = _abrir(db, convenio_listo, gestor)
    ServicioConvenios(db).aprobar(
        convenio_listo.id,
        primera.id,
        convenio_listo.version_actual,
        revisor,
    )
    segunda = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    commit_real = db.commit

    def fallar_commit() -> None:
        raise SQLAlchemyError("fallo simulado al confirmar transición")

    monkeypatch.setattr(db, "commit", fallar_commit)
    with pytest.raises(SQLAlchemyError):
        ServicioConvenios(db).aprobar(
            convenio_listo.id,
            segunda.id,
            convenio_listo.version_actual,
            otro_revisor,
        )
    monkeypatch.setattr(db, "commit", commit_real)
    db.expire_all()

    persistida = db.get(RevisionConvenio, segunda.id)
    convenio_persistido = db.get(type(convenio_listo), convenio_listo.id)
    assert persistida.estado == "PENDIENTE"
    assert persistida.resultado is None
    assert persistida.version_resultado_id is None
    assert convenio_persistido.etapa_actual.codigo == "REVISION_AVAL_JURIDICO"
    assert not db.scalars(
        select(HistorialEtapa).where(
            HistorialEtapa.convenio_id == convenio_listo.id,
            HistorialEtapa.observacion == "Dos revisiones jurídicas aprobadas",
        )
    ).all()
