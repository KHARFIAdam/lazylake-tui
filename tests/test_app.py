"""Interface tests: Textual lets us "drive" the app without a real terminal."""

from lazylake.app import JobsScreen, LazylakeApp, LogsScreen
from lazylake.providers.demo import DemoGlueProvider


async def test_jobs_screen_loads_and_opens_logs():
    app = LazylakeApp(DemoGlueProvider())
    async with app.run_test(size=(140, 40)) as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, JobsScreen)
        jobs = screen.query_one("#jobs")
        assert jobs.row_count == 5

        # The first job (clickstream_compaction) is selected: its runs are loaded
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert screen.query_one("#runs").row_count == 2

        # Move down to orders_daily (last run failed) and open the logs
        for _ in range(4):
            await pilot.press("down")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert screen.current_job == "orders_daily"
        await pilot.press("l")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert isinstance(app.screen, LogsScreen)
        assert app.screen.job_run.state == "FAILED"

        await pilot.press("f")  # toggle the full log
        assert app.screen.full is True
        await pilot.press("escape")
        assert isinstance(app.screen, JobsScreen)
