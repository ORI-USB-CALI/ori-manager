import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.permisos import Rol
from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.session import Session


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rol: Mapped[Rol] = mapped_column(
        Enum(
            Rol,
            name="ck_users_rol",
            native_enum=False,
            create_constraint=True,
            length=30,
            values_callable=lambda roles: [rol.value for rol in roles],
        ),
        default=Rol.USUARIO_ORI,
        server_default=Rol.USUARIO_ORI.value,
        nullable=False,
    )

    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
