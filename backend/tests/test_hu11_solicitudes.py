from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.unidades_organizacionales import TipoUnidad
from backend.main import app
from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.enums import EstadoSolicitud
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.solicitud_usuario import SolicitudUsuario
from backend.models.tipo_convenio import TipoConvenio
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.services import documentos
from backend.services.documentos import get_almacen_documentos


def _autenticar(client, crear_usuario, entrar_como, rol, tipo, **campos):
    usuario = crear_usuario(rol, tipo_usuario=tipo)
    for nombre, valor in campos.items():
        setattr(usuario, nombre, valor)
    usuario.nombre_completo = campos.get("nombre_completo", "Responsable de prueba")
    entrar_como(usuario)
    return usuario


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


def _payload(tipo_convenio_id: int) -> dict[str, object]:
    return {
        "solicitante_unidad": "Dependencia corregida para la solicitud",
        "solicitante_programa": "Programa de prueba",
        "solicitante_cargo": "Cargo presentado",
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
        "observaciones": "Sin observaciones",
    }


def _subir_documentos(client, solicitud_id: int) -> None:
    tipo = "OTRO_DOCUMENTO_REPRESENTACION"
    respuesta = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": tipo},
        files={
            "archivo": (
                f"../../{tipo}.pdf",
                BytesIO(b"%PDF-1.4 soporte"),
                "application/pdf",
            )
        },
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["nombre_original"] == f"{tipo}.pdf"


def test_ca01_interno_y_externo_crean_borrador_tipo_derivado(
    db, client, crear_usuario, entrar_como, unidad
):
    interno = _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Docente",
    )
    db.commit()
    creado = client.post("/api/solicitudes", json={})
    assert creado.status_code == 201, creado.text
    assert creado.json()["tipo_solicitante"] == "INTERNO"
    assert creado.json()["solicitante_id"] == interno.id
    assert creado.json()["solicitante_unidad"] == unidad.nombre
    assert (
        client.post(
            "/api/solicitudes", json={"tipo_solicitante": "EXTERNO"}
        ).status_code
        == 422
    )

    externo = _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_EXTERNO,
        TipoUsuario.EXTERNO,
        documento_identidad="CE-123",
        entidad_externa="Entidad externa",
    )
    db.commit()
    creado = client.post("/api/solicitudes", json={})
    assert creado.status_code == 201
    cuerpo = creado.json()
    assert cuerpo["tipo_solicitante"] == "EXTERNO"
    assert cuerpo["solicitante_id"] == externo.id
    assert cuerpo["solicitante_documento"] == "CE-123"
    assert cuerpo["solicitante_entidad"] == "Entidad externa"


def test_ca02_ca03_ca05_ca06_ca07_radicacion_completa_sin_crear_dominio_posterior(
    db, client, crear_usuario, entrar_como, unidad, tipo_convenio
):
    usuario = _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Coordinadora",
    )
    db.commit()
    aliados_antes = db.scalar(select(func.count()).select_from(Aliado))
    convenios_antes = db.scalar(select(func.count()).select_from(Convenio))
    creado = client.post("/api/solicitudes", json=_payload(tipo_convenio.id))
    assert creado.status_code == 201, creado.text
    solicitud_id = creado.json()["id"]
    _subir_documentos(client, solicitud_id)
    detalle = client.get(f"/api/solicitudes/{solicitud_id}").json()
    assert len(detalle["documentos"]) == 1

    respuesta = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == EstadoSolicitud.RADICADA
    assert cuerpo["fecha_radicacion"]
    assert cuerpo["fecha_recibido_ori"] == cuerpo["fecha_radicacion"]
    assert cuerpo["solicitante_id"] == usuario.id
    assert cuerpo["solicitante_unidad"] == "Dependencia corregida para la solicitud"
    assert cuerpo["solicitante_cargo"] == "Cargo presentado"
    assert cuerpo["nombre_aliado_propuesto"] == "Entidad contraparte"
    assert db.scalar(select(func.count()).select_from(Aliado)) == aliados_antes
    assert db.scalar(select(func.count()).select_from(Convenio)) == convenios_antes
    assert (
        client.patch(
            f"/api/solicitudes/{solicitud_id}", json={"objeto": "Cambio"}
        ).status_code
        == 409
    )


def test_ca04_incompleta_permanece_borrador_y_no_hay_efectos_parciales(
    db, client, crear_usuario, entrar_como, unidad
):
    _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Docente",
    )
    db.commit()
    solicitud_id = client.post("/api/solicitudes", json={"objeto": "Parcial"}).json()[
        "id"
    ]
    respuesta = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert respuesta.status_code == 422
    errores = respuesta.json()["detail"]["errors"]
    assert "tipo_convenio_id" in errores
    assert "documentos.representacion_legal" in errores
    solicitud = db.get(SolicitudConvenio, solicitud_id)
    db.refresh(solicitud)
    assert solicitud.estado == EstadoSolicitud.BORRADOR
    assert solicitud.fecha_radicacion is None


@pytest.mark.parametrize(
    "campo",
    [
        "pais_aliado_propuesto",
        "ciudad_aliado_propuesto",
        "telefono_aliado_propuesto",
        "direccion_aliado_propuesto",
        "contacto_contraparte_cargo",
        "contacto_contraparte_correo",
        "supervisor_usb_nombre",
        "supervisor_usb_cargo",
        "supervisor_usb_telefono",
        "supervisor_usb_correo",
        "supervisor_contraparte_nombre",
        "supervisor_contraparte_cargo",
        "supervisor_contraparte_telefono",
        "supervisor_contraparte_correo",
    ],
)
def test_plantilla_campo_obligatorio_faltante_impide_radicar(
    campo, db, client, crear_usuario, entrar_como, unidad, tipo_convenio
):
    _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Docente",
    )
    db.commit()
    datos = _payload(tipo_convenio.id)
    datos.pop(campo)
    solicitud_id = client.post("/api/solicitudes", json=datos).json()["id"]
    _subir_documentos(client, solicitud_id)

    respuesta = client.post(f"/api/solicitudes/{solicitud_id}/radicar")

    assert respuesta.status_code == 422
    assert campo in respuesta.json()["detail"]["errors"]
    assert db.get(SolicitudConvenio, solicitud_id).estado == EstadoSolicitud.BORRADOR


def test_catalogo_contiene_las_seis_opciones_oficiales(
    db, client, crear_usuario, entrar_como, unidad
):
    _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Docente",
    )
    db.commit()
    respuesta = client.get("/api/solicitudes/catalogos")
    assert respuesta.status_code == 200
    tipos = {
        item["codigo"]: item["naturaleza"]
        for item in respuesta.json()["tipos_convenio"]
    }
    assert {
        "MARCO",
        "ESPECIFICO",
        "PRACTICA_INTERNACIONAL",
        "INVESTIGACION",
        "PLAN_BENEFICIOS",
        "OTRO",
    } <= set(tipos)
    assert tipos["MARCO"] == "MARCO"
    assert tipos["ESPECIFICO"] == "ESPECIFICO"
    assert all(
        tipos[codigo] is None
        for codigo in (
            "PRACTICA_INTERNACIONAL",
            "INVESTIGACION",
            "PLAN_BENEFICIOS",
            "OTRO",
        )
    )


def test_otro_soporte_no_reemplaza_documentacion_de_representacion(
    db, client, crear_usuario, entrar_como, unidad, tipo_convenio
):
    _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Docente",
    )
    db.commit()
    solicitud_id = client.post(
        "/api/solicitudes", json=_payload(tipo_convenio.id)
    ).json()["id"]
    carga = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": "OTRO_SOPORTE"},
        files={"archivo": ("soporte.pdf", b"%PDF-1.4 soporte", "application/pdf")},
    )
    assert carga.status_code == 201
    respuesta = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert respuesta.status_code == 422
    assert "documentos.representacion_legal" in respuesta.json()["detail"]["errors"]


def test_storage_local_falla_cerrado_fuera_de_desarrollo(monkeypatch):
    documentos.get_almacen_documentos.cache_clear()
    monkeypatch.setattr(documentos.settings, "app_env", "production")
    monkeypatch.setattr(documentos.settings, "document_storage_provider", "local")
    with pytest.raises(RuntimeError, match="solo está permitido en development"):
        documentos.get_almacen_documentos()
    documentos.get_almacen_documentos.cache_clear()


def test_radicacion_verifica_existencia_en_storage_resuelto(
    db, client, crear_usuario, entrar_como, unidad, tipo_convenio
):
    class StorageRemotoFalso:
        def __init__(self):
            self.claves_consultadas = []

        def guardar(self, clave, contenido):
            raise AssertionError("radicar no debe guardar")

        def eliminar(self, clave):
            raise AssertionError("radicar no debe eliminar")

        def existe(self, clave):
            self.claves_consultadas.append(clave)
            return True

    _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Docente",
    )
    db.commit()
    solicitud_id = client.post(
        "/api/solicitudes", json=_payload(tipo_convenio.id)
    ).json()["id"]
    _subir_documentos(client, solicitud_id)
    storage_remoto = StorageRemotoFalso()
    app.dependency_overrides[get_almacen_documentos] = lambda: storage_remoto

    respuesta = client.post(f"/api/solicitudes/{solicitud_id}/radicar")

    assert respuesta.status_code == 200
    assert len(storage_remoto.claves_consultadas) == 1
    assert storage_remoto.claves_consultadas[0].startswith(
        f"solicitudes/{solicitud_id}/"
    )


def test_interno_programa_precarga_y_radica_con_programa_y_padre(
    db, client, crear_usuario, entrar_como, unidad, tipo_convenio
):
    programa = UnidadOrganizacional(
        codigo=f"P-{uuid4().hex[:8]}",
        nombre="Programa de Ingeniería",
        tipo=TipoUnidad.PROGRAMA.value,
        unidad_padre_id=unidad.id,
    )
    db.add(programa)
    db.commit()
    _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=programa.id,
        cargo="Docente",
    )
    db.commit()
    datos = _payload(tipo_convenio.id)
    datos.pop("solicitante_unidad")
    datos.pop("solicitante_programa")
    solicitud_id = client.post("/api/solicitudes", json=datos).json()["id"]
    _subir_documentos(client, solicitud_id)
    respuesta = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert respuesta.status_code == 200
    assert respuesta.json()["solicitante_unidad"] == unidad.nombre
    assert respuesta.json()["solicitante_programa"] == programa.nombre


def test_interno_facultad_radica_sin_inventar_programa(
    db, client, crear_usuario, entrar_como, unidad, tipo_convenio
):
    _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Docente",
    )
    db.commit()
    datos = _payload(tipo_convenio.id)
    datos.pop("solicitante_unidad")
    datos.pop("solicitante_programa")
    solicitud_id = client.post("/api/solicitudes", json=datos).json()["id"]
    _subir_documentos(client, solicitud_id)
    respuesta = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert respuesta.status_code == 200
    assert respuesta.json()["solicitante_unidad"] == unidad.nombre
    assert respuesta.json()["solicitante_programa"] is None


def test_interno_unidad_administrativa_radica_sin_programa(
    db, client, crear_usuario, entrar_como, tipo_convenio
):
    unidad = UnidadOrganizacional(
        codigo=f"UA-{uuid4().hex[:8]}",
        nombre="Oficina de Cooperación",
        tipo=TipoUnidad.UNIDAD_ADMINISTRATIVA.value,
    )
    db.add(unidad)
    db.commit()
    _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Profesional",
    )
    db.commit()
    datos = _payload(tipo_convenio.id)
    datos.pop("solicitante_unidad")
    datos.pop("solicitante_programa")
    solicitud_id = client.post("/api/solicitudes", json=datos).json()["id"]
    _subir_documentos(client, solicitud_id)
    respuesta = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert respuesta.status_code == 200
    assert respuesta.json()["solicitante_unidad"] == unidad.nombre
    assert respuesta.json()["solicitante_programa"] is None


def test_interno_sin_informacion_organizacional_no_puede_radicar(
    db, client, crear_usuario, entrar_como, tipo_convenio
):
    _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        cargo="Docente",
    )
    db.commit()
    datos = _payload(tipo_convenio.id)
    datos.pop("solicitante_unidad")
    datos.pop("solicitante_programa")
    solicitud_id = client.post("/api/solicitudes", json=datos).json()["id"]
    _subir_documentos(client, solicitud_id)
    respuesta = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert respuesta.status_code == 422
    assert "solicitante_unidad" in respuesta.json()["detail"]["errors"]


def test_seed_no_sobrescribe_tipo_convenio_preexistente(db):
    marco = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    assert marco is not None
    marco.nombre = "Nombre preexistente"
    marco.activo = False
    marco.descripcion = "Descripción preexistente"
    db.flush()
    ruta_migracion = (
        Path(__file__).parents[1]
        / "migrations/versions/a711c4d8e912_hu11_solicitud_radicacion.py"
    )
    spec = spec_from_file_location("migracion_hu11", ruta_migracion)
    assert spec is not None and spec.loader is not None
    migracion = module_from_spec(spec)
    spec.loader.exec_module(migracion)
    db.execute(
        text(migracion.SEMILLA_TIPOS_SQL),
        {"descripcion": migracion.SEMILLA_DESCRIPCION},
    )
    db.refresh(marco)
    assert marco.nombre == "Nombre preexistente"
    assert marco.activo is False
    assert marco.descripcion == "Descripción preexistente"
    assert marco.naturaleza == "MARCO"


def test_endpoints_de_metadata_no_resuelven_storage(
    db, client, crear_usuario, entrar_como, unidad
):
    def storage_no_disponible():
        raise RuntimeError("storage no debe resolverse")

    app.dependency_overrides[get_almacen_documentos] = storage_no_disponible
    _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Docente",
    )
    db.commit()
    creada = client.post("/api/solicitudes", json={})
    assert creada.status_code == 201
    solicitud_id = creada.json()["id"]
    assert client.get("/api/solicitudes/mias").status_code == 200
    assert client.get(f"/api/solicitudes/{solicitud_id}").status_code == 200
    assert (
        client.patch(
            f"/api/solicitudes/{solicitud_id}", json={"objeto": "Borrador"}
        ).status_code
        == 200
    )


def test_ca08_solo_propias_y_asociadas_sin_acceso_directo_ajeno(
    db, client, crear_usuario, entrar_como, unidad
):
    primero = _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Docente",
    )
    db.commit()
    propia = client.post("/api/solicitudes", json={}).json()["id"]
    segundo = _autenticar(
        client,
        crear_usuario,
        entrar_como,
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        unidad_organizacional_id=unidad.id,
        cargo="Docente",
    )
    db.commit()
    ajena = client.post("/api/solicitudes", json={}).json()["id"]
    entrar_como(primero)
    assert client.get(f"/api/solicitudes/{propia}").status_code == 200
    assert client.get(f"/api/solicitudes/{ajena}").status_code == 404
    ids = {item["id"] for item in client.get("/api/solicitudes/mias").json()["items"]}
    assert propia in ids and ajena not in ids
    db.add(SolicitudUsuario(solicitud_id=ajena, usuario_id=primero.id))
    db.commit()
    assert client.get(f"/api/solicitudes/{ajena}").status_code == 200
    assert (
        client.patch(
            f"/api/solicitudes/{ajena}", json={"objeto": "No permitido"}
        ).status_code
        == 404
    )
    assert segundo.id != primero.id
