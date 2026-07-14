from app.repositories.base_repository import BaseRepository
from app.models.user import User
from app.models.company import Company
from sqlalchemy.orm import Session
from uuid import UUID

class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    def find_by_email(self, db: Session, email: str) -> User | None:
        # Query globally across all companies to locate the user during login
        return db.query(User).filter(User.email == email).first()

    def find_for_login(self, db: Session, email: str, tenant_id: UUID | None = None, role: str | None = None) -> User | None:
        query = db.query(User).filter(User.email == email)
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
        if role:
            query = query.filter(User.role == role)
        return query.first()

    def get_user_by_id(self, db: Session, id: UUID) -> User | None:
        return db.query(User).filter(User.id == id).first()

    def create_company(self, db: Session, company: Company) -> Company:
        db.add(company)
        db.flush()
        return company

    def create_user(self, db: Session, user: User) -> User:
        db.add(user)
        db.flush()
        return user
