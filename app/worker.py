import finnhub
from celery import Celery
from sqlalchemy import text
from app.db import engine
from app.settings import settings

client = finnhub.Client(api_key=settings.api_key)
celery_app = Celery(broker=settings.celery_broker)


# worker is started from the root of the project, command line:
# python -m celery --app app.worker.celery_app worker --beat -l info -c 1
#
# worker relies on this table to exist:
#
# https://questdb.io/docs/reference/sql/create-table/#symbol
# CREATE TABLE
#      quotes(stock_symbol SYMBOL CAPACITY 5 CACHE INDEX, -- we are in fact just checking 3
#             current_price DOUBLE,
#             high_price DOUBLE,
#             low_price DOUBLE,
#             open_price DOUBLE,
#             percent_change DOUBLE,
#             tradets TIMESTAMP, -- timestamp of the trade
#             ts TIMESTAMP)      -- time of insert in our table
#      timestamp(ts)
#  PARTITION BY DAY;


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
    # https://finnhub.io/docs/api/quote
    #  quote = {
    #      'c': 148.96,
    #      'd': -0.84,
    #      'dp': -0.5607,
    #      'h': 149.7,
    #      'l': 147.8,
    #      'o': 148.985,
    #      'pc': 149.8,
    #      't': 1635796803
    #  }
    # c: Current price
    # d: Change
    # dp: Percent change
    # h: High price of the day
    # l: Low price of the day
    # o: Open price of the day
    # pc: Previous close price
    # t: when it was traded

    # I wonder if these inserts could be batched
    query = f"""
    INSERT INTO quotes(stock_symbol, current_price, high_price, low_price, open_price, percent_change, tradets, ts)
    VALUES(
        '{symbol}',
        {quote["c"]},
        {quote["h"]},
        {quote["l"]},
        {quote["o"]},
        {quote["pc"]},
        {quote["t"]} * 1000000,
        systimestamp()
    );
    """

    with engine.connect() as conn:
        conn.execute(text(query))
