from dotenv import load_dotenv
import logging
from env import LOG_LEVEL, MATPLOTLIB_COLOR_MODE, PLOTLY_COLOR_MODE
import plotly.graph_objects as go
from textwrap import wrap


load_dotenv()

END = "\033[0m"
BOLD = "\033[1m"
BROWN = "\033[0;33m"
ITALIC = "\033[3m"


def set_logger_level_to_all_local(level: int) -> None:
    """Sets the level of all local loggers to the given level.

    Parameters
    ----------
    level : int, optional
        The level to set the loggers to, by default logging.DEBUG.
    """
    level_to_int_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    if isinstance(level, str):
        level = level_to_int_map[level.lower()]

    for _, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):
            if hasattr(logger, "local"):
                logger.setLevel(level)


def create_simple_logger(
    logger_name: str, level: str = LOG_LEVEL, set_level_to_all_loggers: bool = False
) -> logging.Logger:
    """Creates a simple logger with the given name and level. The logger has a single handler that logs to the console.

    Parameters
    ----------
    logger_name : str
        Name of the logger.
    level : str or int
        Level of the logger. Can be a string or an integer. If a string, it should be one of the following: "debug", "info", "warning", "error", "critical". Default level is read from the environment variable LOG_LEVEL.

    Returns
    -------
    logging.Logger
        The logger object.
    """
    level_to_int_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    if isinstance(level, str):
        level = level_to_int_map[level.lower()]
    logger = logging.getLogger(logger_name)
    logger.local = True
    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # remove any existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    if set_level_to_all_loggers:
        set_logger_level_to_all_local(level)
    return logger


logger = create_simple_logger(__name__)


def set_publish_matplotlib_template(mode: str = MATPLOTLIB_COLOR_MODE) -> None:
    """Sets the matplotlib template for publication-ready plots."""
    import matplotlib.pyplot as plt

    text_color = "black" if mode == "light" else "white"
    background_color = "white" if mode == "light" else "black"
    grid_color = "#948b72" if mode == "light" else "#666666"

    plt.rcParams.update(
        {
            "font.size": 18,
            "axes.labelcolor": text_color,
            "axes.labelsize": 18,
            "axes.labelweight": "bold",
            "xtick.labelsize": 16,
            "ytick.labelsize": 16,
            "xtick.color": text_color,
            "ytick.color": text_color,
            "axes.grid": True,
            "axes.facecolor": background_color,
            "figure.facecolor": background_color,
            "figure.titlesize": 20,
            "figure.titleweight": "bold",
            "grid.color": grid_color,
            "grid.linewidth": 1,
            "grid.linestyle": "--",
            "axes.edgecolor": text_color,
            "axes.linewidth": 0.5,
            "text.color": text_color,
            "legend.framealpha": 0.8,
            "legend.edgecolor": text_color,
            "legend.facecolor": background_color,
            "legend.labelcolor": text_color,
        }
    )
    logger.info(f"Matplotlib template ready for publication {mode} mode.")


def set_publish_plotly_template(mode: str = PLOTLY_COLOR_MODE) -> None:
    """Sets the Plotly template for publication-ready plots with full color handling."""
    import plotly.graph_objects as go
    import plotly.io as pio

    # --- Color configuration ---
    is_light = mode.lower() == "light"
    text_color = "black" if is_light else "white"
    background_color = "white" if is_light else "#111111"
    grid_color = "#e5e5e5" if is_light else "#333333"
    axis_color = "#444444" if is_light else "#cccccc"
    hover_bg = "rgba(255,255,255,0.9)" if is_light else "rgba(30,30,30,0.9)"
    hover_border = "#bbbbbb" if is_light else "#555555"

    # --- Font setup ---
    font_family = "Times New Roman"

    def get_font_dict(size: int, color: str = text_color) -> dict:
        return dict(
            size=size,
            color=color,
            family=font_family,
        )

    # --- Define template layout ---
    layout = go.Layout(
        font=get_font_dict(16),
        title=dict(font=get_font_dict(24)),
        legend=dict(
            font=get_font_dict(18),
            bgcolor=background_color,
            bordercolor=axis_color,
        ),
        margin=dict(l=80, r=20, t=80, b=80),
        xaxis=dict(
            title=dict(font=get_font_dict(18)),
            tickfont=get_font_dict(16),
            showline=True,
            linecolor=axis_color,
            gridcolor=grid_color,
            zeroline=False,
            automargin=True,
            title_standoff=20,  # push x-title away from ticks/labels
        ),
        yaxis=dict(
            title=dict(font=get_font_dict(18)),
            tickfont=get_font_dict(16),
            showline=True,
            linecolor=axis_color,
            gridcolor=grid_color,
            zeroline=False,
            automargin=True,
            title_standoff=20,
        ),
        plot_bgcolor=background_color,
        paper_bgcolor=background_color,
        hoverlabel=dict(
            font=get_font_dict(14),
            bgcolor=hover_bg,
            bordercolor=hover_border,
        ),
    )

    # --- Apply template globally ---
    pio.templates["publish"] = go.layout.Template(layout=layout)
    pio.templates.default = "publish"

    logger.info(f"✅ Plotly template ready for publication ({mode} mode).")


def wrap_label(s, width=12):
    return "<br>".join(wrap(str(s), width=width))


def autoadjust_axes(
    fig: go.Figure,
    xlabels=None,
    ylabels=None,
    wrap_threshold=14,
    wrap_width=12,
    rotate_threshold=8,
    title_wrap_threshold=30,
):
    # --------- TITLE FIX ----------
    if fig.layout.title and fig.layout.title.text:
        title_text = str(fig.layout.title.text)
        if len(title_text) >= title_wrap_threshold:
            wrapped_title = wrap_label(title_text, title_wrap_threshold)
            fig.update_layout(title_text=wrapped_title)

    # --------- X AXIS FIX ----------
    fig.update_xaxes(automargin=True)

    if xlabels:
        max_len = max(len(str(l)) for l in xlabels)
        avg_len = sum(len(str(l)) for l in xlabels) / len(xlabels)

        # Long labels → wrap
        if max_len >= wrap_threshold:
            wrapped = [wrap_label(l, wrap_width) for l in xlabels]
            fig.update_xaxes(ticktext=wrapped, tickvals=xlabels, tickangle=0)
            fig.update_xaxes(title_standoff=30)
            fig.update_layout(margin=dict(b=100))

        # Medium labels → rotate
        elif avg_len >= rotate_threshold:
            fig.update_xaxes(tickangle=45, title_standoff=25)
            fig.update_layout(margin=dict(b=80))

        else:
            fig.update_xaxes(title_standoff=15)

    # --------- Y AXIS FIX ----------
    fig.update_yaxes(automargin=True)

    if ylabels:
        max_len_y = max(len(str(l)) for l in ylabels)

        # Long vertical labels → wrap
        if max_len_y >= wrap_threshold:
            wrapped_y = [wrap_label(l, wrap_width) for l in ylabels]
            fig.update_yaxes(ticktext=wrapped_y, tickvals=ylabels)
            fig.update_yaxes(title_standoff=30)
            fig.update_layout(margin=dict(l=120))

        # Normal Y labels
        else:
            fig.update_yaxes(title_standoff=20)
            # Slight safe margin
            fig.update_layout(margin=dict(l=80))

    return fig
