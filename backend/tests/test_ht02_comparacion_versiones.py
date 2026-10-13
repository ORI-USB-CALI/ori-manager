from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.unidades_organizacionales import TipoUnidad
from backend.models.documento import Documento
from backend.models.tipo_convenio import TipoConvenio
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.services.comparacion_versiones import (
    clasificar_documentos,
    comparar_campos,
)


@pytest.fixture
def unidad(db):
    item = UnidadOrganizacional(
        codigo=f"U-{uuid4().hex[:8]}",
        nombre="Facultad de prueba",
        tipo=TipoUnidad.FACULTAD.value,
    )
    db.add(item)
    db.commit()
    return item


@pytest.fixture
def tipo_convenio(db):
    item = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    assert item is not None
    return item


@pytest.fixture
def autor(db, crear_usuario, unidad):
    usuario = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)
    usuario.unidad_organizacional_id = unidad.id
    usuario.cargo = "Docente"
    usuario.nombre_completo = "Solicitante de prueba"
    db.commit()
    return usuario


@pytest.fixture
def gestor_ori(crear_usuario):
    return crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)


def _payload(tipo_convenio_id: int) -> dict[str, object]:
    return {
        "solicitante_unidad": "Facultad de prueba",
        "solicitante_cargo": "Docente",
        "nombre_aliado_propuesto": "Entidad contraparte",
        "tipo_identificacion_aliado_propuesto": "NIT",
        "identificacion_aliado_propuesto": "900123456",
        "tipo_aliado_propuesto": "EMPRESA",
        "correo_aliado_propuesto": "contacto@contraparte.com",
        "pais_aliado_propuesto": "Colombia",
        "ciudad_aliado_propuesto": "Cali",
        "telefono_aliado_propuesto": "6025550101",
        "direccion_aliado_propuesto": "Avenida 1 # 2-3",
        "sector_economico_aliado_propuesto": "Educación",
        "contacto_contraparte_nombre": "Contacto contraparte",
        "contacto_contraparte_cargo": "Directora",
        "contacto_contraparte_telefono": "3001234567",
        "contacto_contraparte_correo": "persona@example.com",
        "tipo_convenio_id": tipo_convenio_id,
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
        "supervisor_contraparte_telefono": "3005550303",
        "supervisor_contraparte_correo": "supervisor.contraparte@example.com",
    }


def _subir(
    client, solicitud_id: int, tipo: str, nombre: str, contenido: bytes = b"%PDF-1.4"
) -> dict[str, object]:
    respuesta = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": tipo},
        files={"archivo": (nombre, BytesIO(contenido), "application/pdf")},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _retirar(client, solicitud_id: int, documento_id: int) -> None:
    respuesta = client.delete(
        f"/api/solicitudes/{solicitud_id}/documentos/{documento_id}"
    )
    assert respuesta.status_code == 204


def _radicar(client, db, solicitud_id: int) -> None:
    db.expire_all()
    respuesta = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert respuesta.status_code == 200, respuesta.text


def _devolver(client, entrar_como, gestor, autor, solicitud_id: int) -> None:
    entrar_como(gestor)
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/devolver",
        json={"observaciones": "Ajuste el objeto y los soportes"},
    )
    assert respuesta.status_code == 200, respuesta.text
    entrar_como(autor)


def _corregir(client, solicitud_id: int, **campos) -> None:
    respuesta = client.patch(f"/api/solicitudes/{solicitud_id}", json=campos)
    assert respuesta.status_code == 200, respuesta.text


@pytest.fixture
def radicada(client, db, entrar_como, autor, tipo_convenio):
    """Solicitud radicada una vez (versión 1) con un documento de representación."""
    entrar_como(autor)
    solicitud_id = client.post(
        "/api/solicitudes", json=_payload(tipo_convenio.id)
    ).json()["id"]
    documento = _subir(
        client, solicitud_id, "OTRO_DOCUMENTO_REPRESENTACION", "representacion.pdf"
    )
    _radicar(client, db, solicitud_id)
    return {"id": solicitud_id, "documento": documento}


@pytest.fixture
def reenviada(client, db, entrar_como, autor, gestor_ori, radicada):
    """Devuelta y re-radicada con el objeto corregido (versión 2)."""
    solicitud_id = radicada["id"]
    _devolver(client, entrar_como, gestor_ori, autor, solicitud_id)
    _corregir(client, solicitud_id, objeto="Objeto corregido")
    _radicar(client, db, solicitud_id)
    return solicitud_id


def test_ca02_campos_modificados_con_valor_anterior_y_nuevo(client, reenviada):
    respuesta = client.get(f"/api/solicitudes/{reenviada}/versiones/2/comparacion")
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["solicitud_id"] == reenviada
    assert cuerpo["hay_cambios"] is True
    assert cuerpo["version_base"]["numero"] == 1
    assert cuerpo["version_comparada"]["numero"] == 2
    assert cuerpo["version_comparada"]["radicada_por"]["nombre_completo"] == (
        "Solicitante de prueba"
    )
    assert cuerpo["version_comparada"]["radicada_en"]
    assert cuerpo["campos"] == [
        {
            "campo": "objeto",
            "etiqueta": "Objeto",
            "valor_anterior": "Objeto del convenio",
            "valor_nuevo": "Objeto corregido",
        }
    ]
    assert cuerpo["documentos"] == {
        "agregados": [],
        "eliminados": [],
        "sustituidos": [],
    }


def test_ca03_documentos_agregados_eliminados_y_sustituidos(
    client, db, entrar_como, autor, gestor_ori, tipo_convenio
):
    entrar_como(autor)
    solicitud_id = client.post(
        "/api/solicitudes", json=_payload(tipo_convenio.id)
    ).json()["id"]
    representacion = _subir(
        client, solicitud_id, "OTRO_DOCUMENTO_REPRESENTACION", "representacion.pdf"
    )
    rut = _subir(client, solicitud_id, "RUT", "rut.pdf")
    camara = _subir(client, solicitud_id, "CAMARA_COMERCIO", "camara.pdf")
    soporte = _subir(client, solicitud_id, "OTRO_SOPORTE", "soporte.pdf")
    _radicar(client, db, solicitud_id)

    _devolver(client, entrar_como, gestor_ori, autor, solicitud_id)
    _corregir(client, solicitud_id, vigencia_estimada="36 meses")
    # Mismo tipo y nombre con otro tamaño: sustituido.
    _retirar(client, solicitud_id, representacion["id"])
    nueva_representacion = _subir(
        client,
        solicitud_id,
        "OTRO_DOCUMENTO_REPRESENTACION",
        "representacion.pdf",
        b"%PDF-1.4 version firmada",
    )
    # Sale uno y entra otro del mismo tipo con otro nombre: sustituido.
    _retirar(client, solicitud_id, rut["id"])
    nuevo_rut = _subir(client, solicitud_id, "RUT", "rut-2026.pdf")
    # Sin reemplazo: eliminado.
    _retirar(client, solicitud_id, camara["id"])
    # Tipo nuevo: agregado.
    cedula = _subir(client, solicitud_id, "CEDULA_REPRESENTANTE_LEGAL", "cedula.pdf")
    _radicar(client, db, solicitud_id)

    respuesta = client.get(f"/api/solicitudes/{solicitud_id}/versiones/2/comparacion")
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["hay_cambios"] is True
    assert [
        (item["campo"], item["valor_anterior"], item["valor_nuevo"])
        for item in cuerpo["campos"]
    ] == [("vigencia_estimada", "24 meses", "36 meses")]
    documentos = cuerpo["documentos"]
    assert [item["id"] for item in documentos["agregados"]] == [cedula["id"]]
    assert [item["id"] for item in documentos["eliminados"]] == [camara["id"]]
    assert documentos["eliminados"][0]["nombre_archivo"] == "camara.pdf"
    assert [
        (item["tipo"], item["anterior"]["id"], item["nuevo"]["id"])
        for item in documentos["sustituidos"]
    ] == [
        (
            "OTRO_DOCUMENTO_REPRESENTACION",
            representacion["id"],
            nueva_representacion["id"],
        ),
        ("RUT", rut["id"], nuevo_rut["id"]),
    ]
    assert soporte["id"] not in {
        item["id"] for item in documentos["agregados"] + documentos["eliminados"]
    }


def test_version_antigua_conserva_los_documentos_retirados_despues(
    client, db, entrar_como, autor, gestor_ori, radicada
):
    solicitud_id = radicada["id"]
    original = radicada["documento"]
    _devolver(client, entrar_como, gestor_ori, autor, solicitud_id)
    _retirar(client, solicitud_id, original["id"])
    reemplazo = _subir(
        client, solicitud_id, "OTRO_DOCUMENTO_REPRESENTACION", "poder.pdf"
    )
    _radicar(client, db, solicitud_id)

    # El documento retirado no se borró: queda no vigente y sigue en la versión 1.
    retirado = db.get(Documento, original["id"])
    assert retirado is not None
    assert retirado.es_vigente is False

    # Comparar la versión 1 contra la 2 (base posterior) muestra lo que tenía la 1.
    cuerpo = client.get(
        f"/api/solicitudes/{solicitud_id}/versiones/1/comparacion",
        params={"base": 2},
    ).json()
    sustituido = cuerpo["documentos"]["sustituidos"][0]
    assert sustituido["anterior"]["id"] == reemplazo["id"]
    assert sustituido["nuevo"]["id"] == original["id"]
    assert sustituido["nuevo"]["nombre_archivo"] == "representacion.pdf"


def test_reenvio_sin_cambios_no_reporta_diferencias(
    client, db, entrar_como, autor, gestor_ori, radicada
):
    solicitud_id = radicada["id"]
    _devolver(client, entrar_como, gestor_ori, autor, solicitud_id)
    # Un campo opcional vacío que se envía en blanco sigue vacío: no es un cambio.
    _corregir(client, solicitud_id, observaciones="   ")
    _radicar(client, db, solicitud_id)

    cuerpo = client.get(
        f"/api/solicitudes/{solicitud_id}/versiones/2/comparacion"
    ).json()
    assert cuerpo["hay_cambios"] is False
    assert cuerpo["campos"] == []
    assert cuerpo["documentos"] == {
        "agregados": [],
        "eliminados": [],
        "sustituidos": [],
    }


def test_base_explicita_y_errores_de_comparacion(
    client, db, entrar_como, autor, gestor_ori, reenviada
):
    _devolver(client, entrar_como, gestor_ori, autor, reenviada)
    _corregir(client, reenviada, metas_esperadas="Metas nuevas")
    _radicar(client, db, reenviada)
    ruta = f"/api/solicitudes/{reenviada}/versiones"

    cuerpo = client.get(f"{ruta}/3/comparacion", params={"base": 1}).json()
    assert cuerpo["version_base"]["numero"] == 1
    assert {item["campo"] for item in cuerpo["campos"]} == {
        "objeto",
        "metas_esperadas",
    }
    sin_base = client.get(f"{ruta}/3/comparacion").json()
    assert sin_base["version_base"]["numero"] == 2
    assert [item["campo"] for item in sin_base["campos"]] == ["metas_esperadas"]

    assert client.get(f"{ruta}/1/comparacion").status_code == 422
    assert (
        client.get(f"{ruta}/2/comparacion", params={"base": 2}).status_code == 422
    )
    assert client.get(f"{ruta}/9/comparacion").status_code == 404
    assert (
        client.get(f"{ruta}/2/comparacion", params={"base": 9}).status_code == 404
    )
    assert (
        client.get(f"{ruta}/2/comparacion", params={"base": 0}).status_code == 422
    )


def test_gestor_compara_por_recibidas(client, entrar_como, gestor_ori, reenviada):
    entrar_como(gestor_ori)
    respuesta = client.get(
        f"/api/solicitudes/recibidas/{reenviada}/versiones/2/comparacion"
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["campos"][0]["campo"] == "objeto"
    assert (
        client.get(
            "/api/solicitudes/recibidas/0/versiones/2/comparacion"
        ).status_code
        == 404
    )


def test_otro_solicitante_no_accede_a_la_comparacion(
    client, crear_usuario, entrar_como, reenviada
):
    entrar_como(crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO))
    assert (
        client.get(
            f"/api/solicitudes/{reenviada}/versiones/2/comparacion"
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/solicitudes/recibidas/{reenviada}/versiones/2/comparacion"
        ).status_code
        == 403
    )


def test_sin_sesion_responde_401(client, reenviada):
    client.cookies.clear()
    for ruta in (
        f"/api/solicitudes/{reenviada}/versiones/2/comparacion",
        f"/api/solicitudes/recibidas/{reenviada}/versiones/2/comparacion",
    ):
        assert client.get(ruta).status_code == 401


# ---- Unitarias ---------------------------------------------------------------


def _doc(id_: int, tipo: str, nombre: str, tamano: int = 10) -> Documento:
    return Documento(
        id=id_,
        tipo=tipo,
        nombre_archivo=nombre,
        tipo_mime="application/pdf",
        tamano_bytes=tamano,
    )


def _ids(documentos) -> list[int]:
    return [item.id for item in documentos]


def test_clasificacion_mismo_id_no_es_cambio():
    documento = _doc(1, "RUT", "rut.pdf")
    resultado = clasificar_documentos([documento], [documento])
    assert (resultado.agregados, resultado.eliminados, resultado.sustituidos) == (
        [],
        [],
        [],
    )


def test_clasificacion_mismo_nombre_y_tamano_con_otro_id_no_es_cambio():
    resultado = clasificar_documentos(
        [_doc(1, "RUT", "rut.pdf")], [_doc(2, "RUT", "rut.pdf")]
    )
    assert (resultado.agregados, resultado.eliminados, resultado.sustituidos) == (
        [],
        [],
        [],
    )


def test_clasificacion_mismo_nombre_con_otro_tamano_es_sustitucion():
    resultado = clasificar_documentos(
        [_doc(1, "RUT", "rut.pdf", 10)], [_doc(2, "RUT", "rut.pdf", 20)]
    )
    assert [(item.anterior.id, item.nuevo.id) for item in resultado.sustituidos] == [
        (1, 2)
    ]
    assert resultado.sustituidos[0].tipo == "RUT"
    assert resultado.agregados == resultado.eliminados == []


def test_clasificacion_empareja_por_tipo_en_orden_de_id():
    anteriores = [
        _doc(2, "OTRO_SOPORTE", "b.pdf"),
        _doc(1, "OTRO_SOPORTE", "a.pdf"),
        _doc(3, "RUT", "rut.pdf"),
    ]
    nuevos = [
        _doc(6, "CAMARA_COMERCIO", "camara.pdf"),
        _doc(2, "OTRO_SOPORTE", "b.pdf"),
        _doc(5, "OTRO_SOPORTE", "d.pdf"),
        _doc(4, "OTRO_SOPORTE", "c.pdf"),
    ]
    resultado = clasificar_documentos(anteriores, nuevos)
    assert [(item.anterior.id, item.nuevo.id) for item in resultado.sustituidos] == [
        (1, 4)
    ]
    assert _ids(resultado.agregados) == [5, 6]
    assert _ids(resultado.eliminados) == [3]


def test_comparar_campos_usa_la_union_de_claves_y_etiqueta_de_respaldo():
    cambios = comparar_campos(
        {"objeto": "A", "observaciones": "", "campo_retirado": "x"},
        {"objeto": "A", "observaciones": None, "campo_nuevo_formulario": "y"},
    )
    assert [(item.campo, item.etiqueta) for item in cambios] == [
        ("campo_retirado", "Campo retirado"),
        ("campo_nuevo_formulario", "Campo nuevo formulario"),
    ]
    assert (cambios[0].valor_anterior, cambios[0].valor_nuevo) == ("x", None)
    assert (cambios[1].valor_anterior, cambios[1].valor_nuevo) == (None, "y")
