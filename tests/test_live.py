import threading
import unittest
from unittest.mock import Mock, patch
import subprocess
import chess
import chess.engine
from chess_coach.live import evaluate, replay_moves, terminal_result
from chess_coach.jobs import Supervisor
from chess_coach.storage import Conflict


class LiveTests(unittest.TestCase):
    def test_score_stays_white_perspective_on_both_turns(self):
        cases=[(chess.Board(),'d2d4',chess.engine.PovScore(chess.engine.Cp(150),chess.WHITE)),
               (chess.Board(),'d2d4',chess.engine.PovScore(chess.engine.Cp(-150),chess.WHITE))]
        black,_=replay_moves(chess.Board(),['e2e4'])
        cases.append((black,'c7c5',chess.engine.PovScore(chess.engine.Cp(-150),chess.BLACK)))
        for board,move,score in cases:
            engine=Mock()
            engine.analyse.return_value={'score':score,'pv':[chess.Move.from_uci(move)],'depth':12}
            result=evaluate(engine,board)
            self.assertEqual(result['centipawns'],score.pov(chess.WHITE).score())
            self.assertEqual(result['best_move_uci'],move)
            self.assertEqual(result['fen'],board.fen())
            self.assertEqual(engine.analyse.call_args.args[1].nodes,25000)

    def test_mate_draw_and_illegal_evidence(self):
        engine=Mock()
        engine.analyse.return_value={'score':chess.engine.PovScore(chess.engine.Mate(3),chess.WHITE),
                                    'pv':[chess.Move.from_uci('e2e4')]}
        self.assertEqual(evaluate(engine,chess.Board())['mate'],3)
        board=chess.Board('7k/8/8/8/8/8/8/7K w - - 0 1')
        self.assertEqual(terminal_result(board)['terminal'],'1/2-1/2')
        engine.analyse.return_value['pv']=[chess.Move.from_uci('e2e5')]
        with self.assertRaises(ValueError):evaluate(engine,chess.Board())
        with self.assertRaises(ValueError):replay_moves(chess.Board(),['e2e5'])

    def supervisor(self):
        value=Supervisor.__new__(Supervisor)
        value.engine_lock=threading.Lock();value.process_lock=threading.Lock()
        value.stop_event=threading.Event();value.process=None;value.engine_path='stockfish'
        return value

    def test_busy_engine_does_not_spawn_or_consume_allowance(self):
        supervisor=self.supervisor();supervisor.engine_lock.acquire()
        reserve=Mock()
        with patch('chess_coach.jobs.subprocess.Popen') as spawn, self.assertRaisesRegex(RuntimeError,'busy'):
            supervisor.explore(chess.STARTING_FEN,reserve)
        reserve.assert_not_called();spawn.assert_not_called()

    def test_timeout_cleans_group_and_releases_slot(self):
        supervisor=self.supervisor();process=Mock(pid=99999999)
        process.communicate.side_effect=subprocess.TimeoutExpired('worker',5)
        with patch('chess_coach.jobs.subprocess.Popen',return_value=process), patch('chess_coach.jobs.terminate_group') as cleanup:
            with self.assertRaisesRegex(RuntimeError,'timed out'):supervisor.explore(chess.STARTING_FEN,Mock())
        cleanup.assert_called_once_with(process)
        self.assertTrue(supervisor.engine_lock.acquire(blocking=False))
        self.assertIsNone(supervisor.process)

    def test_exhausted_allowance_keeps_specific_error_and_releases_slot(self):
        supervisor=self.supervisor()
        with patch('chess_coach.jobs.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(Conflict,'Daily allowance'):
                supervisor.explore(chess.STARTING_FEN,Mock(side_effect=Conflict('Daily allowance exhausted')))
        spawn.assert_not_called()
        self.assertTrue(supervisor.engine_lock.acquire(blocking=False))

    def test_walkthrough_uses_same_slot_with_twelve_second_deadline(self):
        supervisor=self.supervisor();process=Mock(pid=99999999,returncode=0)
        process.communicate.return_value=('{}','')
        with patch('chess_coach.jobs.subprocess.Popen',return_value=process),patch('chess_coach.jobs.terminate_group'):
            supervisor.walkthrough(chess.STARTING_FEN,'e2e4','d2d4',Mock())
        self.assertEqual(process.communicate.call_args.kwargs['timeout'],12)
        self.assertIn('walkthrough',process.communicate.call_args.args[0])
        self.assertTrue(supervisor.engine_lock.acquire(blocking=False))
