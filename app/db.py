from psycopg_pool import ConnectionPool

from app.settings import settings

pool = ConnectionPool(
    settings.database_url,
    min_size=1,
    max_size=settings.database_pool_size,
)
