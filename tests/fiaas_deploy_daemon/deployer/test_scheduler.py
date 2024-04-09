from unittest import mock

import pytest
from k8s.client import ClientError, ServerError
from requests.exceptions import RetryError

from fiaas_deploy_daemon.deployer.scheduler import Scheduler


class TestScheduler:
    @pytest.fixture
    def scheduler(self) -> Scheduler:
        def no_delay(*args, **kwargs):
            pass

        def time_func_factory(*args, **kwargs):
            t = 0
            # scheduler re-adds tasks with a 10s delay if they fail. increasing "time" by 15s every tick should ensure
            # a re-added task is always called on the next iteration
            tick_interval = 15

            def _tick():
                nonlocal t
                t += tick_interval
                return t

            return _tick

        yield Scheduler(time_func=time_func_factory(), delay_func=no_delay)

    def test_scheduler_runs_task(self, scheduler):
        task = mock.MagicMock()
        task.return_value = True

        scheduler.add(task, delay=0)

        scheduler(run_forever=False)

        task.assert_called_once()

    @pytest.mark.parametrize(
        "exception_class",
        (
            ClientError,
            ServerError,
            RetryError,
        ),
    )
    def test_scheduler_handles_exception_raised_by_task(self, scheduler, exception_class):
        raise_error = mock.MagicMock()
        raise_error.side_effect = exception_class("updating ApplicationStatus resource failed")

        scheduler.add(raise_error, delay=0)

        # verify that the exception set up above does not flow out of the scheduler; the test will fail if it does
        scheduler(run_forever=False)

        raise_error.assert_called_once()
