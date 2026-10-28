"""HT-14 BE03. Pruebas parametrizadas de las reglas de formato.

Complementa la matriz de ``test_ht14_validaciones.py`` con los valores límite
de cada regla y la integración de ``test_ht14_integracion_solicitud.py`` con
llamadas directas a la API por campo, radicación sin efectos parciales,
corrección de solicitudes devueltas y ambos tipos de solicitante.
"""

from io import BytesIO

import pytest
from sqlalchemy import func, select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.validaciones import (
    normalizar_ciudad,
    normalizar_direccion,
    normalizar_identificacion,
    normalizar_telefono,
)
from backend.models.auditoria import Auditoria
from backend.models.enums import EstadoSolicitud, TipoIdentificacion
from backend.models.notificacion import Notificacion
from backend.models.pais import Pais
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.solicitud_version import SolicitudVersion
from backend.models.tipo_convenio import TipoConvenio

URL = "/api/solicitudes"

NIT = TipoIdentificacion.NIT
CC = TipoIdentificacion.CEDULA_CIUDADANIA
CE = TipoIdentificacion.CEDULA_EXTRANJERIA
PASAPORTE = TipoIdentificacion.PASAPORTE
FISCAL = TipoIdentificacion.IDENTIFICACION_FISCAL_EXTRANJERA
OTRO = TipoIdentificacion.OTRO


# --- Valores límite de la matriz (BE01) ---------------------------------------


@pytest.mark.parametrize(
    ("tipo", "minimo", "maximo"),
    [
        (NIT, "1" * 5, "1" * 10),
        (CC, "1" * 5, "1" * 10),
        (CE, "A" * 3, "A" * 15),
        (PASAPORTE, "A" * 5, "A" * 20),
        (FISCAL, "A" * 3, "A" * 40),
        (OTRO, "A" * 3, "A" * 40),
    ],
)
def test_identificacion_acepta_las_longitudes_limite_y_rechaza_las_vecinas(
    tipo, minimo, maximo
):
    assert normalizar_identificacion(tipo, minimo) == minimo
    assert normalizar_identificacion(tipo, maximo) == maximo
    with pytest.raises(ValueError):
        normalizar_identificacion(tipo, minimo[:-1])
    with pytest.raises(ValueError):
        normalizar_identificacion(tipo, maximo + maximo[-1])


@pytest.mark.parametrize("tipo", [NIT, CC])
def test_los_separadores_no_cuentan_en_la_longitud(tipo):
    # 10 dígitos con puntos y espacios siguen siendo una base válida.
    assert normalizar_identificacion(tipo, "1.144 123.456") == "1144123456"


@pytest.mark.parametrize(
    ("valor", "canonico"),
    [
        ("6025551234 ext 1", "+576025551234;ext=1"),
        ("6025551234 ext 123456", "+576025551234;ext=123456"),
        ("6025551234 extensión 12", "+576025551234;ext=12"),
        ("6025551234 x 12", "+576025551234;ext=12"),
    ],
)
def test_telefono_acepta_extensiones_de_1_a_6_digitos(valor, canonico):
    assert normalizar_telefono(valor) == canonico


@pytest.mark.parametrize(
    "valor",
    [
        "6025551234 ext 1234567",  # extensión de 7 dígitos
        "+57",  # solo el indicativo
        "+",
        "   ",
        "3001234567#",
    ],
)
def test_telefono_rechaza_los_casos_limite(valor):
    with pytest.raises(ValueError):
        normalizar_telefono(valor)


@pytest.mark.parametrize(
    ("valor", "canonico"),
    [
        ("Ub", "Ub"),
        ("A" * 120, "A" * 120),
        # Los espacios repetidos no cuentan en la longitud.
        (" A " + " " * 10 + "B ", "A B"),
        ("Cali.", "Cali."),  # el punto final es válido (abreviaturas como "D.C.")
    ],
)
def test_ciudad_acepta_las_longitudes_limite(valor, canonico):
    assert normalizar_ciudad(valor) == canonico


@pytest.mark.parametrize("valor", ["U", "A" * 121, "'Cali", "Cali_Valle"])
def test_ciudad_rechaza_los_casos_limite(valor):
    with pytest.raises(ValueError):
        normalizar_ciudad(valor)


@pytest.mark.parametrize(
    ("valor", "canonico"),
    [
        ("Cl 51", "Cl 51"),  # 5 caracteres
        ("A" * 200, "A" * 200),
        ("Casa  12 ", "Casa 12"),
        ("Calle 5\t# 38", "Calle 5 # 38"),  # el tabulador se normaliza
    ],
)
def test_direccion_acepta_las_longitudes_limite(valor, canonico):
    assert normalizar_direccion(valor) == canonico


@pytest.mark.parametrize(
    "valor",
    [
        "Cl 5",  # 4 caracteres
        "A" * 201,
        "     ",
        "#-.,/",  # solo signos
    ],
)
def test_direccion_rechaza_los_casos_limite(valor):
    with pytest.raises(ValueError):
        normalizar_direccion(valor)


# --- Datos de prueba de la API -------------------------------------------------


@pytest.fixture
def colombia(db):
    return db.scalar(select(Pais).where(Pais.codigo_iso == "CO"))


@pytest.fixture
def payload(db, colombia):
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    return {
        "solicitante_tipo_documento": "CEDULA_CIUDADANIA",
        "solicitante_documento": "1144123456",
        "nombre_aliado_propuesto": "Entidad contraparte",
        "tipo_identificacion_aliado_propuesto": "NIT",
        "identificacion_aliado_propuesto": "900123456",
        "digito_verificacion_aliado_propuesto": "8",
        "tipo_aliado_propuesto": "UNIVERSIDAD",
        "correo_aliado_propuesto": "contacto@contraparte.com",
        "pais_aliado_propuesto_id": colombia.id,
        "ciudad_aliado_propuesto": "Cali",
        "telefono_aliado_propuesto": "6025550101",
        "direccion_aliado_propuesto": "Avenida 1 # 2-3",
        "contacto_contraparte_nombre": "Contacto contraparte",
        "contacto_contraparte_cargo": "Directora",
        "contacto_contraparte_telefono": "3001234567",
        "contacto_contraparte_correo": "persona@example.com",
        "tipo_convenio_id": tipo.id,
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


@pytest.fixture
def externo(crear_usuario, entrar_como, db):
    usuario = crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)
    usuario.entidad_externa = "Empresa solicitante"
    db.commit()
    entrar_como(usuario)
    return usuario


@pytest.fixture
def interno(crear_usuario, entrar_como, db):
    usuario = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)
    usuario.cargo = "Docente"
    db.commit()
    entrar_como(usuario)
    return usuario


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
    """CA-06: 422 con ``detail.errors[campo]`` y un mensaje legible por campo."""
    assert respuesta.status_code == 422, respuesta.text
    detalle = respuesta.json()["detail"]
    assert isinstance(detalle["message"], str)
    errores = detalle["errors"]
    for mensaje in errores.values():
        assert isinstance(mensaje, str) and mensaje
        # El frontend muestra el mensaje tal cual; no lleva el prefijo de Pydantic.
        assert not mensaje.startswith("Value error")
    return errores


def _conteos(db, solicitud_id=None):
    filtro_version = (
        [SolicitudVersion.solicitud_id == solicitud_id] if solicitud_id else []
    )
    return (
        db.scalar(select(func.count()).select_from(SolicitudConvenio)),
        db.scalar(
            select(func.count()).select_from(SolicitudVersion).where(*filtro_version)
        ),
        db.scalar(select(func.count()).select_from(Auditoria)),
        db.scalar(select(func.count()).select_from(Notificacion)),
    )


# Un valor inválido y uno válido (con su forma canónica) por cada campo con formato.
CASOS_POR_CAMPO = [
    ("telefono_aliado_propuesto", "300-ABC-4567", "602 555 0303", "+576025550303"),
    ("contacto_contraparte_telefono", "5551234", "+44 20 7946 0958", "+442079460958"),
    ("supervisor_usb_telefono", "300123456", "(602) 555-1234", "+576025551234"),
    (
        "supervisor_contraparte_telefono",
        "+999 1234567",
        "+1 650 253 0000",
        "+16502530000",
    ),
    ("ciudad_aliado_propuesto", "Cali 123", "  São   Paulo ", "São Paulo"),
    (
        "direccion_aliado_propuesto",
        "Calle 5 <script>",
        "Vereda El Roble, Finca 3",
        "Vereda El Roble, Finca 3",
    ),
    ("identificacion_aliado_propuesto", "900123456-8", "900.123.456", "900123456"),
    ("solicitante_documento", "1144-123456", "1.144.123.456", "1144123456"),
]


# --- Crear y PATCH por API directa (CA-06) --------------------------------------


@pytest.mark.parametrize(("campo", "invalido", "valido", "canonico"), CASOS_POR_CAMPO)
def test_crear_por_api_valida_cada_campo(
    client, db, externo, payload, campo, invalido, valido, canonico
):
    antes = _conteos(db)

    errores = _errores(client.post(URL, json={**payload, campo: invalido}))

    assert set(errores) == {campo}
    assert _conteos(db) == antes
    assert _crear(client, {**payload, campo: valido})[campo] == canonico


@pytest.mark.parametrize(("campo", "invalido", "valido", "canonico"), CASOS_POR_CAMPO)
def test_patch_por_api_valida_cada_campo_sin_modificar_la_solicitud(
    client, externo, payload, campo, invalido, valido, canonico
):
    solicitud = _crear(client, payload)
    url = f"{URL}/{solicitud['id']}"

    errores = _errores(client.patch(url, json={campo: invalido}))

    assert set(errores) == {campo}
    assert client.get(url).json()[campo] == solicitud[campo]
    actualizada = client.patch(url, json={campo: valido})
    assert actualizada.status_code == 200, actualizada.text
    assert actualizada.json()[campo] == canonico


def test_crear_reporta_todos_los_campos_invalidos_a_la_vez(client, externo, payload):
    errores = _errores(
        client.post(
            URL,
            json={campo: invalido for campo, invalido, _, _ in CASOS_POR_CAMPO}
            | {
                "tipo_identificacion_aliado_propuesto": "NIT",
                "solicitante_tipo_documento": "CEDULA_CIUDADANIA",
            },
        )
    )

    assert set(errores) == {campo for campo, *_ in CASOS_POR_CAMPO}


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [
        (
            {"digito_verificacion_aliado_propuesto": "12"},
            "digito_verificacion_aliado_propuesto",
        ),
        ({"pais_aliado_propuesto_id": "Colombia"}, "pais_aliado_propuesto_id"),
        (
            {"tipo_identificacion_aliado_propuesto": "RUT"},
            "tipo_identificacion_aliado_propuesto",
        ),
        ({"telefono_aliado_propuesto": "1" * 41}, "telefono_aliado_propuesto"),
        ({"campo_inexistente": "x"}, "campo_inexistente"),
    ],
)
def test_tipos_y_campos_ajenos_al_contrato_se_rechazan_antes_del_servicio(
    client, db, externo, cuerpo, campo
):
    antes = _conteos(db)

    respuesta = client.post(URL, json=cuerpo)

    # Error estándar de FastAPI: lista de errores con la ubicación del campo.
    assert respuesta.status_code == 422
    assert any(error["loc"][-1] == campo for error in respuesta.json()["detail"])
    assert _conteos(db) == antes


def test_campos_vacios_del_borrador_no_se_validan(client, externo):
    cuerpo = _crear(
        client,
        {
            "telefono_aliado_propuesto": "   ",
            "ciudad_aliado_propuesto": "",
            "direccion_aliado_propuesto": None,
            "tipo_identificacion_aliado_propuesto": "NIT",
        },
    )

    assert cuerpo["estado"] == EstadoSolicitud.BORRADOR.value
    assert cuerpo["telefono_aliado_propuesto"] is None
    assert cuerpo["ciudad_aliado_propuesto"] is None


def test_patch_puede_vaciar_un_campo_con_formato(client, externo, payload):
    solicitud = _crear(client, payload)

    respuesta = client.patch(
        f"{URL}/{solicitud['id']}", json={"telefono_aliado_propuesto": ""}
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["telefono_aliado_propuesto"] is None


@pytest.mark.parametrize(
    ("tipo", "identificacion", "dv", "completa"),
    [
        ("NIT", "800.197.268", "4", "800197268-4"),
        ("CEDULA_CIUDADANIA", "1.144.123.456", None, "1144123456"),
        ("CEDULA_EXTRANJERIA", "e 123456", None, "E123456"),
        ("PASAPORTE", "ab123456", None, "AB123456"),
        ("IDENTIFICACION_FISCAL_EXTRANJERA", "B-12345678", None, "B-12345678"),
    ],
)
def test_crear_normaliza_la_identificacion_segun_el_tipo(
    client, externo, payload, tipo, identificacion, dv, completa
):
    cuerpo = _crear(
        client,
        {
            **payload,
            "tipo_identificacion_aliado_propuesto": tipo,
            "identificacion_aliado_propuesto": identificacion,
            "digito_verificacion_aliado_propuesto": dv,
        },
    )

    assert cuerpo["identificacion_aliado_propuesto_completa"] == completa


def test_el_dv_solo_se_acepta_para_nit(client, externo, payload):
    errores = _errores(
        client.post(
            URL,
            json={
                **payload,
                "tipo_identificacion_aliado_propuesto": "PASAPORTE",
                "identificacion_aliado_propuesto": "AB123456",
                "digito_verificacion_aliado_propuesto": "4",
            },
        )
    )

    assert set(errores) == {"digito_verificacion_aliado_propuesto"}


def test_patch_del_dv_se_valida_contra_la_base_guardada(client, externo, payload):
    solicitud = _crear(client, payload)
    url = f"{URL}/{solicitud['id']}"

    errores = _errores(
        client.patch(url, json={"digito_verificacion_aliado_propuesto": "9"})
    )

    assert set(errores) == {"digito_verificacion_aliado_propuesto"}
    # Cambiar la base sin actualizar el DV también se detecta.
    errores = _errores(
        client.patch(url, json={"identificacion_aliado_propuesto": "800197268"})
    )
    assert set(errores) == {"digito_verificacion_aliado_propuesto"}


def test_el_pais_se_guarda_con_el_nombre_oficial_del_catalogo(
    client, db, externo, payload
):
    espana = db.scalar(select(Pais).where(Pais.codigo_iso == "ES"))
    solicitud = _crear(client, payload)

    respuesta = client.patch(
        f"{URL}/{solicitud['id']}", json={"pais_aliado_propuesto_id": espana.id}
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["pais_aliado_propuesto"] == espana.nombre
    # Quitar el país también quita el nombre.
    vacio = client.patch(
        f"{URL}/{solicitud['id']}", json={"pais_aliado_propuesto_id": None}
    )
    assert vacio.json()["pais_aliado_propuesto"] is None


# --- Radicación sin efectos parciales (CA-05, CA-06) -----------------------------


@pytest.mark.parametrize(("campo", "invalido", "_valido", "_canonico"), CASOS_POR_CAMPO)
def test_radicacion_con_un_valor_historico_invalido_no_produce_efectos(
    client, db, externo, payload, campo, invalido, _valido, _canonico
):
    solicitud = _crear(client, payload)
    _subir_representacion(client, solicitud["id"])
    # RN-10: dato guardado antes de HT-14, sin pasar por las reglas actuales.
    db.execute(
        SolicitudConvenio.__table__.update()
        .where(SolicitudConvenio.id == solicitud["id"])
        .values({campo: invalido})
    )
    db.commit()
    antes = _conteos(db, solicitud["id"])

    errores = _errores(client.post(f"{URL}/{solicitud['id']}/radicar"))

    assert campo in errores
    db.expire_all()
    guardada = db.get(SolicitudConvenio, solicitud["id"])
    assert guardada.estado == EstadoSolicitud.BORRADOR.value
    assert guardada.fecha_radicacion is None
    # RN-10: el valor histórico no se corrige automáticamente.
    assert getattr(guardada, campo) == invalido
    assert _conteos(db, solicitud["id"]) == antes


def test_radicacion_reporta_obligatorios_y_formatos_juntos(
    client, db, externo, payload
):
    solicitud = _crear(client, {**payload, "objeto": None})
    _subir_representacion(client, solicitud["id"])
    db.execute(
        SolicitudConvenio.__table__.update()
        .where(SolicitudConvenio.id == solicitud["id"])
        .values(telefono_aliado_propuesto="123")
    )
    db.commit()

    errores = _errores(client.post(f"{URL}/{solicitud['id']}/radicar"))

    assert errores["objeto"] == "Este campo es obligatorio"
    assert "telefono_aliado_propuesto" in errores


# --- Solicitudes devueltas (RN-09) -------------------------------------------------


@pytest.fixture
def devuelta(client, crear_usuario, entrar_como, externo, payload):
    solicitud = _crear(client, payload)
    _subir_representacion(client, solicitud["id"])
    assert client.post(f"{URL}/{solicitud['id']}/radicar").status_code == 200
    entrar_como(crear_usuario(CodigoRol.GESTOR_ORI))
    respuesta = client.post(
        f"{URL}/recibidas/{solicitud['id']}/devolver",
        json={"observaciones": "Corregir el teléfono de la contraparte"},
    )
    assert respuesta.status_code == 200, respuesta.text
    entrar_como(externo)
    return solicitud["id"]


@pytest.mark.parametrize(("campo", "invalido", "valido", "canonico"), CASOS_POR_CAMPO)
def test_corregir_una_devuelta_aplica_las_mismas_reglas(
    client, devuelta, campo, invalido, valido, canonico
):
    url = f"{URL}/{devuelta}"

    errores = _errores(client.patch(url, json={campo: invalido}))

    assert set(errores) == {campo}
    assert client.get(url).json()["estado"] == EstadoSolicitud.DEVUELTA.value
    corregida = client.patch(url, json={campo: valido})
    assert corregida.status_code == 200, corregida.text
    assert corregida.json()[campo] == canonico
    assert corregida.json()["estado"] == EstadoSolicitud.DEVUELTA.value


def test_volver_a_radicar_una_devuelta_invalida_conserva_el_estado_y_las_versiones(
    client, db, devuelta
):
    db.execute(
        SolicitudConvenio.__table__.update()
        .where(SolicitudConvenio.id == devuelta)
        .values(telefono_aliado_propuesto="5551234")
    )
    db.commit()
    antes = _conteos(db, devuelta)

    errores = _errores(client.post(f"{URL}/{devuelta}/radicar"))

    assert "telefono_aliado_propuesto" in errores
    db.expire_all()
    assert db.get(SolicitudConvenio, devuelta).estado == EstadoSolicitud.DEVUELTA.value
    assert _conteos(db, devuelta) == antes
    # La devolución sigue pendiente para el solicitante.
    assert client.get(f"{URL}/{devuelta}").json()["observaciones_devolucion"]

    corregida = client.patch(
        f"{URL}/{devuelta}", json={"telefono_aliado_propuesto": "602 555 0101"}
    )
    assert corregida.status_code == 200, corregida.text
    radicada = client.post(f"{URL}/{devuelta}/radicar")
    assert radicada.status_code == 200, radicada.text
    assert radicada.json()["estado"] == EstadoSolicitud.RADICADA.value
    assert radicada.json()["telefono_aliado_propuesto"] == "+576025550101"


# --- Ambos tipos de solicitante -------------------------------------------------------


@pytest.mark.parametrize(("campo", "invalido", "_valido", "_canonico"), CASOS_POR_CAMPO)
def test_el_solicitante_interno_recibe_las_mismas_reglas(
    client, interno, payload, campo, invalido, _valido, _canonico
):
    errores = _errores(client.post(URL, json={**payload, campo: invalido}))

    assert set(errores) == {campo}


def test_el_solicitante_interno_radica_sin_tipo_de_documento(client, interno, payload):
    solicitud = _crear(
        client,
        {
            **payload,
            "solicitante_tipo_documento": None,
            "solicitante_documento": None,
            "solicitante_unidad": "Facultad de Ingeniería",
        },
    )
    _subir_representacion(client, solicitud["id"])

    respuesta = client.post(f"{URL}/{solicitud['id']}/radicar")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == EstadoSolicitud.RADICADA.value


def test_el_solicitante_externo_con_nit_registra_su_dv(client, externo, payload):
    base = "800197268"
    errores = _errores(
        client.post(
            URL,
            json={
                **payload,
                "solicitante_tipo_documento": "NIT",
                "solicitante_documento": base,
                "solicitante_digito_verificacion": "5",
            },
        )
    )
    assert set(errores) == {"solicitante_digito_verificacion"}

    cuerpo = _crear(
        client,
        {
            **payload,
            "solicitante_tipo_documento": "NIT",
            "solicitante_documento": "800.197.268",
            "solicitante_digito_verificacion": "4",
        },
    )
    assert cuerpo["solicitante_documento_completo"] == f"{base}-4"
