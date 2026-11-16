"""App memory commands (artemis app-memory)."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from artemis.app_memory.harvester import Harvester
from artemis.app_memory.service import DB_FILE, excluded_packages
from artemis.app_memory.store import MapStore
from artemis.app_memory.trace_reader import DATA_ENGINE_DB, TraceReader
from artemis.config import settings
from artemis.config.agent import load_agent_config

app_memory_app = typer.Typer(help="Inspect and backfill the per-app maps learned from runs.")

TracesPath = Annotated[
    Path | None, typer.Option("--path", "-p", help="Custom traces directory path.")
]


@app_memory_app.command("backfill")
def backfill(
    session: Annotated[str | None, typer.Option("--session", help="Harvest one session.")] = None,
    all_sessions: Annotated[bool, typer.Option("--all", help="Harvest every session.")] = False,
    traces_path: TracesPath = None,
) -> None:
    """Harvest sessions already recorded in data_engine.db. Safe to run repeatedly."""
    if (session is not None) == all_sessions:
        typer.secho("Pass exactly one of --session ID or --all.", fg=typer.colors.RED)
        raise typer.Exit(2)
    base_dir = traces_path or settings.TRACES_PATH
    if not (base_dir / DATA_ENGINE_DB).exists():
        typer.secho(f"No recorded sessions at: {base_dir}", fg=typer.colors.YELLOW)
        raise typer.Exit(1)
    reader = TraceReader.open(base_dir)
    known = reader.session_ids()
    if session is not None and session not in known:
        typer.secho(f"Session '{session}' not found in {base_dir}", fg=typer.colors.RED)
        raise typer.Exit(1)
    table = Table(title="App memory backfill")
    table.add_column("Session", style="cyan")
    table.add_column("Result", style="green")
    store = MapStore.open(base_dir / DB_FILE)
    try:
        excluded = excluded_packages(load_agent_config().app_memory)
        harvester = Harvester(store, reader, excluded)
        for session_id in [session] if session is not None else known:
            outcome = harvester.backfill(session_id)
            table.add_row(session_id, outcome.value if outcome else "running: left live")
    finally:
        store.close()
    Console().print(table)


@app_memory_app.command("stats")
def stats(traces_path: TracesPath = None) -> None:
    """Print states, edges and observations per map."""
    path = (traces_path or settings.TRACES_PATH) / DB_FILE
    if not path.exists():
        typer.secho(f"No app memory at: {path}", fg=typer.colors.YELLOW)
        return
    store = MapStore.open(path)
    try:
        rows = store.map_stats()
    finally:
        store.close()
    table = Table(title=f"App memory maps ({len(rows)} total)")
    table.add_column("Package", style="cyan")
    for column in ("Version", "States", "Edges", "Confirmed", "Discounted", "Provisional"):
        table.add_column(column, justify="right")
    for row in rows:
        counts = (row.states, row.edges, row.confirmed, row.discounted, row.provisional)
        table.add_row(row.map_id.package, str(row.map_id.version_code), *map(str, counts))
    Console().print(table)
