"""The TUI application, built with Textual.

Layout:
- JobsScreen (main screen): jobs table at the top, runs of the selected job at the bottom
- LogsScreen: the extracted error of a run, with a toggle to the full log

AWS calls run in "workers" (threads) so the interface never freezes
while waiting on the network.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, RichLog, Static

from lazylake.errors import extract_error
from lazylake.models import JobRun
from lazylake.providers.base import GlueProvider

STATE_STYLE = {
    "SUCCEEDED": "bold green",
    "FAILED": "bold red",
    "ERROR": "bold red",
    "TIMEOUT": "bold magenta",
    "RUNNING": "bold yellow",
    "STARTING": "yellow",
    "STOPPING": "yellow",
    "STOPPED": "dim",
    "NEVER_RUN": "dim",
}


def fmt_state(state: str) -> Text:
    return Text(state, style=STATE_STYLE.get(state, ""))


def fmt_duration(seconds: int) -> str:
    if not seconds:
        return "—"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def fmt_ago(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    minutes = int(delta.total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 48 * 60:
        return f"{minutes // 60} h ago"
    return f"{minutes // 1440} d ago"


def fmt_cost(run: JobRun | None) -> str:
    if run is None or run.estimated_cost_usd is None:
        return "—"
    return f"~${run.estimated_cost_usd:.2f}"


class LogsScreen(Screen):
    """Shows the meaningful error of a run, or the full log with the f key."""

    BINDINGS = [
        Binding("escape,q", "app.pop_screen", "Back"),
        Binding("f", "toggle_full", "Full log / error"),
    ]

    def __init__(self, provider: GlueProvider, run: JobRun):
        super().__init__()
        self.provider = provider
        self.job_run = run
        self.full = False
        self.lines: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="logs-title")
        yield RichLog(id="logs", wrap=True, highlight=True, markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.load_logs()

    @work(thread=True, exclusive=True)
    def load_logs(self) -> None:
        lines = self.provider.get_logs(self.job_run, errors_only=True)
        self.app.call_from_thread(self._show, lines)

    def _show(self, lines: list[str]) -> None:
        self.lines = lines
        self.render_logs()

    def render_logs(self) -> None:
        title = self.query_one("#logs-title", Static)
        log = self.query_one("#logs", RichLog)
        log.clear()
        mode = "full log" if self.full else "extracted error"
        title.update(f" {self.job_run.job_name} · {self.job_run.run_id} · {self.job_run.state} · {mode}")
        if self.job_run.error_message and not self.full:
            log.write(Text("Glue message: " + self.job_run.error_message, style="bold red"))
            log.write("")
        shown = self.lines if self.full else extract_error(self.lines)
        if not shown:
            log.write(Text("No error detected in this run's logs.", style="green"))
        for line in shown:
            log.write(line)

    def action_toggle_full(self) -> None:
        self.full = not self.full
        self.render_logs()


class JobsScreen(Screen):
    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("l", "logs", "Run logs"),
        Binding("tab", "focus_next", "Switch panel", show=False),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self, provider: GlueProvider):
        super().__init__()
        self.provider = provider
        self.runs: dict[str, JobRun] = {}
        self.current_job: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static(" Glue jobs", classes="panel-title")
            yield DataTable(id="jobs", cursor_type="row", zebra_stripes=True)
            yield Static(" Runs of the selected job  (Enter or l = logs)", classes="panel-title")
            yield DataTable(id="runs", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        self.app.sub_title = self.provider.label
        jobs = self.query_one("#jobs", DataTable)
        jobs.add_columns("Job", "Last status", "Started", "Duration", "Est. cost", "Workers")
        runs = self.query_one("#runs", DataTable)
        runs.add_columns("Run ID", "Status", "Started", "Duration", "Est. cost", "Error")
        self.action_refresh()

    # --- Data loading (in threads) ---------------------------------------------
    @work(thread=True, exclusive=True, group="jobs")
    def load_jobs(self) -> None:
        try:
            jobs = self.provider.list_jobs()
        except Exception as exc:  # credential, network, IAM permission errors…
            self.app.call_from_thread(self.notify, f"AWS error: {exc}", severity="error", timeout=10)
            return
        self.app.call_from_thread(self._fill_jobs, jobs)

    @work(thread=True, exclusive=True, group="runs")
    def load_runs(self, job_name: str) -> None:
        try:
            runs = self.provider.list_runs(job_name)
        except Exception as exc:
            self.app.call_from_thread(self.notify, f"AWS error: {exc}", severity="error")
            return
        self.app.call_from_thread(self._fill_runs, job_name, runs)

    # --- Filling the tables -----------------------------------------------------
    def _fill_jobs(self, jobs) -> None:
        table = self.query_one("#jobs", DataTable)
        table.clear()
        for job in jobs:
            run = job.last_run
            workers = f"{job.number_of_workers}× {job.worker_type}" if job.worker_type else "—"
            table.add_row(
                job.name,
                fmt_state(job.last_state),
                fmt_ago(run.started_on if run else None),
                fmt_duration(run.execution_time_s if run else 0),
                fmt_cost(run),
                workers,
                key=job.name,
            )
        failed = sum(1 for j in jobs if j.last_state in ("FAILED", "TIMEOUT", "ERROR"))
        msg = f"{len(jobs)} jobs loaded"
        if failed:
            msg += f" · {failed} failed"
        self.notify(msg, severity="warning" if failed else "information")
        if jobs:
            table.focus()

    def _fill_runs(self, job_name: str, runs: list[JobRun]) -> None:
        if job_name != self.current_job:
            return  # the user has already moved to another job
        table = self.query_one("#runs", DataTable)
        table.clear()
        self.runs = {}
        for run in runs:
            self.runs[run.run_id] = run
            error = (run.error_message or "")[:80]
            table.add_row(
                run.run_id,
                fmt_state(run.state),
                fmt_ago(run.started_on),
                fmt_duration(run.execution_time_s),
                fmt_cost(run),
                error,
                key=run.run_id,
            )

    # --- Events and actions -----------------------------------------------------
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "jobs" and event.row_key is not None:
            self.current_job = event.row_key.value
            self.load_runs(self.current_job)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "jobs":
            self.query_one("#runs", DataTable).focus()
        else:
            self.action_logs()

    def selected_run(self) -> JobRun | None:
        table = self.query_one("#runs", DataTable)
        if table.row_count == 0:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        return self.runs.get(key)

    def action_refresh(self) -> None:
        self.load_jobs()

    def action_logs(self) -> None:
        run = self.selected_run()
        if run is None:
            self.notify("No run to display for this job.", severity="warning")
            return
        self.app.push_screen(LogsScreen(self.provider, run))


class LazylakeApp(App):
    TITLE = "lazylake"
    CSS = """
    .panel-title { background: $boost; color: $text; text-style: bold; height: 1; }
    #jobs { height: 1fr; }
    #runs { height: 1fr; }
    #logs-title { background: $boost; text-style: bold; height: 1; }
    """

    def __init__(self, provider: GlueProvider):
        super().__init__()
        self.provider = provider

    def on_mount(self) -> None:
        self.push_screen(JobsScreen(self.provider))
