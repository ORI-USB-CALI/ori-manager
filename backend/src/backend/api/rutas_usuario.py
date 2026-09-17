from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.db.session import get_db
from backend.schemas.usuario import UsuarioLeer, UsuarioListar, UsuarioCrear, UsuarioActualizar, UsuarioCambiarRol
from backend.services import usuario_service

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

@router.get("/", response_model=list[UsuarioListar])
def listar(db: Session = Depends(get_db)):
    return usuario_service.listar_usuarios(db)

@router.get("/{usuario_id}", response_model=UsuarioLeer)
def obtener(usuario_id: int, db: Session = Depends(get_db)):
    return usuario_service.obtener_usuario(db, usuario_id)

@router.post("/", response_model=UsuarioLeer)
def crear(usuario_in: UsuarioCrear, db: Session = Depends(get_db)):
    return usuario_service.crear_usuario(db, usuario_in)

@router.patch("/{usuario_id}", response_model=UsuarioLeer)
def editar(usuario_id: int, usuario_in: UsuarioActualizar, db: Session = Depends(get_db)):
    return usuario_service.editar_usuario(db, usuario_id, usuario_in)

@router.patch("/{usuario_id}/rol", response_model=UsuarioLeer)
def cambiar_rol(usuario_id: int, rol_in: UsuarioCambiarRol, db: Session = Depends(get_db)):
    return usuario_service.cambiar_rol(db, usuario_id, rol_in)

@router.post("/{usuario_id}/desactivar", response_model=UsuarioLeer)
def desactivar(usuario_id: int, db: Session = Depends(get_db)):
    return usuario_service.desactivar_usuario(db, usuario_id)