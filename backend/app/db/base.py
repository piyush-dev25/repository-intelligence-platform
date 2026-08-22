from app.db.database import Base

# Every model must be imported here, once, so SQLAlchemy's mapper
# registry knows about all of them before any relationship gets resolved.
# Both Alembic and the running app import from here.
from app.models.user import User
from app.models.repository import Repository, RepositoryFile
from app.models.file_knowledge import FileKnowledge