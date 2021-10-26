# Real-time stock streaming dashboard with QuestDB and Plotly

We are working with a lot of numbers and data every day. As understanding the raw data is challenging sometimes, the most common thing we do is create charts and graphs from it. 

## What we will build

In this tutorial, we are going to create a real-time streaming dashboard using QuestDB, Celery, Redis, Plotly, and Dash. It will be a fun project with awesome visualizations.

### What are Plotly and Dash

Plotly is "the front end for ML and data science models", as the company defines its product, and this describes it really well.

With Plotly and, its "app framework", Dash, we can create web applications in a fast and efficient way. Dash abstracts away the boilerplate needed to set up a web server and several handlers for it. 

### Project structure

The project will build up from two parts:

- a backend that periodically fetches user-defined stock data from [Finnhub](https://finnhub.io/), and
- a front-end that utilizes Plotly and Dash to visualize the gathered data on interactive charts

For this tutorial, you will need some experience in Python and basic SQL knowledge. To periodically fetch data, we will use Celery backed by Redis as the message broker and QuestDB as storage.

Let's see the prerequisites and jump right in!

### Prerequisites

- Python 3.8
- Docker
- Docker Compose
- Finnhub account and sandbox API key

## Environment setup

### Create a new project

First of all, we are going to create an empty directory. That will be the project root. Create the following project structure:

```shell
streaming-dashboard (project root)
└── app (this directory will contain our application)
```

### Installing QuestDB & Redis

To install the services required for our project, we are using Docker and Docker Compose to avoid polluting our host machine.

Within the project root, let's create a file, called `docker-compose.yml`. This file describes all the necessary requirements the project will use; later on we will extend this file with other services too.

```yaml
version: '3'

volumes:
  questdb_data: {}

services:
  redis:
    image: 'redis:latest'
    ports:
      - '6379:6379'

  questdb:
    image: 'questdb/questdb:latest'
    volumes:
      - questdb_data:/root/.questdb/db
    ports:
      - '9000:9000'
      - '8812:8812'
```

Here we go! When you run `docker-compose up`, QuestDB and Redis will fire up. After starting the services, we can access QuestDB's interactive console on [http://127.0.0.1:9000](http://127.0.0.1:9000/).

### Create the database table

Although we could create the database table later, since we already started QuestDB, we are going to take this chance and create the table now.

Connect to QuestDB's interactive console, and run the following SQL statement:

```sql
CREATE TABLE
    quotes(stock_symbol STRING, current_price DOUBLE, high_price DOUBLE, low_price DOUBLE, open_price DOUBLE, percent_change DOUBLE, ts TIMESTAMP)
    timestamp(ts);
```

After executing the command, we will see a success message in the bottom left corner, confirming that the table creation was successful and the table appears on the right-hand side's table list view.

![img](https://www.gaboros.hu/content/images/2021/10/Screenshot-2021-10-26-at-17.15.22.png)

Voilá! The table is ready for use.

## Create workers

### Define Python dependencies

As mentioned, our project will have two pieces. For now, let's focus on the periodic jobs that will fetch the data from Finnhub.

As in the case of every standard Python project, we are using `requirements.txt` to define the dependencies the project will use. Place the `requirements.txt` in your project root with the content below:

```
finnhub-python==2.4.5   # The official Finnhub Python client 
pydantic==1.8.2        # We will use Pydantic to create data models
celery[redis]==5.1.2   # Celery will be the periodic task executor
psycopg2==2.9.1        # We are using QuestDB's PostgreSQL connector
sqlalchemy==1.4.2      # SQLAlchemy will help us executing SQL queries
dash==2.0.0            # Dash is used for building data apps
pandas==1.3.4          # Pandas will handle the data frames from QuestDB
plotly==5.3.1          # Plotly will help us with beautiful charts
```

We can split the requirements into two logical groups:

1. those requirements that are needed for fetching the data, and
2. the requirements needed to visualize it

For the sake of simplicity, we did not create two separate requirements files, though in a production environment we would do.

Create a virtualenv and install the dependencies by executing:

```shell
$ virtualenv -p python3.8 virtualenv
$ source virtualenv/bin/activate
$ pip install -r requirements.txt
```

### Setting up the DB connection

Since the periodic tasks would need to store the fetched quotes, we need to connect to QuestDB. Therefore, we create a new file in the `app` package, called `db.py`. This file contains the `SQLAlchemy` engine that will serve as the base for our connections.

```python
from sqlalchemy import create_engine

from app.settings import settings

engine = create_engine(
    settings.database_url, pool_size=settings.database_pool_size, pool_pre_ping=True
)
```

### Define the worker settings

Before we jump right into the implementation, first we must configure Celery.

To create a configuration used by both the workers and the dashboard, create a `settings.py` file in the `app` package. We will use `pydantic`'s `BaseSettings` to define the configuration. This helps us to read the settings from a `.env` file, environment variable and prefix them if needed.

Ensuring that we do not overwrite any other environment variables, we will set the prefix to `SMD` that stands for "stock market dashboard", our application. Below you can see the settings file:

```python
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
    debug: bool = False
    graph_interval: int = 10

    class Config:
        """
        Meta configuration of the settings parser.
        """

        # Prefix the environment variable not to mix up with other variables
        # used by the OS or other software.
        env_prefix = "SMD_"  # SMD stands for Stock Market Dashboard


settings = Settings()
```

In the settings, you can notice we already defined the `celery_broker` and `database_url` settings with unusual default values. The hostnames are the name of the containers we defined in `docker-compose.yml`. This is not a typo nor a coincidence. As the linked container's names are available as hostnames within the containers, we can use that to connect to the desired services.

Some bits are missing at the moment. We still have to define the correct settings and run the worker in a Docker container. Get started with the settings!

To keep our environment separated, we will use a `.env` file. One of `pydantic` based settings' biggest advantage is that it can read environment variables from `.env` files. 

Let's create a `.env` file in the project root, next to `docker-compose.yml`:

```
SMD_API_KEY = "<YOUR SANDBOX API KEY>"
SMD_FREQUENCY = 10
SMD_SYMBOLS = ["AAPL","DOCN","EBAY"]
```

As you may assume, you will need to get your API key for the sandbox environment at this step. To retrieve the key, the only thing you have to do is sign up to Finnhub, and your API key will appear on the dashboard after login.

![img](https://www.gaboros.hu/content/images/2021/10/Screenshot-2021-10-26-at-17.28.44.png)

### Create the periodic task

Now, that we discussed the settings file, in the `app` package, create a new `worker.py` which will contain the Celery and beat schedule configuration:

```python
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
```

Review the code above together and discuss what `worker.py` does.

```python
import finnhub
from celery import Celery
from sqlalchemy import text

from app.db import engine
from app.settings import settings

# [...]
```

In the first few lines, we import the requirements that are needed to fetch and store the data.

After importing the requirements, we configure the Finnhub client and Celery to use the Redis broker we defined in the application settings.

```python
# [...]

client = finnhub.Client(api_key=settings.api_key)
celery_app = Celery(broker=settings.celery_broker)

# [...]
```

To fetch the data periodically per stock symbol, we need to programmatically create a periodic task for every symbol we defined in the settings.

```python
# [...]

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Setup a periodic task for every symbol defined in the settings.
    """
    for symbol in settings.symbols:
        sender.add_periodic_task(settings.frequency, fetch.s(symbol))
        
# [...]
```

The snippet above will register a new periodic per stock symbol after Celery is connected to the broker.

The last step is to define the `fetch` task that does the majority of the work.

```python
# [...]

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
```

Using the Finnhub `client` we get a quote for the given symbol. After the quote is retrieved successfully, we prepare an SQL query to insert the quote into the database. At the end of the function, as the last step, we open a connection to QuestDB and insert the new quote.

Congratulations! The worker is ready for use, let's try it out!

Execute the command below and wait some seconds to let Celery kick in:

Soon, you will see that the tasks are scheduled and the database is slowly filling.

### A check-in

Before going on, let's check what we have by now:

1. we created the project root
2. a `docker-compose.yml` file to manage related services
3. `app/settings.py` that handles our application configuration
4. `app/db.py` configuring the database engine, and
5. last, but not least `app/worker.py` that handles the hard work, fetches, and stores the data.

At this point, we should have the following project structure:

```
├── app
│   ├── __init__.py
│   ├── db.py
│   ├── settings.py
│   └── worker.py
├── docker-compose.yml
```

## Visualize the data with Plotly and Dash

### Getting static assets

This tutorial is not about writing the necessary style sheets or collecting static assets. Hence you only need to copy-paste the following code.

As the first step, create an `assets` directory next to the `app` package with the structure below:

```
├── app
│   ├── __init__.py
│   ├── db.py
│   ├── settings.py
│   └── worker.py
├── assets
│   └── style.css
├── docker-compose.yml
```

The `style.css` will define the styling for our application. As mentioned above, Dash will save us from boilerplate code, so the `assets` directory will be used by default in conjunction with the stylesheet in it.

Copy-paste the following code to `style.css`:

```css
html {
    font-size: 62.5%;
}

body {
    font-size: 1.5em;
    line-height: 1.6;
    font-weight: 400;
    font-family: "Open Sans", "HelveticaNeue", "Helvetica Neue", Helvetica, Arial, sans-serif;
    color: rgb(50, 50, 50);
    background-color: #21222c;
}

h1, h2, h3, h4, h5, h6 {
    margin-top: 0;
    margin-bottom: 0;
    font-weight: 300;
}

h1 {
    font-size: 4.5rem;
    line-height: 1.2;
    letter-spacing: -.1rem;
    margin-bottom: 2rem;
}

h2 {
    font-size: 3.6rem;
    line-height: 1.25;
    letter-spacing: -.1rem;
    margin-bottom: 1.8rem;
    margin-top: 1.8rem;
}

h3 {
    font-size: 3.0rem;
    line-height: 1.3;
    letter-spacing: -.1rem;
    margin-bottom: 1.5rem;
    margin-top: 1.5rem;
}

h4 {
    font-size: 2.6rem;
    line-height: 1.35;
    letter-spacing: -.08rem;
    margin-bottom: 1.2rem;
    margin-top: 1.2rem;
}

h5 {
    font-size: 2.2rem;
    line-height: 1.5;
    letter-spacing: -.05rem;
    margin-bottom: 0.6rem;
    margin-top: 0.6rem;
}

h6 {
    font-size: 2.0rem;
    line-height: 1.6;
    letter-spacing: 0;
    margin-bottom: 0.75rem;
    margin-top: 0.75rem;
}

p {
    margin-top: 0;
}

#stock-symbol {
    color: #aaaaaa !important;
}

.column {
    width: 100%;
    float: left;
    box-sizing: border-box;
    margin-left: 4%;
}

.column:first-child {
    margin-left: 0;
}

.one-half.column {
    width: 48%;
}

.Select--single > .Select-control {
    background-color: #282a36;
    border: none;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24);
}

.Select--single > .Select-control .Select-value .Select-value-label {
    color: #aaaaaa !important;
}

.Select-menu-outer {
    color: #282a36;
}

.app__container {
    margin: 3% 5%;
}

.app__header {
    display: flex;
    justify-content: space-between;
    color: #fff;
    margin-bottom: 4rem;
}

.app__header__title {
    letter-spacing: 0.23rem;
}

.app__selector {
    width: 48%;
}

.app__selector p {
    color: #fafafa;
}

.app__content {
    display: flex;
    margin-top: 20px;
}

.graph__title {
    background-color: #282a36;
    color: #fff !important;
    letter-spacing: 0.3rem !important;
    padding: 25px 25px 0px 25px;
    margin-bottom: 0px !important;
    font-size: 1em;
}
```

### Setting up the application

This is the most interesting part of the tutorial. We are going to visualize the data we collect.

Create a `main.py` file in the `app` package, and let's begin with the imports:

```python
from datetime import datetime, timedelta

import dash
import pandas
from dash import dcc, html
from dash.dependencies import Input, Output
from plotly import graph_objects

from app.db import engine
from app.settings import settings

# [...]
```

After having the imports in place, we are defining some helper functions and constants.

```python
# [...]

GRAPH_INTERVAL = settings.graph_interval * 1000

COLORS = [
    "#1e88e5",
    "#7cb342",
    "#fbc02d",
    "#ab47bc",
    "#26a69a",
    "#5d8aa8",
]


def now() -> datetime:
    return datetime.utcnow()


def get_stock_data(start: datetime, end: datetime, stock_symbol: str):
    def format_date(dt: datetime) -> str:
        return dt.isoformat(timespec="microseconds") + "Z"

    query = f"SELECT * FROM quotes WHERE ts >= '{format_date(start)}' AND ts <= '{format_date(end)}'"

    if stock_symbol:
        query += f" AND stock_symbol = '{stock_symbol}' "

    with engine.connect() as conn:
        return pandas.read_sql_query(query, conn)

# [...]
```

In the first few lines, we define constants for setting a graph update frequency (`GRAPH_INTERVAL`) and colors that will be used for coloring the graph (`COLORS`).

After that, we define two helper functions, `now` and `get_stock_data`. While `now` is responsible only for getting the current time in UTC (as Finnhub returns the date in UTC too), the `get_stock_data` does more. It is the core of our front-end application, it fetches the stock data from QuestDB that workers inserted.

Now, define the initial data frame and the application:

```python
# [...]

df = get_stock_data(now() - timedelta(hours=5), now(), "")

app = dash.Dash(
    __name__,
    title="Real-time stock market changes",
    assets_folder="../assets",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

# [...]
```

As you can see above, the initial data frame (`df`) will contain the latest 5 hours of data we have. This is needed to pre-populate the application with some data we have.

The application definition `app` describes the application's title, asset folder, and some HTML meta tags used during rendering.

Create the application layout that will be rendered as HTML. As you may assume, we won't write HTML code, though we will use Dash's helpers for that:

```python
# [...]

app.layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Stock market changes", className="app__header__title"),
                        html.P(
                            "Continually query QuestDB and display live changes of the specified stocks.",
                            className="app__header__subtitle",
                        ),
                    ],
                    className="app__header__desc",
                ),
            ],
            className="app__header",
        ),
        html.Div(
            [
                html.P("Select a stock symbol"),
                dcc.Dropdown(
                    id="stock-symbol",
                    searchable=True,
                    options=[
                        {"label": symbol, "value": symbol}
                        for symbol in df["stock_symbol"].unique()
                    ],
                ),
            ],
            className="app__selector",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [html.H6("Current price changes", className="graph__title")]
                        ),
                        dcc.Graph(id="stock-graph"),
                    ],
                    className="one-half column",
                ),
                html.Div(
                    [
                        html.Div(
                            [html.H6("Percent changes", className="graph__title")]
                        ),
                        dcc.Graph(id="stock-graph-percent-change"),
                    ],
                    className="one-half column",
                ),
            ],
            className="app__content",
        ),
        dcc.Interval(
            id="stock-graph-update",
            interval=int(GRAPH_INTERVAL),
            n_intervals=0,
        ),
    ],
    className="app__container",
)

# [...]
```

This snippet is a bit longer, though it has only one interesting part, `dcc.Interval`. The interval is used to set up periodic graph refresh.

We are close to the end of this tutorial, hold on!

Now, we are going to define two callbacks that will listen to input changes and the interval discussed above. The first callback is for generating the graph data and rendering the lines per stock symbol.

```python
# [...]

@app.callback(
    Output("stock-graph", "figure"),
    [Input("stock-symbol", "value"), Input("stock-graph-update", "n_intervals")],
)
def generate_stock_graph(selected_symbol, _):
    data = []
    filtered_df = get_stock_data(now() - timedelta(hours=5), now(), selected_symbol)
    groups = filtered_df.groupby(by="stock_symbol")

    for group, data_frame in groups:
        data_frame = data_frame.sort_values(by=["ts"])
        trace = graph_objects.Scatter(
            x=data_frame.ts.tolist(),
            y=data_frame.current_price.tolist(),
            marker=dict(color=COLORS[len(data)]),
            name=group,
        )
        data.append(trace)

    layout = graph_objects.Layout(
        xaxis={"title": "Time"},
        yaxis={"title": "Price"},
        margin={"l": 70, "b": 70, "t": 70, "r": 70},
        hovermode="closest",
        plot_bgcolor="#282a36",
        paper_bgcolor="#282a36",
        font={"color": "#aaa"},
    )

    figure = graph_objects.Figure(data=data, layout=layout)
    return figure
    
# [...]
```

The other callback is very similar to the previous one, it will be responsible for updating the percentage change representation of the stocks or a given stock.

```python
# [...]

@app.callback(
    Output("stock-graph-percent-change", "figure"),
    [
        Input("stock-symbol", "value"),
        Input("stock-graph-update", "n_intervals"),
    ],
)
def generate_stock_graph_percentage(selected_symbol, _):
    data = []
    filtered_df = get_stock_data(now() - timedelta(hours=5), now(), selected_symbol)
    groups = filtered_df.groupby(by="stock_symbol")

    for group, data_frame in groups:
        data_frame = data_frame.sort_values(by=["ts"])
        trace = graph_objects.Scatter(
            x=data_frame.ts.tolist(),
            y=data_frame.percent_change.tolist(),
            marker=dict(color=COLORS[len(data)]),
            name=group,
        )
        data.append(trace)

    layout = graph_objects.Layout(
        xaxis={"title": "Time"},
        yaxis={"title": "Percent change"},
        margin={"l": 70, "b": 70, "t": 70, "r": 70},
        hovermode="closest",
        plot_bgcolor="#282a36",
        paper_bgcolor="#282a36",
        font={"color": "#aaa"},
    )

    figure = graph_objects.Figure(data=data, layout=layout)
    return figure
    
# [...]
```

The last pice is to call `run_server` on the `app` object when the script is called from the CLI. 

```python
# [...]

if __name__ == "__main__":
    app.run_server(host="0.0.0.0", debug=settings.debug)
```

We are done! As every piece took its place, we can try our application with real data. Make sure that the Docker containers are started and execute `PYTHONPATH=. python app/main.py` from the project root:

```shell
$ PYTHONPATH=. python app/main.py

Dash is running on http://0.0.0.0:8050/

 * Tip: There are .env or .flaskenv files present. Do "pip install python-dotenv" to use them.
 * Serving Flask app 'main' (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
 * Running on all addresses.
   WARNING: This is a development server. Do not use it in a production deployment.
 * Running on http://192.168.0.14:8050/ (Press CTRL+C to quit)
```

Navigate to http://127.0.0.1:8050/, to see the application in action.

![img](https://www.gaboros.hu/content/images/2021/10/Screenshot-2021-10-26-at-18.37.27.png)

To select only one stock, in the dropdown field choose the desired stock symbol and let the application refresh.

![img](https://www.gaboros.hu/content/images/2021/10/Screenshot-2021-10-26-at-18.37.35.png)

## Summary

In this tutorial, we've learned how to write periodic tasks in Python, store data in QuestDB, and create beautiful dashboards using Plotly and Dash. Although we won't start trading just right now, this tutorial demonstrated well how to combine these separately powerful tools and software to create something bigger and more useful.

Thank you for your attention!

*The source code is available at* https://github.com/gabor-boros/questdb-stock-market-dashboard.
