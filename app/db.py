from sqlalchemy import create_engine

from app.settings import settings

engine = create_engine(
    settings.database_url, pool_size=settings.database_pool_size, pool_pre_ping=True
)
