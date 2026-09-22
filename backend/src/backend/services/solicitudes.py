from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex

from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.core.roles import TipoUsuario
from backend.core.unidades_organizacionales import TipoUnidad
from backend.models.documento_solicitud import DocumentoSolicitud
from backend.models.enums import EstadoSolicitud, TipoAliado, TipoDocumentoSolicitud
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.solicitud_usuario import SolicitudUsuario
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.schemas.solicitud import SolicitudActualizar, SolicitudCrear
from backend.services.documentos import (
    EXTENSIONES_PERMITIDAS,
    TAMANO_MAXIMO_DOCUMENTO,
    TIPOS_DOCUMENTO_REPRESENTACION,
    TIPOS_MIME_PERMITIDOS,
    AlmacenDocumentos,
)


class ErrorSolicitud(Exception):
    pass


class SolicitudNoEncontrada(ErrorSolicitud):
    pass


class SolicitudNoEditable(ErrorSolicitud):
    pass


class SolicitudIncompleta(ErrorSolicitud):
    def __init__(self, errores: dict[str, str]):
        super().__init__("La solicitud está incompleta")
        self.errores = errores


class DocumentoInvalido(ErrorSolicitud):
    pass


class ReferenciaSolicitudInvalida(ErrorSolicitud):
    pass


class ServicioSolicitudes:
    def __init__(self, db: Session, almacen: AlmacenDocumentos | None = None):
        self.db = db
        self.almacen = almacen

    def _almacen_requerido(self) -> AlmacenDocumentos:
        if self.almacen is None:
            raise RuntimeError("Esta operación requiere un almacén documental")
        return self.almacen

    @staticmethod
    def _snapshot(usuario: Usuario) -> dict[str, object | None]:
        unidad = usuario.unidad_organizacional
        unidad_nombre = None
        programa_nombre = None
        if unidad is not None and unidad.tipo == TipoUnidad.PROGRAMA:
            programa_nombre = unidad.nombre
            unidad_nombre = unidad.unidad_padre.nombre if unidad.unidad_padre else None
        elif unidad is not None:
            unidad_nombre = unidad.nombre
        return {
            "tipo_solicitante": usuario.tipo_usuario,
            "unidad_organizacional_id": usuario.unidad_organizacional_id,
            "solicitante_nombre": usuario.nombre_completo,
            "solicitante_correo": usuario.correo,
            "solicitante_documento": usuario.documento_identidad,
            "solicitante_cargo": usuario.cargo,
            "solicitante_entidad": usuario.entidad_externa,
            "solicitante_unidad": unidad_nombre,
            "solicitante_programa": programa_nombre,
        }

    def _consulta_visible(self, usuario: Usuario):
        asociada = exists().where(
            SolicitudUsuario.solicitud_id == SolicitudConvenio.id,
            SolicitudUsuario.usuario_id == usuario.id,
        )
        return select(SolicitudConvenio).where(
            or_(SolicitudConvenio.solicitante_id == usuario.id, asociada)
        )

    def _cargar(
        self, solicitud_id: int, usuario: Usuario, *, bloquear: bool = False
    ) -> SolicitudConvenio:
        consulta = (
            self._consulta_visible(usuario)
            .where(SolicitudConvenio.id == solicitud_id)
            .options(selectinload(SolicitudConvenio.documentos))
        )
        if bloquear:
            consulta = consulta.with_for_update()
        solicitud = self.db.scalar(consulta)
        if solicitud is None:
            raise SolicitudNoEncontrada("Solicitud no encontrada")
        return solicitud

    def _cargar_editable(
        self, solicitud_id: int, usuario: Usuario, *, bloquear: bool = False
    ) -> SolicitudConvenio:
        solicitud = self._cargar(solicitud_id, usuario, bloquear=bloquear)
        if solicitud.solicitante_id != usuario.id:
            raise SolicitudNoEncontrada("Solicitud no encontrada")
        if solicitud.estado != EstadoSolicitud.BORRADOR:
            raise SolicitudNoEditable(
                "Solo se pueden modificar solicitudes en BORRADOR"
            )
        return solicitud

    def crear(self, datos: SolicitudCrear, usuario: Usuario) -> SolicitudConvenio:
        valores = {**self._snapshot(usuario), **self._valores(datos)}
        solicitud = SolicitudConvenio(
            consecutivo=f"TEMP-{token_hex(12)}",
            solicitante_id=usuario.id,
            estado=EstadoSolicitud.BORRADOR.value,
            **valores,
        )
        self._validar_tipo_convenio(solicitud.tipo_convenio_id)
        self.db.add(solicitud)
        self.db.flush()
        solicitud.consecutivo = f"SOL-{solicitud.id:08d}"
        self.db.commit()
        return self.obtener(solicitud.id, usuario)

    @staticmethod
    def _valores(datos: SolicitudCrear | SolicitudActualizar) -> dict[str, object]:
        return {
            campo: valor.value if hasattr(valor, "value") else valor
            for campo, valor in datos.model_dump(exclude_unset=True).items()
        }

    def _validar_tipo_convenio(self, tipo_id: int | None) -> None:
        if tipo_id is None:
            return
        tipo = self.db.get(TipoConvenio, tipo_id)
        if tipo is None or not tipo.activo:
            raise ReferenciaSolicitudInvalida(
                "El tipo de convenio no existe o está inactivo"
            )

    def actualizar(
        self, solicitud_id: int, datos: SolicitudActualizar, usuario: Usuario
    ) -> SolicitudConvenio:
        solicitud = self._cargar_editable(solicitud_id, usuario, bloquear=True)
        cambios = self._valores(datos)
        self._validar_tipo_convenio(
            cambios.get("tipo_convenio_id", solicitud.tipo_convenio_id)
        )
        for campo, valor in cambios.items():
            setattr(solicitud, campo, valor)
        self.db.commit()
        return self.obtener(solicitud.id, usuario)

    def listar(self, usuario: Usuario) -> list[SolicitudConvenio]:
        return list(
            self.db.scalars(
                self._consulta_visible(usuario)
                .options(selectinload(SolicitudConvenio.documentos))
                .order_by(
                    SolicitudConvenio.creado_en.desc(), SolicitudConvenio.id.desc()
                )
            ).unique()
        )

    def obtener(self, solicitud_id: int, usuario: Usuario) -> SolicitudConvenio:
        return self._cargar(solicitud_id, usuario)

    def agregar_documento(
        self,
        solicitud_id: int,
        usuario: Usuario,
        tipo_documento: TipoDocumentoSolicitud,
        nombre: str,
        tipo_mime: str,
        contenido: bytes,
    ) -> DocumentoSolicitud:
        solicitud = self._cargar_editable(solicitud_id, usuario, bloquear=True)
        nombre_seguro = Path(nombre.replace("\\", "/")).name.strip()
        extension = Path(nombre_seguro).suffix.lower()
        if not nombre_seguro or extension not in EXTENSIONES_PERMITIDAS:
            raise DocumentoInvalido("Extensión no permitida; use PDF, JPG, JPEG o PNG")
        if tipo_mime not in TIPOS_MIME_PERMITIDOS:
            raise DocumentoInvalido("Tipo de contenido no permitido")
        if not contenido:
            raise DocumentoInvalido("El documento está vacío")
        if len(contenido) > TAMANO_MAXIMO_DOCUMENTO:
            raise DocumentoInvalido("El documento supera el límite de 10 MB")
        clave = f"solicitudes/{solicitud.id}/{token_hex(20)}{extension}"
        documento = DocumentoSolicitud(
            solicitud_id=solicitud.id,
            tipo_documento=tipo_documento.value,
            nombre_original=nombre_seguro[:255],
            tipo_mime=tipo_mime,
            tamano_bytes=len(contenido),
            clave_objeto=clave,
        )
        almacen = self._almacen_requerido()
        almacen.guardar(clave, contenido)
        self.db.add(documento)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            almacen.eliminar(clave)
            raise
        self.db.refresh(documento)
        return documento

    def eliminar_documento(
        self, solicitud_id: int, documento_id: int, usuario: Usuario
    ) -> None:
        solicitud = self._cargar_editable(solicitud_id, usuario, bloquear=True)
        documento = next(
            (item for item in solicitud.documentos if item.id == documento_id), None
        )
        if documento is None:
            raise SolicitudNoEncontrada("Documento no encontrado")
        clave = documento.clave_objeto
        self.db.delete(documento)
        self.db.commit()
        self._almacen_requerido().eliminar(clave)

    def _errores_radicacion(
        self, solicitud: SolicitudConvenio, usuario: Usuario
    ) -> dict[str, str]:
        requeridos = (
            "nombre_aliado_propuesto",
            "tipo_identificacion_aliado_propuesto",
            "identificacion_aliado_propuesto",
            "tipo_aliado_propuesto",
            "correo_aliado_propuesto",
            "pais_aliado_propuesto",
            "ciudad_aliado_propuesto",
            "telefono_aliado_propuesto",
            "direccion_aliado_propuesto",
            "contacto_contraparte_nombre",
            "contacto_contraparte_cargo",
            "contacto_contraparte_telefono",
            "contacto_contraparte_correo",
            "tipo_convenio_id",
            "justificacion",
            "objeto",
            "actividades_por_parte",
            "metas_esperadas",
            "implicacion_financiera",
            "vigencia_estimada",
            "requisitos_renovacion",
            "supervisor_usb_nombre",
            "supervisor_usb_cargo",
            "supervisor_usb_telefono",
            "supervisor_usb_correo",
            "supervisor_contraparte_nombre",
            "supervisor_contraparte_cargo",
            "supervisor_contraparte_telefono",
            "supervisor_contraparte_correo",
        )
        errores = {
            campo: "Este campo es obligatorio"
            for campo in requeridos
            if not getattr(solicitud, campo)
        }
        if (
            solicitud.tipo_aliado_propuesto == TipoAliado.EMPRESA
            and not solicitud.sector_economico_aliado_propuesto
        ):
            errores["sector_economico_aliado_propuesto"] = (
                "Es obligatorio para una empresa"
            )
        if not solicitud.solicitante_nombre:
            errores["solicitante_nombre"] = "Este campo es obligatorio"
        if usuario.tipo_usuario == TipoUsuario.INTERNO:
            unidad = usuario.unidad_organizacional
            if unidad is None:
                if not (solicitud.solicitante_unidad or solicitud.solicitante_programa):
                    errores["solicitante_unidad"] = (
                        "Ingrese la Facultad, Dependencia, Programa o Unidad aplicable"
                    )
            elif unidad.tipo == TipoUnidad.PROGRAMA:
                if not solicitud.solicitante_programa:
                    errores["solicitante_programa"] = "Este campo es obligatorio"
                if unidad.unidad_padre is not None and not solicitud.solicitante_unidad:
                    errores["solicitante_unidad"] = "Este campo es obligatorio"
            elif not solicitud.solicitante_unidad:
                errores["solicitante_unidad"] = "Este campo es obligatorio"
            if not solicitud.solicitante_cargo:
                errores["solicitante_cargo"] = "Este campo es obligatorio"
        else:
            if not solicitud.solicitante_documento:
                errores["solicitante_documento"] = "Este campo es obligatorio"
            if not solicitud.solicitante_entidad:
                errores["solicitante_entidad"] = "Este campo es obligatorio"
        cargados = {
            TipoDocumentoSolicitud(item.tipo_documento) for item in solicitud.documentos
        }
        if not cargados.intersection(TIPOS_DOCUMENTO_REPRESENTACION):
            errores["documentos.representacion_legal"] = (
                "Adjunte al menos un documento de representación legal aplicable"
            )
        for documento in solicitud.documentos:
            if not self._almacen_requerido().existe(documento.clave_objeto):
                errores[f"documentos.{documento.id}"] = (
                    "El archivo almacenado no está disponible"
                )
        return errores

    def radicar(self, solicitud_id: int, usuario: Usuario) -> SolicitudConvenio:
        solicitud = self._cargar_editable(solicitud_id, usuario, bloquear=True)
        errores = self._errores_radicacion(solicitud, usuario)
        if errores:
            raise SolicitudIncompleta(errores)
        solicitud.estado = EstadoSolicitud.RADICADA.value
        instante = datetime.now(UTC)
        solicitud.fecha_radicacion = instante
        solicitud.fecha_recibido_ori = instante
        self.db.commit()
        return self.obtener(solicitud.id, usuario)
