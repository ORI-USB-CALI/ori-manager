"""HT-16: carreras reales con sesiones y transacciones PostgreSQL independientes."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from backend.core.roles import CodigoRol
from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.borrador_convenio import BorradorConvenio
from backend.models.convenio import Convenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.invitacion_revision_contraparte import InvitacionRevisionContraparte
from backend.models.notificacion import Notificacion
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_convenio import RevisionConvenio
from backend.models.rol import Rol
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.models.version_convenio import VersionConvenio
from backend.schemas.convenio import (
    ConvenioCrearManual,
    ConvenioElaboracionActualizar,
    ConvenioElaboracionGuardar,
)
from backend.services import contraparte_externa
from backend.services.contraparte_externa import (
    EnlaceContraparteError,
    ServicioContraparteExterna,
)
from backend.services.convenios import (
    ConvenioNoEditable,
    IdentidadAliadoIncompatible,
    RevisionNoDisponible,
    ServicioConvenios,
)
from backend.services.correo import CorreoLocal


@pytest.fixture
def escenario(db_engine):
    fabrica = sessionmaker(bind=db_engine, expire_on_commit=False)
    usuarios = []
    convenio_id = None
    with fabrica() as db:
        for codigo in (CodigoRol.GESTOR_ORI, CodigoRol.REVISOR_ORI, CodigoRol.REVISOR_ORI):
            usuario = Usuario(
                correo=f"ht16-{uuid4().hex}@example.com", nombre_completo="Prueba HT-16",
                hash_contrasena="Sin acceso en esta prueba", tipo_usuario="INTERNO",
                rol=db.scalar(select(Rol).where(Rol.codigo == codigo.value)),
            )
            db.add(usuario)
            db.commit()
            usuarios.append(usuario.id)
        gestor = db.get(Usuario, usuarios[0])
        servicio = ServicioConvenios(db)
        convenio = servicio.crear_manual(ConvenioCrearManual(
            objeto="Proyecto concurrente HT-16", alcance="INSTITUCIONAL",
            duracion_meses=12, implicacion_financiera="Sin costo",
            tipo_convenio_id=db.scalar(select(TipoConvenio.id).where(TipoConvenio.codigo == "MARCO")),
        ), gestor)
        convenio_id = convenio.id
        servicio.guardar_elaboracion(convenio_id, ConvenioElaboracionGuardar(
            # HT-15: el borrador nace en la revisión 1 al crear el convenio.
            expected_revision=1, contenido={"type": "doc", "content": [{
                "type": "paragraph", "content": [{"type": "text", "text": "Texto HT-16"}],
            }]},
        ), gestor)
        servicio.finalizar_elaboracion(convenio_id, gestor)
        for usuario_id in usuarios[1:]:
            revision = db.scalar(select(RevisionConvenio).where(
                RevisionConvenio.convenio_id == convenio_id, RevisionConvenio.estado == "PENDIENTE",
            ))
            servicio.aprobar(convenio_id, revision.id, convenio.version_actual, db.get(Usuario, usuario_id))
        version = convenio.version_actual
    # Los aliados se crean con transacciones propias para que ambas sesiones los vean.
    aliados = []
    with fabrica() as db:
        for _ in range(2):
            aliado = Aliado(nombre="Aliado HT-16", tipo="UNIVERSIDAD", tipo_identificacion="NIT",
                            identificacion=uuid4().hex, correo="contraparte@example.com", activo=True)
            db.add(aliado)
            db.commit()
            aliados.append(aliado.id)
    try:
        yield fabrica, convenio_id, usuarios[0], version, aliados
    finally:
        with fabrica() as db:
            for modelo in (ObservacionRevision, RevisionConvenio, HistorialEtapa, BorradorConvenio, VersionConvenio):
                db.execute(delete(modelo).where(modelo.convenio_id == convenio_id))
            db.execute(delete(Notificacion).where(Notificacion.usuario_id.in_(usuarios)))
            db.execute(delete(Auditoria).where(Auditoria.usuario_id.in_(usuarios)))
            db.execute(delete(Convenio).where(Convenio.id == convenio_id))
            db.execute(delete(Aliado).where(Aliado.id.in_(aliados)))
            db.execute(delete(Usuario).where(Usuario.id.in_(usuarios)))
            db.commit()


@pytest.mark.parametrize("operacion", ["enviar", "reenviar", "asignar"])
def test_operaciones_simultaneas_no_duplican_ni_reutilizan_avales(escenario, operacion):
    fabrica, convenio_id, gestor_id, version, aliados = escenario
    correo = CorreoLocal()
    revision_id = invitacion_id = None
    if operacion != "asignar":
        with fabrica() as db:
            gestor = db.get(Usuario, gestor_id)
            servicio = ServicioConvenios(db, enviador=correo, frontend_url="http://localhost:5173")
            servicio.actualizar(convenio_id, ConvenioElaboracionActualizar(aliado_id=aliados[0]), gestor)
            if operacion == "reenviar":
                revision_id = servicio.enviar_a_contraparte(convenio_id, version, gestor).id
                invitacion_id = db.scalar(select(InvitacionRevisionContraparte.id).where(
                    InvitacionRevisionContraparte.revision_convenio_id == revision_id,
                ))
    barrera = Barrier(2, timeout=15)

    def ejecutar(indice):
        with fabrica() as db:
            gestor = db.get(Usuario, gestor_id)
            # Precarga deliberada: el bloqueo debe releer el estado tras esperar.
            convenio_precargado = db.get(Convenio, convenio_id)
            assert convenio_precargado.etapa_actual.codigo == "REVISION_CONTRAPARTE"
            servicio = ServicioConvenios(db, enviador=correo, frontend_url="http://localhost:5173")
            barrera.wait()
            try:
                if operacion == "enviar":
                    servicio.enviar_a_contraparte(convenio_id, version, gestor)
                elif operacion == "reenviar":
                    servicio.reenviar_invitacion_contraparte(convenio_id, revision_id, gestor, invitacion_id)
                else:
                    servicio.actualizar(convenio_id, ConvenioElaboracionActualizar(aliado_id=aliados[indice]), gestor)
                return 200
            except (RevisionNoDisponible, ConvenioNoEditable):
                db.rollback()
                return 409
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(ejecutar, (0, 1)))
    with fabrica() as db:
        convenio = db.get(Convenio, convenio_id)
        pendientes = db.scalar(select(func.count()).select_from(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_id, RevisionConvenio.tipo == "CONTRAPARTE",
        ))
        if operacion == "asignar":
            assert resultados == [200, 200]
            assert convenio.etapa_actual.codigo == "ELABORACION"
            assert pendientes == 0
            assert not correo.mensajes
        else:
            assert sorted(resultados) == [200, 409]
            assert pendientes == 1
            assert len(correo.mensajes) == (2 if operacion == "reenviar" else 1)
            activas = db.scalar(select(func.count()).select_from(InvitacionRevisionContraparte)
                .join(RevisionConvenio).where(
                    RevisionConvenio.convenio_id == convenio_id,
                    InvitacionRevisionContraparte.revocado_en.is_(None),
                ))
            assert activas == 1


def test_envio_y_rectificacion_simultaneos_conservan_la_contraparte_avalada(escenario):
    fabrica, convenio_id, gestor_id, version, aliados = escenario
    correo = CorreoLocal()
    with fabrica() as db:
        ServicioConvenios(db).actualizar(convenio_id,
            ConvenioElaboracionActualizar(aliado_id=aliados[0]), db.get(Usuario, gestor_id))
    barrera = Barrier(2, timeout=15)

    def ejecutar(enviar):
        with fabrica() as db:
            gestor = db.get(Usuario, gestor_id)
            previo = db.get(Convenio, convenio_id)
            assert previo.aliado_id == aliados[0]
            servicio = ServicioConvenios(db, enviador=correo, frontend_url="http://localhost:5173")
            barrera.wait()
            try:
                if enviar:
                    servicio.enviar_a_contraparte(convenio_id, version, gestor)
                else:
                    servicio.actualizar(convenio_id, ConvenioElaboracionActualizar(aliado_id=aliados[1]), gestor)
                return 200
            except (RevisionNoDisponible, ConvenioNoEditable):
                db.rollback()
                return 409
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(ejecutar, (True, False)))
    assert sorted(resultados) == [200, 409]
    with fabrica() as db:
        convenio = db.get(Convenio, convenio_id)
        if resultados[0] == 200:
            assert convenio.aliado_id == aliados[0]
            assert convenio.etapa_actual.codigo == "REVISION_CONTRAPARTE"
            assert len(correo.mensajes) == 1
        else:
            assert convenio.aliado_id == aliados[1]
            assert convenio.etapa_actual.codigo == "ELABORACION"
            assert not correo.mensajes


def test_identidad_no_puede_cambiar_entre_validacion_y_commit_del_envio(escenario):
    fabrica, convenio_id, gestor_id, version, aliados = escenario
    con_bloqueo = Event()
    continuar = Event()

    class CorreoEnEspera(CorreoLocal):
        def enviar(self, mensaje):
            con_bloqueo.set()
            if not continuar.wait(15):
                raise RuntimeError("La prueba no liberó el envío")
            super().enviar(mensaje)

    correo = CorreoEnEspera()
    with fabrica() as db:
        ServicioConvenios(db).actualizar(convenio_id,
            ConvenioElaboracionActualizar(aliado_id=aliados[0]), db.get(Usuario, gestor_id))

    def enviar():
        with fabrica() as db:
            return ServicioConvenios(db, enviador=correo, frontend_url="http://localhost:5173").enviar_a_contraparte(
                convenio_id, version, db.get(Usuario, gestor_id),
            ).id

    with ThreadPoolExecutor(max_workers=1) as pool:
        envio = pool.submit(enviar)
        try:
            assert con_bloqueo.wait(15)
            with fabrica() as db:
                db.execute(text("SET LOCAL lock_timeout = '250ms'"))
                with pytest.raises(OperationalError):
                    db.execute(update(Aliado).where(Aliado.id == aliados[0]).values(nombre="Cambio durante el envío"))
                db.rollback()
        finally:
            continuar.set()
        revision_id = envio.result(timeout=15)
    assert len(correo.mensajes) == 1
    # El bloqueo no es un veto global: la edición queda permitida después del commit.
    with fabrica() as db:
        aliado = db.get(Aliado, aliados[0])
        assert aliado.nombre == "Aliado HT-16"
        aliado.nombre = "Identidad posterior al envío"
        db.commit()
        invitacion_id = db.scalar(select(InvitacionRevisionContraparte.id).where(
            InvitacionRevisionContraparte.revision_convenio_id == revision_id,
        ))
        with pytest.raises(IdentidadAliadoIncompatible):
            ServicioConvenios(db, enviador=correo, frontend_url="http://localhost:5173").reenviar_invitacion_contraparte(
                convenio_id, revision_id, db.get(Usuario, gestor_id), invitacion_id,
            )
    assert len(correo.mensajes) == 1


def _enlace_para_concurrencia(escenario):
    fabrica, convenio_id, gestor_id, version, aliados = escenario
    correo = CorreoLocal()
    with fabrica() as db:
        gestor = db.get(Usuario, gestor_id)
        servicio = ServicioConvenios(db, enviador=correo, frontend_url="http://localhost:5173")
        servicio.actualizar(convenio_id, ConvenioElaboracionActualizar(aliado_id=aliados[0]), gestor)
        revision = servicio.enviar_a_contraparte(convenio_id, version, gestor)
        invitacion_id = db.scalar(select(InvitacionRevisionContraparte.id).where(
            InvitacionRevisionContraparte.revision_convenio_id == revision.id,
        ))
        token = correo.mensajes[-1].texto.split("#token=", 1)[1].splitlines()[0]
        return fabrica, convenio_id, gestor_id, version, aliados[0], revision.id, invitacion_id, token


def _operar_enlace(db, accion, token):
    servicio = ServicioContraparteExterna(db)
    if accion == "acceso":
        servicio.acceder(token)
        db.commit()  # Fin de la lectura pública y construcción de su respuesta.
    elif accion == "aprobar":
        firma = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            "+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        servicio.aprobar(token, "Representante", "Director", firma)
    else:
        servicio.devolver(token, "Representante", "Director", ["Ajustar proyecto"])


@pytest.mark.parametrize("accion", ["acceso", "aprobar", "devolver"])
def test_operacion_publica_retiene_identidad_hasta_terminar(escenario, monkeypatch, accion):
    fabrica, _, _, _, aliado_id, _, _, token = _enlace_para_concurrencia(escenario)
    validado = Event()
    terminar = Event()
    original = contraparte_externa.identidad_autorizada_para_revision

    def verificar_y_esperar(db, convenio, version):
        resultado = original(db, convenio, version)
        assert resultado is True
        validado.set()
        if not terminar.wait(15):
            raise RuntimeError("La prueba no liberó la operación pública")
        return resultado

    monkeypatch.setattr(contraparte_externa, "identidad_autorizada_para_revision", verificar_y_esperar)
    def operar():
        with fabrica() as db:
            _operar_enlace(db, accion, token)

    with ThreadPoolExecutor(max_workers=1) as pool:
        futuro = pool.submit(operar)
        try:
            assert validado.wait(15)
            with fabrica() as editor:
                editor.execute(text("SET LOCAL lock_timeout = '250ms'"))
                with pytest.raises(OperationalError):
                    editor.execute(update(Aliado).where(Aliado.id == aliado_id).values(nombre="Edición en carrera"))
                editor.rollback()
        finally:
            terminar.set()
        futuro.result(timeout=15)
    with fabrica() as db:
        assert db.get(Aliado, aliado_id).nombre == "Aliado HT-16"
        db.execute(update(Aliado).where(Aliado.id == aliado_id).values(nombre="Edición después del commit"))
        db.commit()


@pytest.mark.parametrize("accion", ["acceso", "aprobar", "devolver"])
def test_edicion_ganadora_se_relee_antes_de_aceptar_el_enlace(escenario, accion):
    fabrica, convenio_id, _, _, aliado_id, revision_id, _, token = _enlace_para_concurrencia(escenario)
    intento = Event()

    def operar():
        with fabrica() as db:
            assert db.get(Aliado, aliado_id).nombre == "Aliado HT-16"  # Precarga anterior al commit del editor.
            def observar(_conexion, _cursor, sentencia, _parametros, _contexto, _varios):
                if "FROM aliado" in sentencia and "FOR SHARE" in sentencia:
                    intento.set()
            event.listen(db.connection(), "before_cursor_execute", observar)
            try:
                _operar_enlace(db, accion, token)
                return "ACEPTADO"
            except EnlaceContraparteError as exc:
                return exc.codigo

    with fabrica() as editor:
        editor.execute(update(Aliado).where(Aliado.id == aliado_id).values(nombre="Identidad editada primero"))
        with ThreadPoolExecutor(max_workers=1) as pool:
            futuro = pool.submit(operar)
            try:
                assert intento.wait(15)
            finally:
                editor.commit()
            assert futuro.result(timeout=15) == "ENLACE_NO_DISPONIBLE"
    with fabrica() as db:
        assert db.get(RevisionConvenio, revision_id).estado == "PENDIENTE"
        assert db.get(Convenio, convenio_id).etapa_actual.codigo == "REVISION_CONTRAPARTE"


@pytest.mark.parametrize("operacion_publica", ["acceso", "aprobar", "devolver", "otra_recuperacion"])
def test_recuperacion_serializa_reintentos_y_operaciones_publicas(escenario, operacion_publica):
    fabrica, convenio_id, gestor_id, version, aliado_id, revision_id, invitacion_id, token = _enlace_para_concurrencia(escenario)
    with fabrica() as db:
        db.execute(update(Aliado).where(Aliado.id == aliado_id).values(nombre="Identidad incompatible"))
        db.commit()
    barrera = Barrier(2, timeout=15)

    def ejecutar(recuperar):
        with fabrica() as db:
            gestor = db.get(Usuario, gestor_id)
            assert db.get(RevisionConvenio, revision_id).estado == "PENDIENTE"
            barrera.wait()
            try:
                if recuperar or operacion_publica == "otra_recuperacion":
                    ServicioConvenios(db).invalidar_revision_por_identidad(
                        convenio_id, revision_id, version, invitacion_id, gestor,
                    )
                    return 200
                _operar_enlace(db, operacion_publica, token)
                return 200
            except EnlaceContraparteError as exc:
                assert exc.codigo == "ENLACE_NO_DISPONIBLE"
                return 400
            except RevisionNoDisponible:
                return 409

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(ejecutar, (True, False)))
    assert sorted(resultados) == ([200, 409] if operacion_publica == "otra_recuperacion" else [200, 400])
    with fabrica() as db:
        revision = db.get(RevisionConvenio, revision_id)
        assert revision.estado == "RESUELTA" and revision.resultado == "DEVUELTA"
        assert revision.resuelta_por_id == gestor_id and revision.respuesta_contraparte is None
        assert db.get(InvitacionRevisionContraparte, invitacion_id).revocado_en is not None
        assert db.get(Convenio, convenio_id).etapa_actual.codigo == "ELABORACION"
        assert db.scalar(select(func.count()).select_from(HistorialEtapa).where(
            HistorialEtapa.convenio_id == convenio_id,
            HistorialEtapa.observacion.like("Invalidación administrativa%"),
        )) == 1
