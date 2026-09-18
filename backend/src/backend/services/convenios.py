from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.enums import AlcanceConvenio, EstadoConvenio
from backend.models.etapa import Etapa
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.usuario import Usuario
from backend.schemas.convenio import ConvenioActualizar, ConvenioCrear


class ErrorConvenio(Exception):
    pass


class ConvenioNoEncontrado(ErrorConvenio):
    pass


class ConvenioDuplicado(ErrorConvenio):
    pass


class ReferenciaConvenioInvalida(ErrorConvenio):
    pass


class ServicioConvenios:
    def __init__(self, db: Session):
        self.db = db

    def _validar_referencias(self, datos: dict[str, object]) -> None:
        aliado_id = datos.get("aliado_id")
        if aliado_id is not None:
            aliado = self.db.get(Aliado, aliado_id)
            if aliado is None:
                raise ReferenciaConvenioInvalida("El aliado seleccionado no existe")
            if not aliado.activo:
                raise ReferenciaConvenioInvalida(
                    "El aliado seleccionado está inactivo"
                )
        tipo_id = datos.get("tipo_convenio_id")
        if tipo_id is not None and self.db.get(TipoConvenio, tipo_id) is None:
            raise ReferenciaConvenioInvalida("El tipo de convenio no existe")
        etapa_id = datos.get("etapa_actual_id")
        if etapa_id is not None and self.db.get(Etapa, etapa_id) is None:
            raise ReferenciaConvenioInvalida("La etapa indicada no existe")
        unidad_id = datos.get("unidad_organizacional_id")
        if unidad_id is not None and self.db.get(UnidadOrganizacional, unidad_id) is None:
            raise ReferenciaConvenioInvalida("La unidad organizacional no existe")
        origen_id = datos.get("convenio_origen_id")
        if origen_id is not None and self.db.get(Convenio, origen_id) is None:
            raise ReferenciaConvenioInvalida("El convenio de origen no existe")
        alcance = datos.get("alcance")
        alcance_valor = alcance.value if isinstance(alcance, AlcanceConvenio) else alcance
        if alcance_valor == AlcanceConvenio.PROGRAMA and unidad_id is None:
            raise ReferenciaConvenioInvalida(
                "unidad_organizacional_id es obligatorio para alcance PROGRAMA"
            )

    def crear(self, datos: ConvenioCrear, usuario: Usuario) -> Convenio:
        if self.db.get(SolicitudConvenio, datos.solicitud_id) is None:
            raise ReferenciaConvenioInvalida("La solicitud indicada no existe")
        if self.db.scalar(
            select(Convenio.id).where(Convenio.solicitud_id == datos.solicitud_id)
        ) is not None:
            raise ConvenioDuplicado("La solicitud ya tiene un convenio registrado")
        valores = datos.model_dump()
        self._validar_referencias(valores)
        valores = {
            campo: valor.value if isinstance(valor, AlcanceConvenio) else valor
            for campo, valor in valores.items()
        }
        convenio = Convenio(
            **valores,
            estado=EstadoConvenio.EN_TRAMITE.value,
            creado_por_id=usuario.id,
        )
        self.db.add(convenio)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConvenioDuplicado(
                "La solicitud o el código ya están asociados a otro convenio"
            ) from exc
        return self.obtener(convenio.id)

    def obtener(self, convenio_id: int) -> Convenio:
        convenio = self.db.scalar(
            select(Convenio)
            .options(joinedload(Convenio.aliado), joinedload(Convenio.creado_por))
            .where(Convenio.id == convenio_id)
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        return convenio

    def actualizar(
        self, convenio_id: int, datos: ConvenioActualizar
    ) -> Convenio:
        convenio = self.obtener(convenio_id)
        cambios = datos.model_dump(exclude_unset=True)
        combinados = {
            "aliado_id": convenio.aliado_id,
            "tipo_convenio_id": convenio.tipo_convenio_id,
            "etapa_actual_id": convenio.etapa_actual_id,
            "alcance": convenio.alcance,
            "unidad_organizacional_id": convenio.unidad_organizacional_id,
            "convenio_origen_id": convenio.convenio_origen_id,
            **cambios,
        }
        self._validar_referencias(combinados)
        for campo, valor in cambios.items():
            setattr(
                convenio,
                campo,
                valor.value if isinstance(valor, AlcanceConvenio) else valor,
            )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConvenioDuplicado("El código ya pertenece a otro convenio") from exc
        return self.obtener(convenio.id)
