import finnhub
from celery import Celery
from sqlalchemy import text

from app.db import engine
from app.settings import settings

client = finnhub.Client(api_key=settings.api_key)
celery_app = Celery(broker=settings.celery_broker)


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Setup a periodic task for every symbol defined in the settings.
    """
    for symbol in settings.symbols:
        sender.add_periodic_task(settings.frequency, fetch.s(symbol))


@celery_app.task
def fetch(symbol: str):
    """
    Fetch the stock info for a given symbol from Finnhub and load it into QuestDB.
    """

    quote: dict = client.quote(symbol)

    query = f"""
    INSERT INTO quotes(stock_symbol, current_price, high_price, low_price, open_price, percent_change, ts)
    VALUES(
        '{symbol}',
        {quote["c"]},
        {quote["h"]},
        {quote["l"]},
        {quote["o"]},
        {quote["pc"]},
        cast({quote["t"]} * 1000000L AS TIMESTAMP)
    ) timestamp(ts);
    """

    with engine.connect() as conn:
        conn.execute(text(query))
