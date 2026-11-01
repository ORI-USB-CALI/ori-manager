"""HT-14 BE02. Reglas de formato integradas en crear, actualizar y radicar."""

from io import BytesIO

import pytest
from sqlalchemy import select, text

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.validaciones import calcular_digito_verificacion_nit
from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio, EstadoSolicitud, TipoIdentificacion
from backend.models.pais import Pais
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.schemas.aliado import AliadoLeer
from backend.schemas.convenio import AliadoResumen, SolicitudAntecedenteLeer
from backend.services.aliados import resolver_aliado_para_convenio
from backend.services.contenido_convenio import expandir_plantilla
from backend.services.pdf_convenio import ServicioPdfConvenio
from backend.services.renovaciones import CAMPOS_SOLICITUD_RENOVACION

URL = "/api/solicitudes"


@pytest.fixture
def externo(crear_usuario, entrar_como, db):
    usuario = crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)
    usuario.documento_identidad = "1.144.123.456"
    usuario.entidad_externa = "Empresa solicitante"
    db.commit()
    entrar_como(usuario)
    return usuario


@pytest.fixture
def colombia(db):
    return db.scalar(select(Pais).where(Pais.codigo_iso == "CO"))


@pytest.fixture
def tipo_convenio(db):
    return db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))


@pytest.fixture
def payload(colombia, tipo_convenio):
    return {
        "solicitante_tipo_documento": "CEDULA_CIUDADANIA",
        "nombre_aliado_propuesto": "Entidad contraparte",
        "tipo_identificacion_aliado_propuesto": "NIT",
        "identificacion_aliado_propuesto": "900.123.456",
        "digito_verificacion_aliado_propuesto": "8",
        "tipo_aliado_propuesto": "UNIVERSIDAD",
        "correo_aliado_propuesto": "contacto@contraparte.com",
        "pais_aliado_propuesto_id": colombia.id,
        "ciudad_aliado_propuesto": "  Santiago   de Cali ",
        "telefono_aliado_propuesto": "602 555 0101",
        "direccion_aliado_propuesto": "Avenida 1 # 2-3",
        "contacto_contraparte_nombre": "Contacto contraparte",
        "contacto_contraparte_cargo": "Directora",
        "contacto_contraparte_telefono": "300 123 4567",
        "contacto_contraparte_correo": "persona@example.com",
        "tipo_convenio_id": tipo_convenio.id,
        "justificacion": "Justificación suficiente",
        "objeto": "Objeto del convenio",
        "actividades_por_parte": "Actividades definidas",
        "metas_esperadas": "Metas medibles",
        "implicacion_financiera": "Sin erogación inicial",
        "vigencia_estimada": "24 meses",
        "requisitos_renovacion": "Acuerdo escrito",
        "supervisor_usb_nombre": "Supervisora USB",
        "supervisor_usb_cargo": "Directora",
        "supervisor_usb_telefono": "6025550202",
        "supervisor_usb_correo": "supervisor.usb@example.com",
        "supervisor_contraparte_nombre": "Supervisor contraparte",
        "supervisor_contraparte_cargo": "Coordinador",
        "supervisor_contraparte_telefono": "+34 912 345 678",
        "supervisor_contraparte_correo": "supervisor.contraparte@example.com",
    }


def _crear(client, datos):
    respuesta = client.post(URL, json=datos)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _subir_representacion(client, solicitud_id):
    respuesta = client.post(
        f"{URL}/{solicitud_id}/documentos",
        data={"tipo_documento": "OTRO_DOCUMENTO_REPRESENTACION"},
        files={"archivo": ("rep.pdf", BytesIO(b"%PDF-1.4 soporte"), "application/pdf")},
    )
    assert respuesta.status_code == 201, respuesta.text


def _errores(respuesta):
    assert respuesta.status_code == 422, respuesta.text
    return respuesta.json()["detail"]["errors"]


# --- Crear y actualizar borradores (CA-05, CA-06) -----------------------------


def test_crear_guarda_los_valores_en_forma_canonica(client, externo, payload, colombia):
    cuerpo = _crear(client, payload)

    assert cuerpo["identificacion_aliado_propuesto"] == "900123456"
    assert cuerpo["digito_verificacion_aliado_propuesto"] == "8"
    assert cuerpo["identificacion_aliado_propuesto_completa"] == "900123456-8"
    assert cuerpo["solicitante_documento"] == "1144123456"
    assert cuerpo["solicitante_documento_completo"] == "1144123456"
    assert cuerpo["telefono_aliado_propuesto"] == "+576025550101"
    assert cuerpo["contacto_contraparte_telefono"] == "+573001234567"
    assert cuerpo["supervisor_contraparte_telefono"] == "+34912345678"
    assert cuerpo["ciudad_aliado_propuesto"] == "Santiago de Cali"
    assert cuerpo["pais_aliado_propuesto_id"] == colombia.id
    assert cuerpo["pais_aliado_propuesto"] == "Colombia"


def test_borrador_incompleto_se_guarda_si_lo_diligenciado_es_valido(client, externo):
    cuerpo = _crear(client, {"telefono_aliado_propuesto": "3001234567"})
    assert cuerpo["estado"] == EstadoSolicitud.BORRADOR.value
    assert cuerpo["telefono_aliado_propuesto"] == "+573001234567"


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"telefono_aliado_propuesto": "abc3001234567"}, "telefono_aliado_propuesto"),
        ({"supervisor_usb_telefono": "12345"}, "supervisor_usb_telefono"),
        ({"contacto_contraparte_telefono": "5551234"}, "contacto_contraparte_telefono"),
        ({"supervisor_contraparte_telefono": "+999 1"}, "supervisor_contraparte_telefono"),
        ({"ciudad_aliado_propuesto": "Cali 123"}, "ciudad_aliado_propuesto"),
        ({"direccion_aliado_propuesto": "12345 # 67"}, "direccion_aliado_propuesto"),
        ({"identificacion_aliado_propuesto": "900123456-8"}, "identificacion_aliado_propuesto"),
        ({"digito_verificacion_aliado_propuesto": "5"}, "digito_verificacion_aliado_propuesto"),
        (
            {"tipo_identificacion_aliado_propuesto": "PASAPORTE"},
            "digito_verificacion_aliado_propuesto",
        ),
        ({"pais_aliado_propuesto_id": 999999}, "pais_aliado_propuesto_id"),
        ({"solicitante_documento": "ABC"}, "solicitante_documento"),
    ],
)
def test_crear_rechaza_formatos_invalidos_por_campo(
    client, db, externo, payload, cambios, campo
):
    antes = db.scalar(text("SELECT count(*) FROM solicitud_convenio"))

    errores = _errores(client.post(URL, json={**payload, **cambios}))

    assert campo in errores
    assert db.scalar(text("SELECT count(*) FROM solicitud_convenio")) == antes


def test_el_pais_ya_no_se_recibe_como_texto(client, externo):
    respuesta = client.post(URL, json={"pais_aliado_propuesto": "Colombia"})
    assert respuesta.status_code == 422


def test_actualizar_valida_con_el_tipo_ya_guardado(client, externo, payload):
    solicitud = _crear(client, payload)

    errores = _errores(
        client.patch(
            f"{URL}/{solicitud['id']}", json={"identificacion_aliado_propuesto": "ABC"}
        )
    )

    assert "identificacion_aliado_propuesto" in errores


def test_actualizar_solo_el_tipo_revalida_la_identificacion_guardada(
    client, externo, payload
):
    solicitud = _crear(
        client,
        {
            **payload,
            "tipo_identificacion_aliado_propuesto": "CEDULA_EXTRANJERIA",
            "identificacion_aliado_propuesto": "E123456",
            "digito_verificacion_aliado_propuesto": None,
        },
    )

    errores = _errores(
        client.patch(
            f"{URL}/{solicitud['id']}",
            json={"tipo_identificacion_aliado_propuesto": "CEDULA_CIUDADANIA"},
        )
    )

    assert "identificacion_aliado_propuesto" in errores


def test_al_dejar_de_ser_nit_se_borra_el_digito_de_verificacion(client, externo, payload):
    solicitud = _crear(client, payload)

    respuesta = client.patch(
        f"{URL}/{solicitud['id']}",
        json={"tipo_identificacion_aliado_propuesto": "CEDULA_CIUDADANIA"},
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["identificacion_aliado_propuesto"] == "900123456"
    assert cuerpo["digito_verificacion_aliado_propuesto"] is None
    assert cuerpo["identificacion_aliado_propuesto_completa"] == "900123456"


def test_actualizar_con_error_no_modifica_la_solicitud(client, externo, payload):
    solicitud = _crear(client, payload)

    _errores(
        client.patch(
            f"{URL}/{solicitud['id']}",
            json={"ciudad_aliado_propuesto": "Bogotá", "telefono_aliado_propuesto": "123"},
        )
    )

    actual = client.get(f"{URL}/{solicitud['id']}").json()
    assert actual["ciudad_aliado_propuesto"] == "Santiago de Cali"
    assert actual["telefono_aliado_propuesto"] == "+576025550101"


# --- Radicación (CA-05, CA-06, RN-09, RN-10) ----------------------------------


def test_radica_una_solicitud_valida(client, externo, payload):
    solicitud = _crear(client, payload)
    _subir_representacion(client, solicitud["id"])

    respuesta = client.post(f"{URL}/{solicitud['id']}/radicar")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == EstadoSolicitud.RADICADA.value


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"digito_verificacion_aliado_propuesto": None}, "digito_verificacion_aliado_propuesto"),
        ({"pais_aliado_propuesto_id": None}, "pais_aliado_propuesto_id"),
        ({"solicitante_tipo_documento": None}, "solicitante_tipo_documento"),
    ],
)
def test_radicacion_exige_los_nuevos_campos(client, externo, payload, cambios, campo):
    solicitud = _crear(client, {**payload, **cambios})
    _subir_representacion(client, solicitud["id"])

    errores = _errores(client.post(f"{URL}/{solicitud['id']}/radicar"))

    assert campo in errores
    assert client.get(f"{URL}/{solicitud['id']}").json()["estado"] == "BORRADOR"


def test_radicacion_exige_dv_cuando_el_solicitante_usa_nit(client, externo, payload):
    solicitud = _crear(
        client,
        {
            **payload,
            "solicitante_tipo_documento": "NIT",
            "solicitante_documento": "800197268",
        },
    )
    _subir_representacion(client, solicitud["id"])

    errores = _errores(client.post(f"{URL}/{solicitud['id']}/radicar"))

    assert "solicitante_digito_verificacion" in errores


def test_radicacion_revalida_valores_historicos_sin_cambiar_estado(
    client, db, externo, payload
):
    solicitud = _crear(client, payload)
    _subir_representacion(client, solicitud["id"])
    # Dato guardado antes de HT-14, sin pasar por las reglas actuales.
    db.execute(
        text("UPDATE solicitud_convenio SET telefono_aliado_propuesto = '123' WHERE id = :id"),
        {"id": solicitud["id"]},
    )
    db.commit()

    errores = _errores(client.post(f"{URL}/{solicitud['id']}/radicar"))

    assert "telefono_aliado_propuesto" in errores
    assert db.get(SolicitudConvenio, solicitud["id"]).estado == "BORRADOR"


# --- Catálogo de países ------------------------------------------------------


def test_paises_requiere_autenticacion(client):
    assert client.get("/api/paises").status_code == 401


@pytest.mark.parametrize("rol", list(CodigoRol))
def test_cualquier_usuario_autenticado_consulta_los_paises(
    client, crear_usuario, entrar_como, colombia, rol
):
    entrar_como(crear_usuario(rol))

    respuesta = client.get("/api/paises")

    assert respuesta.status_code == 200
    paises = respuesta.json()
    assert len(paises) >= 240
    assert {"id": colombia.id, "codigo_iso": "CO", "nombre": "Colombia"} in paises


def test_catalogos_de_solicitud_ya_no_incluyen_paises(client, externo):
    assert "paises" not in client.get(f"{URL}/catalogos").json()


# --- Aliado y renovación ------------------------------------------------------


def test_al_formalizar_el_aliado_copia_dv_y_pais(db, crear_usuario, colombia):
    usuario = crear_usuario()
    solicitud = SolicitudConvenio(
        consecutivo="SOL-HT14-ALIADO",
        tipo_solicitante="INTERNO",
        solicitante_id=usuario.id,
        estado=EstadoSolicitud.APROBADA.value,
        nombre_aliado_propuesto="Universidad aliada",
        tipo_identificacion_aliado_propuesto=TipoIdentificacion.NIT.value,
        identificacion_aliado_propuesto="800197268",
        digito_verificacion_aliado_propuesto="4",
        tipo_aliado_propuesto="UNIVERSIDAD",
        pais_aliado_propuesto_id=colombia.id,
        pais_aliado_propuesto="Colombia",
    )
    db.add(solicitud)
    db.flush()
    convenio = Convenio(
        solicitud_id=solicitud.id,
        estado=EstadoConvenio.VIGENTE.value,
        objeto="Cooperación",
        alcance="INSTITUCIONAL",
        creado_por_id=usuario.id,
    )
    db.add(convenio)
    db.flush()

    aliado = resolver_aliado_para_convenio(db, convenio)

    assert aliado.identificacion == "800197268"
    assert aliado.digito_verificacion == "4"
    assert aliado.pais_id == colombia.id


def test_un_aliado_existente_se_reconoce_por_la_base(db, crear_usuario, colombia):
    existente = Aliado(
        nombre="Universidad aliada",
        tipo="UNIVERSIDAD",
        tipo_identificacion="NIT",
        identificacion="800197268",
        digito_verificacion="4",
        activo=True,
    )
    db.add(existente)
    usuario = crear_usuario()
    solicitud = SolicitudConvenio(
        consecutivo="SOL-HT14-REUSO",
        tipo_solicitante="INTERNO",
        solicitante_id=usuario.id,
        estado=EstadoSolicitud.APROBADA.value,
        nombre_aliado_propuesto="Universidad aliada (nuevo correo)",
        tipo_identificacion_aliado_propuesto="NIT",
        identificacion_aliado_propuesto="800197268",
        digito_verificacion_aliado_propuesto="4",
        tipo_aliado_propuesto="UNIVERSIDAD",
    )
    db.add(solicitud)
    db.flush()
    convenio = Convenio(
        solicitud_id=solicitud.id,
        estado=EstadoConvenio.VIGENTE.value,
        objeto="Cooperación",
        alcance="INSTITUCIONAL",
        creado_por_id=usuario.id,
    )
    db.add(convenio)
    db.flush()

    assert resolver_aliado_para_convenio(db, convenio).id == existente.id


def test_la_renovacion_copia_los_campos_nuevos():
    for campo in (
        "solicitante_tipo_documento",
        "solicitante_digito_verificacion",
        "digito_verificacion_aliado_propuesto",
        "pais_aliado_propuesto_id",
    ):
        assert campo in CAMPOS_SOLICITUD_RENOVACION


# --- Presentación del NIT con su DV ------------------------------------------


def test_contenido_del_convenio_muestra_el_nit_con_dv():
    solicitud = SolicitudConvenio(
        consecutivo="SOL-1",
        nombre_aliado_propuesto="Entidad",
        tipo_identificacion_aliado_propuesto="NIT",
        identificacion_aliado_propuesto="900123456",
        digito_verificacion_aliado_propuesto="8",
    )
    plantilla = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "{{ solicitud.contraparte }}"}],
            }
        ],
    }

    resultado = expandir_plantilla(plantilla, solicitud, None)

    assert "900123456-8" in resultado["content"][0]["content"][0]["text"]


def test_pdf_muestra_el_nit_del_aliado_con_dv(db, convenio_exportable):
    aliado = convenio_exportable.aliado
    aliado.digito_verificacion = str(calcular_digito_verificacion_nit(aliado.identificacion))
    db.commit()

    dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio_exportable.id, db)

    assert dto.aliado_identificacion == f"{aliado.identificacion}-{aliado.digito_verificacion}"


def test_respuestas_del_aliado_incluyen_la_identificacion_completa(db):
    aliado = Aliado(
        nombre="Entidad",
        tipo="UNIVERSIDAD",
        tipo_identificacion="NIT",
        identificacion="800197268",
        digito_verificacion="4",
        activo=True,
    )
    db.add(aliado)
    db.flush()
    db.refresh(aliado)

    assert AliadoResumen.model_validate(aliado).identificacion_completa == "800197268-4"
    leido = AliadoLeer.model_validate(aliado)
    assert leido.digito_verificacion == "4"
    assert leido.identificacion_completa == "800197268-4"


def test_antecedente_del_convenio_incluye_la_identificacion_completa():
    solicitud = SolicitudConvenio(
        id=1,
        consecutivo="SOL-1",
        tipo_solicitante="EXTERNO",
        estado="APROBADA",
        tipo_identificacion_aliado_propuesto="NIT",
        identificacion_aliado_propuesto="900123456",
        digito_verificacion_aliado_propuesto="8",
    )

    leida = SolicitudAntecedenteLeer.model_validate(solicitud)

    assert leida.identificacion_aliado_propuesto_completa == "900123456-8"
