from typing import List
from pydantic import BaseSettings


class Settings(BaseSettings):
    """
    Settings of the application, used by workers and dashboard.
    """

    # Celery settings
    celery_broker: str = "redis://redis:6379/0"

    # Database settings
    database_url: str = "postgresql://admin:quest@questdb:8812/qdb"
    database_pool_size: int = 3

    # Finnhub settings
    api_key: str = ""
    frequency: int = 5  # default stock data fetch frequency in seconds
    symbols: List[str] = list()

    # Dash/Plotly
    debug: bool = True
    graph_interval: int = 10

    class Config:
        """
        Meta configuration of the settings parser.
        """

        # Prefix the environment variable not to mix up with other variables
        # used by the OS or other software.
        env_prefix = "SMD_"  # SMD stands for Stock Market Dashboard
        env_file = ".env"


settings = Settings()
