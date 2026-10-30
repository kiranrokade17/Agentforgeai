from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash, verify_password
from app.repositories.user_repo import UserRepository
from app.repositories.workspace_repo import WorkspaceRepository
from app.schemas.auth import Token, UserLogin, UserRegister, UserResponse


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.workspace_repo = WorkspaceRepository(session)

    async def register(self, data: UserRegister) -> UserResponse:
        existing = await self.user_repo.get_by_email(data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists",
            )

        hashed_password = get_password_hash(data.password)
        user = await self.user_repo.create(
            name=data.name, email=data.email, password_hash=hashed_password
        )

        # Create default personal workspace for the newly registered user
        workspace_name = f"{data.name.split()[0]}'s Workspace"
        await self.workspace_repo.create(name=workspace_name, owner_id=user.id)

        return UserResponse.model_validate(user)

    async def login(self, data: UserLogin) -> Token:
        user = await self.user_repo.get_by_email(data.email)
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(subject=str(user.id))
        return Token(access_token=access_token, token_type="bearer")
