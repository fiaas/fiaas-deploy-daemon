
import mock
import pytest

from fiaas_deploy_daemon import HealthCheck
from fiaas_deploy_daemon.base_thread import DaemonThread

THREADS = ["deployer", "consumer", "scheduler", "crd_watcher", "usage_reporter"]


def _create_mock(failing):
    m = mock.create_autospec(DaemonThread)
    m.is_alive.return_value = not failing
    return m


class TestHealthCheck(object):
    @pytest.mark.parametrize("fails", THREADS)
    def test_one_thread_fails(self, fails):
        threads = (_create_mock(name == fails) for name in THREADS)
        health_check = HealthCheck(*threads)
        assert not health_check.is_healthy()

    @pytest.mark.parametrize("lives", THREADS)
    def test_one_thread_lives(self, lives):
        threads = (_create_mock(name != lives) for name in THREADS)
        health_check = HealthCheck(*threads)
        assert not health_check.is_healthy()

    def test_all_threads_fail(self):
        threads = (_create_mock(True) for _ in THREADS)
        health_check = HealthCheck(*threads)
        assert not health_check.is_healthy()

    def test_all_threads_live(self):
        threads = (_create_mock(False) for _ in THREADS)
        health_check = HealthCheck(*threads)
        assert health_check.is_healthy()
