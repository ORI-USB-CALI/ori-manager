from collections.abc import Callable
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.contacto_aliado import ContactoAliado
from backend.models.convenio import Convenio
from backend.models.enums import (
    AlcanceConvenio,
    EstadoConvenio,
    EstadoSolicitud,
    TipoAliado,
    TipoIdentificacion,
    TipoSolicitante,
)
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.usuario import Usuario
from backend.services.aliados import (
    ConflictoAliado,
    resolver_aliado_existente_para_solicitud,
    resolver_aliado_para_convenio,
)


@pytest.fixture
def crear_aliado(db: Session) -> Callable[..., Aliado]:
    def _crear(**cambios) -> Aliado:
        datos = {
            "nombre": "Universidad aliada",
            "tipo": TipoAliado.UNIVERSIDAD.value,
            "tipo_identificacion": TipoIdentificacion.NIT.value,
            "identificacion": str(900000000 + (uuid4().int % 99999999)),
            "correo": "contacto@aliada.example",
            "activo": True,
        }
        datos.update(cambios)
        aliado = Aliado(**datos)
        db.add(aliado)
        db.commit()
        return aliado

    return _crear


@pytest.fixture
def crear_solicitud(db: Session, crear_usuario) -> Callable[..., SolicitudConvenio]:
    def _crear(solicitante: Usuario | None = None, **cambios) -> SolicitudConvenio:
        usuario = solicitante or crear_usuario()
        datos = {
            "consecutivo": f"SOL-{uuid4().hex}",
            "tipo_solicitante": TipoSolicitante.INTERNO.value,
            "solicitante_id": usuario.id,
            "objeto": "Solicitud de cooperación académica",
            "estado": EstadoSolicitud.APROBADA.value,
        }
        datos.update(cambios)
        solicitud = SolicitudConvenio(**datos)
        db.add(solicitud)
        db.commit()
        return solicitud

    return _crear


def _crear_convenio(
    db: Session,
    solicitud: SolicitudConvenio,
    usuario: Usuario,
    aliado: Aliado | None = None,
    estado: EstadoConvenio = EstadoConvenio.EN_TRAMITE,
) -> Convenio:
    # Nace en ELABORACION igual que en ServicioConvenios.crear(): sin etapa el
    # convenio no sería editable y no reflejaría un registro real.
    elaboracion = db.scalar(select(Etapa).where(Etapa.codigo == "ELABORACION"))
    convenio = Convenio(
        solicitud_id=solicitud.id,
        aliado_id=aliado.id if aliado else None,
        estado=estado.value,
        objeto="Cooperación internacional",
        alcance=AlcanceConvenio.INSTITUCIONAL.value,
        etapa_actual_id=elaboracion.id if elaboracion else None,
        creado_por_id=usuario.id,
    )
    db.add(convenio)
    db.commit()
    return convenio


def _autenticar(client, crear_usuario, entrar_como, rol: CodigoRol) -> Usuario:
    usuario = crear_usuario(
        rol,
        TipoUsuario.EXTERNO if rol == CodigoRol.SOLICITANTE_EXTERNO else TipoUsuario.INTERNO,
    )
    entrar_como(usuario)
    return usuario


def _payload_convenio(solicitud_id: int) -> dict:
    return {
        "solicitud_id": solicitud_id,
        "objeto": "Convenio de movilidad académica",
        "alcance": "INSTITUCIONAL",
    }


# HU04 CA-01 a CA-05: contraparte persistida y formalización.
def _contraparte(numero: str, correo: str = "contacto@fundacionabc.org") -> dict:
    return {
        "nombre_aliado_propuesto": "Fundación ABC",
        "tipo_identificacion_aliado_propuesto": TipoIdentificacion.NIT.value,
        "identificacion_aliado_propuesto": numero,
        "tipo_aliado_propuesto": TipoAliado.ENTIDAD_GUBERNAMENTAL.value,
        "correo_aliado_propuesto": correo,
    }


def _nit_unico() -> str:
    return str(900000000 + (uuid4().int % 99999999))


def test_hu04_ca01_solicitud_conserva_contraparte_sin_crear_aliado(
    db, crear_usuario, crear_solicitud
) -> None:
    usuario = crear_usuario()
    identificacion = _nit_unico()
    solicitud = crear_solicitud(usuario, **_contraparte(identificacion))
    convenio = _crear_convenio(db, solicitud, usuario)
    assert solicitud.solicitante_id == usuario.id
    assert solicitud.nombre_aliado_propuesto == "Fundación ABC"
    assert solicitud.tipo_identificacion_aliado_propuesto == TipoIdentificacion.NIT
    assert solicitud.identificacion_aliado_propuesto == identificacion
    assert solicitud.tipo_aliado_propuesto == TipoAliado.ENTIDAD_GUBERNAMENTAL
    assert solicitud.correo_aliado_propuesto == "contacto@fundacionabc.org"
    assert resolver_aliado_existente_para_solicitud(db, solicitud) is None
    assert resolver_aliado_para_convenio(db, convenio) is None
    assert convenio.estado == EstadoConvenio.EN_TRAMITE
    assert solicitud.aliado_id is None and convenio.aliado_id is None
    assert db.scalar(select(Aliado).where(Aliado.identificacion == identificacion)) is None


def test_hu04_ca02_reconoce_aliado_por_pareja_sin_crear(
    db, crear_usuario, crear_solicitud, crear_aliado
) -> None:
    aliado = crear_aliado(identificacion="900123456")
    solicitud = crear_solicitud(crear_usuario(), **_contraparte("900123456"))
    encontrado = resolver_aliado_existente_para_solicitud(db, solicitud)
    assert encontrado is not None and encontrado.id == aliado.id
    assert solicitud.aliado_id == aliado.id
    assert len(db.scalars(select(Aliado).where(Aliado.identificacion == "900123456")).all()) == 1


def test_hu04_documento_igual_de_tipo_distinto_no_colisiona_ni_se_confunde(
    db, crear_usuario, crear_solicitud, crear_aliado
) -> None:
    nit = crear_aliado(identificacion="900123456")
    pasaporte = crear_aliado(
        identificacion="900123456", tipo_identificacion=TipoIdentificacion.PASAPORTE.value
    )
    solicitud = crear_solicitud(crear_usuario(), **{
        **_contraparte("900123456"),
        "tipo_identificacion_aliado_propuesto": TipoIdentificacion.PASAPORTE.value,
    })
    encontrado = resolver_aliado_existente_para_solicitud(db, solicitud)
    assert encontrado is not None and encontrado.id == pasaporte.id != nit.id


def test_hu04_vigente_reutiliza_aliado_ya_asociado_a_solicitud(
    db, crear_usuario, crear_solicitud, crear_aliado
) -> None:
    usuario = crear_usuario()
    aliado = crear_aliado(identificacion="900123456")
    solicitud = crear_solicitud(
        usuario, aliado_id=aliado.id,
        correo_aliado_propuesto="nuevo@example.com",
    )
    convenio = _crear_convenio(db, solicitud, usuario, estado=EstadoConvenio.VIGENTE)
    resultado = resolver_aliado_para_convenio(db, convenio)
    assert resultado is not None and resultado.id == aliado.id
    assert convenio.aliado_id == aliado.id
    assert resultado.correo == "nuevo@example.com"


def test_hu04_ca03_ca04_vigente_crea_y_reutiliza_desde_solicitud(
    db, crear_usuario, crear_solicitud
) -> None:
    usuario = crear_usuario()
    solicitud_1 = crear_solicitud(usuario, **_contraparte("900777222"))
    convenio_1 = _crear_convenio(db, solicitud_1, usuario, estado=EstadoConvenio.VIGENTE)
    aliado_1 = resolver_aliado_para_convenio(db, convenio_1)
    db.commit()
    solicitud_2 = crear_solicitud(usuario, **_contraparte("900777222"))
    convenio_2 = _crear_convenio(db, solicitud_2, usuario, estado=EstadoConvenio.VIGENTE)
    aliado_2 = resolver_aliado_para_convenio(db, convenio_2)
    db.commit()
    assert aliado_1 is not None and aliado_2 is not None
    assert aliado_1.id == aliado_2.id
    assert aliado_1.correo == "contacto@fundacionabc.org"
    assert convenio_1.aliado_id == aliado_1.id == solicitud_1.aliado_id
    assert convenio_2.aliado_id == aliado_1.id == solicitud_2.aliado_id
    assert {convenio.id for convenio in aliado_1.convenios} == {convenio_1.id, convenio_2.id}


def test_hu04_ca05_correo_distinto_conserva_contactos(
    db, crear_usuario, crear_solicitud, crear_aliado
) -> None:
    usuario = crear_usuario()
    aliado = crear_aliado(identificacion="900123456", correo="anterior@example.com")
    solicitud = crear_solicitud(usuario, **_contraparte("900123456", "nuevo@example.com"))
    convenio = _crear_convenio(db, solicitud, usuario, estado=EstadoConvenio.VIGENTE)
    resultado = resolver_aliado_para_convenio(db, convenio)
    db.commit()
    assert resultado is not None and resultado.id == aliado.id
    assert resultado.correo == "nuevo@example.com"
    correos = set(db.scalars(select(ContactoAliado.correo).where(ContactoAliado.aliado_id == aliado.id)))
    assert correos == {"anterior@example.com", "nuevo@example.com"}
    resolver_aliado_para_convenio(db, convenio)
    db.flush()
    assert len(db.scalars(select(ContactoAliado).where(ContactoAliado.aliado_id == aliado.id)).all()) == 2


def test_hu04_aliado_inactivo_no_se_reactiva_al_formalizar(
    db, crear_usuario, crear_solicitud, crear_aliado
) -> None:
    usuario = crear_usuario()
    aliado = crear_aliado(identificacion="900123456", activo=False)
    solicitud = crear_solicitud(usuario, **_contraparte("900123456"))
    convenio = _crear_convenio(db, solicitud, usuario, estado=EstadoConvenio.VIGENTE)
    with pytest.raises(ConflictoAliado, match="reactivarse"):
        resolver_aliado_para_convenio(db, convenio)
    assert aliado.activo is False
    assert convenio.aliado_id is None

# HU04 CA-06 a CA-12: gestión, permisos, estado e integridad.
@pytest.mark.parametrize(
    "rol",
    [CodigoRol.ADMINISTRADOR_ORI, CodigoRol.GESTOR_ORI, CodigoRol.REVISOR_ORI],
)
def test_hu04_ca06_roles_autorizados_consultan(
    rol, client, crear_usuario, entrar_como
) -> None:
    _autenticar(client, crear_usuario, entrar_como, rol)
    assert client.get("/api/aliados").status_code == 200


def test_hu04_tc06_ca06_tres_roles_consultan_perfil_y_estado(
    client, crear_usuario, entrar_como, crear_aliado
) -> None:
    identificacion = _nit_unico()
    aliado = crear_aliado(identificacion=identificacion, activo=True)
    for rol in (
        CodigoRol.ADMINISTRADOR_ORI,
        CodigoRol.GESTOR_ORI,
        CodigoRol.REVISOR_ORI,
    ):
        _autenticar(client, crear_usuario, entrar_como, rol)
        respuesta = client.get(f"/api/aliados/{aliado.id}")
        assert respuesta.status_code == 200
        assert respuesta.json()["id"] == aliado.id
        assert respuesta.json()["identificacion"] == identificacion
        assert respuesta.json()["activo"] is True


def test_hu04_tc13_ca12_revisor_no_modifica_telefono(
    db, client, crear_usuario, entrar_como, crear_aliado
) -> None:
    aliado = crear_aliado(identificacion="900123456", telefono="6011234567")
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)
    respuesta = client.patch(
        f"/api/aliados/{aliado.id}", json={"telefono": "6017654321"}
    )
    assert respuesta.status_code == 403
    db.refresh(aliado)
    assert aliado.telefono == "6011234567"


def test_hu04_tc14_ca12_revisor_no_cambia_ningun_estado(
    db, client, crear_usuario, entrar_como, crear_aliado
) -> None:
    activo = crear_aliado(identificacion="900123456", activo=True)
    inactivo = crear_aliado(identificacion="900777222", activo=False)
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)

    inactivar = client.patch(
        f"/api/aliados/{activo.id}/estado", json={"activo": False}
    )
    reactivar = client.patch(
        f"/api/aliados/{inactivo.id}/estado", json={"activo": True}
    )
    assert inactivar.status_code == 403
    assert reactivar.status_code == 403
    db.refresh(activo)
    db.refresh(inactivo)
    assert activo.activo is True
    assert inactivo.activo is False


def test_hu04_ca07_ca12_revisor_no_edita_y_gestor_si(
    client, crear_usuario, entrar_como, crear_aliado
) -> None:
    aliado = crear_aliado()
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)
    assert client.patch(f"/api/aliados/{aliado.id}", json={"ciudad": "Cali"}).status_code == 403
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    respuesta = client.patch(f"/api/aliados/{aliado.id}", json={"ciudad": "Cali"})
    assert respuesta.status_code == 200
    assert respuesta.json()["ciudad"] == "Cali"


def test_hu04_ca08_ca09_ca10_inactivar_segun_estado_y_reactivar(
    db, client, crear_usuario, entrar_como, crear_aliado, crear_solicitud
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    aliado = crear_aliado()
    solicitud = crear_solicitud(gestor)
    convenio = _crear_convenio(db, solicitud, gestor, aliado, EstadoConvenio.VIGENTE)
    assert client.patch(f"/api/aliados/{aliado.id}/estado", json={"activo": False}).status_code == 409
    convenio.estado = EstadoConvenio.VENCIDO.value
    db.commit()
    inactivar = client.patch(f"/api/aliados/{aliado.id}/estado", json={"activo": False})
    assert inactivar.status_code == 200 and inactivar.json()["activo"] is False
    reactivar = client.patch(f"/api/aliados/{aliado.id}/estado", json={"activo": True})
    assert reactivar.status_code == 200 and reactivar.json()["activo"] is True


def test_hu04_por_vencer_bloquea_y_finalizado_no_bloquea(
    db, client, crear_usuario, entrar_como, crear_aliado, crear_solicitud
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    aliado = crear_aliado()
    convenio = _crear_convenio(db, crear_solicitud(gestor), gestor, aliado, EstadoConvenio.POR_VENCER)
    assert client.patch(f"/api/aliados/{aliado.id}/estado", json={"activo": False}).status_code == 409
    convenio.estado = EstadoConvenio.FINALIZADO.value
    db.commit()
    assert client.patch(f"/api/aliados/{aliado.id}/estado", json={"activo": False}).status_code == 200


def test_hu04_ca11_identificacion_unica_y_no_editable_por_patch_ordinario(
    db, client, crear_usuario, entrar_como, crear_aliado
) -> None:
    aliado = crear_aliado(identificacion="900123456")
    db.add(Aliado(nombre="Duplicado", tipo=TipoAliado.COLEGIO.value, tipo_identificacion=TipoIdentificacion.NIT.value, identificacion="900123456"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    assert client.patch(f"/api/aliados/{aliado.id}", json={"identificacion": "900555111"}).status_code == 422
    assert client.patch(f"/api/aliados/{aliado.id}", json={"tipo_identificacion": "PASAPORTE"}).status_code == 422
    otro_tipo = crear_aliado(tipo_identificacion=TipoIdentificacion.PASAPORTE.value, identificacion="900123456")
    assert otro_tipo.id != aliado.id


def test_hu04_correccion_admin_permiso_colision_y_convenios(
    db, client, crear_usuario, entrar_como, crear_aliado, crear_solicitud
) -> None:
    admin = _autenticar(client, crear_usuario, entrar_como, CodigoRol.ADMINISTRADOR_ORI)
    aliado = crear_aliado(identificacion="900123456")
    otro = crear_aliado(identificacion=_nit_unico())
    convenio = _crear_convenio(db, crear_solicitud(admin), admin, aliado)
    ruta = f"/api/aliados/{aliado.id}/identificacion"
    duplicado = client.patch(ruta, json={"tipo_identificacion": "NIT", "identificacion": otro.identificacion})
    assert duplicado.status_code == 409
    corregido = client.patch(ruta, json={"tipo_identificacion": "PASAPORTE", "identificacion": " 900777222 "})
    assert corregido.status_code == 200
    assert corregido.json()["tipo_identificacion"] == "PASAPORTE"
    assert corregido.json()["identificacion"] == "900777222"
    assert convenio.aliado_id == aliado.id
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)
    assert client.patch(ruta, json={"tipo_identificacion": "NIT", "identificacion": "900777222"}).status_code == 403


def test_hu04_gestor_puede_corregir_identificacion(
    db, client, crear_usuario, entrar_como, crear_aliado
) -> None:
    aliado = crear_aliado(identificacion=_nit_unico())
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    nueva_identificacion = _nit_unico()

    respuesta = client.patch(
        f"/api/aliados/{aliado.id}/identificacion",
        json={"tipo_identificacion": "PASAPORTE", "identificacion": nueva_identificacion},
    )

    assert respuesta.status_code == 200
    db.refresh(aliado)
    assert aliado.tipo_identificacion == TipoIdentificacion.PASAPORTE
    assert aliado.identificacion == nueva_identificacion


@pytest.mark.parametrize("rol", [CodigoRol.ADMINISTRADOR_ORI, CodigoRol.GESTOR_ORI])
def test_hu04_administracion_colision_no_persiste_cambios_ordinarios(
    rol, db, client, crear_usuario, entrar_como, crear_aliado
) -> None:
    aliado = crear_aliado(identificacion=_nit_unico(), telefono="6011111111")
    otro = crear_aliado(identificacion=_nit_unico())
    _autenticar(client, crear_usuario, entrar_como, rol)

    respuesta = client.patch(
        f"/api/aliados/{aliado.id}/administracion",
        json={
            "telefono": "6019999999",
            "tipo_identificacion": "NIT",
            "identificacion": otro.identificacion,
        },
    )

    assert respuesta.status_code == 409
    db.refresh(aliado)
    assert aliado.telefono == "6011111111"
    assert aliado.tipo_identificacion == TipoIdentificacion.NIT
    assert aliado.identificacion != otro.identificacion


@pytest.mark.parametrize("rol", [CodigoRol.ADMINISTRADOR_ORI, CodigoRol.GESTOR_ORI])
def test_hu04_administracion_edicion_completa_valida(
    rol, db, client, crear_usuario, entrar_como, crear_aliado
) -> None:
    aliado = crear_aliado(identificacion=_nit_unico(), telefono="6011111111")
    nueva_identificacion = _nit_unico()
    _autenticar(client, crear_usuario, entrar_como, rol)

    respuesta = client.patch(
        f"/api/aliados/{aliado.id}/administracion",
        json={
            "nombre": "Fundación ABC",
            "telefono": "6019999999",
            "tipo_identificacion": "NIT",
            "identificacion": nueva_identificacion,
        },
    )

    assert respuesta.status_code == 200
    db.refresh(aliado)
    assert aliado.nombre == "Fundación ABC"
    assert aliado.telefono == "6019999999"
    assert aliado.tipo_identificacion == TipoIdentificacion.NIT
    assert aliado.identificacion == nueva_identificacion


def test_hu04_revisor_no_puede_modificar_identificacion(
    db, client, crear_usuario, entrar_como, crear_aliado
) -> None:
    aliado = crear_aliado(identificacion=_nit_unico(), telefono="6011111111")
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)

    correccion = client.patch(
        f"/api/aliados/{aliado.id}/identificacion",
        json={"tipo_identificacion": "NIT", "identificacion": _nit_unico()},
    )

    respuesta = client.patch(
        f"/api/aliados/{aliado.id}/administracion",
        json={
            "telefono": "6019999999",
            "tipo_identificacion": "NIT",
            "identificacion": _nit_unico(),
        },
    )

    assert correccion.status_code == 403
    assert respuesta.status_code == 403
    db.refresh(aliado)
    assert aliado.telefono == "6011111111"


def test_hu04_rutas_sin_sesion_responden_401(client) -> None:
    client.cookies.clear()
    assert client.get("/api/aliados").status_code == 401
    assert client.patch("/api/aliados/1", json={"nombre": "X"}).status_code == 401
    assert client.patch("/api/aliados/1/estado", json={"activo": False}).status_code == 401


# HU05 CA-01 a CA-08: perfil consolidado, filtrado y errores.
def test_hu05_perfil_devuelve_todos_y_solo_convenios_del_aliado(
    db, client, crear_usuario, entrar_como, crear_aliado, crear_solicitud
) -> None:
    revisor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)
    aliado = crear_aliado()
    otro = crear_aliado()
    propios = {
        _crear_convenio(db, crear_solicitud(revisor), revisor, aliado, EstadoConvenio.VIGENTE).id,
        _crear_convenio(db, crear_solicitud(revisor), revisor, aliado, EstadoConvenio.FINALIZADO).id,
    }
    ajeno = _crear_convenio(db, crear_solicitud(revisor), revisor, otro).id

    respuesta = client.get(f"/api/aliados/{aliado.id}")
    assert respuesta.status_code == 200
    ids = {item["id"] for item in respuesta.json()["convenios"]}
    assert ids == propios and ajeno not in ids


def test_hu05_aliado_sin_convenios_e_inactivo_sigue_consultable(
    client, crear_usuario, entrar_como, crear_aliado
) -> None:
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)
    aliado = crear_aliado(activo=False)
    respuesta = client.get(f"/api/aliados/{aliado.id}")
    assert respuesta.status_code == 200
    assert respuesta.json()["activo"] is False
    assert respuesta.json()["convenios"] == []


def test_hu05_404_403_y_401(client, crear_usuario, entrar_como) -> None:
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)
    assert client.get("/api/aliados/999999999").status_code == 404
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.SOLICITANTE_INTERNO)
    assert client.get("/api/aliados/1").status_code == 403
    client.cookies.clear()
    assert client.get("/api/aliados/1").status_code == 401


# HU06 CA-01 a CA-08: registro, consulta, edición y permisos.
def test_hu06_ca01_ca03_ca04_ca06_crea_desde_sesion_sin_aliado(
    db, client, crear_usuario, entrar_como, crear_solicitud
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(gestor)
    respuesta = client.post("/api/convenios", json=_payload_convenio(solicitud.id))
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["id"] > 0
    assert cuerpo["aliado_id"] is None
    assert cuerpo["estado"] == EstadoConvenio.EN_TRAMITE
    assert cuerpo["creado_por_id"] == gestor.id
    assert cuerpo["creado_por"]["id"] == gestor.id
    assert cuerpo["creado_en"]
    solicitud_persistida = db.get(SolicitudConvenio, solicitud.id)
    assert solicitud_persistida is not None
    assert solicitud_persistida.estado == EstadoSolicitud.APROBADA
    convenio = db.get(Convenio, cuerpo["id"])
    assert convenio is not None
    elaboracion = db.scalar(select(Etapa).where(Etapa.codigo == "ELABORACION"))
    assert elaboracion is not None
    assert convenio.etapa_actual_id == elaboracion.id
    assert convenio.etapa_actual.codigo == "ELABORACION"
    historiales = list(
        db.scalars(
            select(HistorialEtapa).where(HistorialEtapa.convenio_id == convenio.id)
        )
    )
    assert len(historiales) == 1
    historial = historiales[0]
    assert historial.etapa_origen_id is None
    assert historial.etapa_destino_id == elaboracion.id
    assert historial.usuario_id == gestor.id
    assert historial.responsable_id == gestor.id
    assert historial.observacion is None
    assert (
        db.scalar(
            select(ObservacionRevision).where(
                ObservacionRevision.convenio_id == convenio.id
            )
        )
        is None
    )
    assert client.get(f"/api/convenios/{cuerpo['id']}").status_code == 200


@pytest.mark.parametrize(
    "estado",
    [
        EstadoSolicitud.BORRADOR,
        EstadoSolicitud.RADICADA,
        EstadoSolicitud.EN_ESTUDIO,
        EstadoSolicitud.DEVUELTA,
        EstadoSolicitud.RECHAZADA,
    ],
)
def test_convenio_rechaza_solicitud_no_aprobada_sin_persistir(
    estado, db, client, crear_usuario, entrar_como, crear_solicitud
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(gestor, estado=estado.value)

    respuesta = client.post("/api/convenios", json=_payload_convenio(solicitud.id))

    assert respuesta.status_code == 409
    assert (
        db.scalar(select(Convenio).where(Convenio.solicitud_id == solicitud.id))
        is None
    )


def test_hu06_aliado_se_deriva_exclusivamente_de_solicitud(
    client, crear_usuario, entrar_como, crear_solicitud, crear_aliado
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    aliado = crear_aliado()
    solicitud = crear_solicitud(gestor, aliado_id=aliado.id)

    respuesta = client.post("/api/convenios", json=_payload_convenio(solicitud.id))

    assert respuesta.status_code == 201
    assert respuesta.json()["aliado_id"] == aliado.id


def test_hu06_aliado_inactivo_derivado_impide_crear_convenio(
    db, client, crear_usuario, entrar_como, crear_solicitud, crear_aliado
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    aliado = crear_aliado(activo=False)
    solicitud = crear_solicitud(gestor, aliado_id=aliado.id)

    respuesta = client.post("/api/convenios", json=_payload_convenio(solicitud.id))

    assert respuesta.status_code == 422
    assert (
        db.scalar(select(Convenio).where(Convenio.solicitud_id == solicitud.id))
        is None
    )


def test_hu06_post_rechaza_campos_controlados_por_servidor(
    client, crear_usuario, entrar_como, crear_solicitud, crear_aliado
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(gestor)
    aliado = crear_aliado()
    for campo, valor in (
        ("aliado_id", aliado.id),
        ("etapa_actual_id", 999999999),
        ("estado", EstadoConvenio.VIGENTE.value),
    ):
        respuesta = client.post(
            "/api/convenios",
            json={**_payload_convenio(solicitud.id), campo: valor},
        )
        assert respuesta.status_code == 422


def test_hu06_ca04_rechaza_estado_y_creado_por_del_cliente(
    client, crear_usuario, entrar_como, crear_solicitud
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(gestor)
    datos = {**_payload_convenio(solicitud.id), "creado_por_id": 999}
    assert client.post("/api/convenios", json=datos).status_code == 422


def test_hu06_ca05_solicitud_unica(client, crear_usuario, entrar_como, crear_solicitud) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(gestor)
    assert client.post("/api/convenios", json=_payload_convenio(solicitud.id)).status_code == 201
    assert client.post("/api/convenios", json=_payload_convenio(solicitud.id)).status_code == 409


def test_hu06_patch_parcial_y_campos_inmutables(
    client, crear_usuario, entrar_como, crear_solicitud
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(gestor)
    creado = client.post("/api/convenios", json=_payload_convenio(solicitud.id)).json()
    respuesta = client.patch(f"/api/convenios/{creado['id']}", json={"objeto": "Objeto actualizado"})
    assert respuesta.status_code == 200 and respuesta.json()["objeto"] == "Objeto actualizado"
    for campo, valor in [
        ("estado", "VIGENTE"),
        ("solicitud_id", 1),
        ("aliado_id", 1),
        ("etapa_actual_id", 1),
        ("creado_por_id", 1),
        ("id", 1),
        ("creado_en", "2026-01-01"),
    ]:
        assert client.patch(f"/api/convenios/{creado['id']}", json={campo: valor}).status_code == 422


@pytest.mark.parametrize(
    ("rol", "lectura", "escritura"),
    [
        (CodigoRol.REVISOR_ORI, 200, 403),
        (CodigoRol.GESTOR_ORI, 200, 201),
        (CodigoRol.SOLICITANTE_INTERNO, 403, 403),
        (CodigoRol.SOLICITANTE_EXTERNO, 403, 403),
    ],
)
def test_hu06_ca08_permisos_por_rol(
    rol, lectura, escritura, db, client, crear_usuario, entrar_como, crear_solicitud
) -> None:
    autor = crear_usuario(CodigoRol.GESTOR_ORI)
    existente = _crear_convenio(db, crear_solicitud(autor), autor)
    actor = _autenticar(client, crear_usuario, entrar_como, rol)
    assert client.get(f"/api/convenios/{existente.id}").status_code == lectura
    solicitud = crear_solicitud(actor)
    assert client.post("/api/convenios", json=_payload_convenio(solicitud.id)).status_code == escritura
    assert client.patch(f"/api/convenios/{existente.id}", json={"objeto": "Cambio"}).status_code == (200 if rol == CodigoRol.GESTOR_ORI else 403)


def test_hu06_rutas_sin_sesion_responden_401(client) -> None:
    client.cookies.clear()
    assert client.post("/api/convenios", json=_payload_convenio(1)).status_code == 401
    assert client.get("/api/convenios/1").status_code == 401
    assert client.patch("/api/convenios/1", json={"objeto": "X"}).status_code == 401
