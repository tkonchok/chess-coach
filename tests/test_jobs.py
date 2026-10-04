import os
import signal
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from chess_coach.jobs import Supervisor,terminate_group


class JobTests(unittest.TestCase):
    def supervisor(self):
        value=Supervisor.__new__(Supervisor)
        value.store=Mock()
        value.store.game.return_value={'pgn':'invalid','color':'white'}
        value.engine_path='stockfish';value.timeout=.01;value.process=None
        value.process_lock=threading.Lock();value.stop_event=threading.Event()
        return value

    def test_spawn_failure_and_shutdown_before_spawn_fail_claimed_job(self):
        for stopping in (False,True):
            supervisor=self.supervisor()
            if stopping:supervisor.stop_event.set()
            with patch('chess_coach.jobs.subprocess.Popen',side_effect=OSError('cannot spawn')) as spawn:
                supervisor.run_one({'id':'job','user_id':'u','game_id':'g'})
            supervisor.store.fail.assert_called_once()
            supervisor.store.complete.assert_not_called()
            if stopping:spawn.assert_not_called()

    def test_timeout_terminates_group_and_records_failure(self):
        process=Mock(pid=99999999)
        process.communicate.side_effect=subprocess.TimeoutExpired('worker',.01)
        supervisor=self.supervisor()
        with patch('chess_coach.jobs.subprocess.Popen',return_value=process),patch('chess_coach.jobs.terminate_group') as terminate:
            supervisor.run_one({'id':'job','user_id':'u','game_id':'g'})
        self.assertGreaterEqual(terminate.call_count,1)
        supervisor.store.complete.assert_not_called()
        self.assertIn('four minutes',supervisor.store.fail.call_args.args[1])

    def test_actual_process_group_is_terminated(self):
        process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True)
        try:
            terminate_group(process)
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:process.kill();process.wait()
