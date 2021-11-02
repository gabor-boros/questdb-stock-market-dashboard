from datetime import datetime, timedelta

import dash
import pandas
from dash import dcc, html
from dash.dependencies import Input, Output
from plotly import graph_objects

from app.db import engine
from app.settings import settings

GRAPH_INTERVAL = settings.graph_interval * 1000

TIME_DELTA = 5  # last T hours of data are looked into as per insert time

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

    query = f"quotes WHERE ts BETWEEN '{format_date(start)}' AND '{format_date(end)}'"

    if stock_symbol:
        query += f" AND stock_symbol = '{stock_symbol}' "

    with engine.connect() as conn:
        print(f"SDQ: {query}")
        return pandas.read_sql_query(query, conn)


df = get_stock_data(now() - timedelta(hours=TIME_DELTA), now(), "")

app = dash.Dash(
    __name__,
    title="Real-time stock market changes",
    assets_folder="../assets",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
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
            n_intervals=5,
        ),
    ],
    className="app__container",
)


@app.callback(
    Output("stock-graph", "figure"),
    [Input("stock-symbol", "value"), Input("stock-graph-update", "n_intervals")],
)
def generate_stock_graph(selected_symbol, _):
    data = []
    filtered_df = get_stock_data(now() - timedelta(hours=TIME_DELTA), now(), selected_symbol)
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


@app.callback(
    Output("stock-graph-percent-change", "figure"),
    [
        Input("stock-symbol", "value"),
        Input("stock-graph-update", "n_intervals"),
    ],
)
def generate_stock_graph_percentage(selected_symbol, _):
    data = []
    filtered_df = get_stock_data(now() - timedelta(hours=TIME_DELTA), now(), selected_symbol)
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


if __name__ == "__main__":
    app.run_server(host="0.0.0.0", debug=settings.debug)
