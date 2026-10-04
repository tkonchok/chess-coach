from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch
import chess
import chess.engine

from beta_fixtures import snapshot
from chess_coach.analysis import EngineEvaluation, MoveComparison
from chess_coach.exercises import card_from_exercise, digest, eligible, prepare


class ExerciseTests(unittest.TestCase):
    def test_replay_identity_and_tamper_detection(self):
        value = snapshot()
        original = deepcopy(value)
        card = card_from_exercise(value)
        self.assertEqual(card.continuation_san, ('d4','d5'))
        self.assertEqual(value, original)
        value['card']['explanation'] = 'changed'
        with self.assertRaises(ValueError):
            card_from_exercise(value)

    def test_recomputed_digest_cannot_hide_source_mismatch(self):
        value = snapshot()
        value['candidate']['position_fen'] = chess.Board().copy().mirror().fen()
        value['version_id'] = digest({k:v for k,v in value.items() if k != 'version_id'})
        with self.assertRaises(ValueError):
            card_from_exercise(value)

    def test_threshold_and_mate_exclusions(self):
        value = snapshot()['verification']
        self.assertTrue(eligible(value))
        value['evaluation_loss'] = 149
        self.assertFalse(eligible(value))
        value['evaluation_loss'] = 150
        value['best_evaluation']['centipawns'] = -201
        self.assertFalse(eligible(value))
        value['best_evaluation']['centipawns'] = None
        self.assertFalse(eligible(value))

    def prepare_fixture(self, recommended='d4'):
        s = snapshot()
        engine = Mock(id={'name':'Test'})
        engine.analyse.return_value = [{'pv':[chess.Move.from_uci('d2d4'), chess.Move.from_uci('d7d5')],
                                        'score':chess.engine.PovScore(chess.engine.Cp(200),chess.WHITE)}]
        verified = MoveComparison(chess.STARTING_FEN,'e4',recommended,
                                  EngineEvaluation(200,None,200),EngineEvaluation(0,None,0),200)
        report = {'source':s['source'],'engine':{},'created_at':s['analysis_created_at'],'candidates':[s['candidate']]}
        with patch('chess_coach.exercises.analyze_pgn',return_value=report), patch('chess_coach.exercises.compare_move',return_value=verified) as compare:
            result = prepare(engine,s['source']['pgn'],'white')
        return result,compare

    def test_stable_candidate_contains_both_searches_and_legal_line(self):
        result,compare = self.prepare_fixture()
        self.assertEqual(len(result['exercises']),1)
        self.assertEqual(compare.call_args.kwargs['nodes'],200000)
        self.assertEqual(card_from_exercise(result['exercises'][0]).continuation_san,('d4','d5'))
        self.assertNotIn('review',result['exercises'][0])

    def test_unstable_recommendation_is_declined(self):
        result,_ = self.prepare_fixture('c4')
        self.assertEqual(result['exercises'],[])

    def test_no_candidates_is_valid(self):
        s = snapshot()
        with patch('chess_coach.exercises.analyze_pgn',return_value={'source':s['source'],'engine':{},'created_at':'now','candidates':[]}):
            self.assertEqual(prepare(Mock(),s['source']['pgn'],'white')['exercises'],[])

    def test_recommendation_changed_during_continuation_search_is_declined(self):
        s = snapshot()
        engine = Mock(id={'name':'Test'})
        engine.analyse.return_value = [
            {'pv':[chess.Move.from_uci('c2c4')], 'score':chess.engine.PovScore(chess.engine.Cp(210),chess.WHITE)},
            {'pv':[chess.Move.from_uci('d2d4')], 'score':chess.engine.PovScore(chess.engine.Cp(200),chess.WHITE)}]
        verified = MoveComparison(chess.STARTING_FEN,'e4','d4',
                                  EngineEvaluation(200,None,200),EngineEvaluation(0,None,0),200)
        report = {'source':s['source'],'engine':{},'created_at':'now','candidates':[s['candidate']]}
        with patch('chess_coach.exercises.analyze_pgn',return_value=report), patch('chess_coach.exercises.compare_move',return_value=verified):
            self.assertEqual(prepare(engine,s['source']['pgn'],'white')['exercises'],[])
