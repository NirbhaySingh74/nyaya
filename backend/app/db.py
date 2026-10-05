from functools import lru_cache

from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings


def _configure(conn) -> None:
    register_vector(conn)


@lru_cache
def get_pool() -> ConnectionPool:
    return ConnectionPool(
        get_settings().database_url,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
        configure=_configure,
        open=True,
    )
