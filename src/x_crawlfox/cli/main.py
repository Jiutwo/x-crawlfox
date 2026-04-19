import sys
import typer
from loguru import logger

from .config import ConfigManager, config_manager
from .x_commands import x_app
from .se_commands import se_app

app = typer.Typer(help="x-crawlfox: A multi-platform web scraping CLI tool")
app.add_typer(x_app, name="x")
app.add_typer(se_app, name="se")


@app.callback()
def _global_init(ctx: typer.Context):
    """x-crawlfox global initialization"""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config_manager


@app.command()
def init(
    ctx: typer.Context,
    global_mode: bool = typer.Option(False, "--global", help="Initialize globally in ~/.x-crawlfox/ instead of current directory"),
):
    """
    Initialize X-CrawlFox environment and generate default config file.
    """
    config: ConfigManager = ctx.obj["config"]
    base_dir = config.init_config(global_mode=global_mode)
    logger.info(f"[x-crawlfox] Configuration initialized successfully! Saved in {base_dir}")


def cli():
    try:
        app()
    except KeyboardInterrupt:
        logger.warning("Operation aborted by user.")
        sys.exit(0)


if __name__ == "__main__":
    cli()
