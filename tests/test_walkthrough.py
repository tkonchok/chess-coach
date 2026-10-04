import copy
import json
import unittest
from unittest.mock import Mock, patch
import chess
import chess.engine
from chess_coach.walkthrough import prepare, step, digest
from chess_coach.coaching import coach_walkthrough, validate_walkthrough, walkthrough_payload


class FixtureEngine:
    id = {'name':'Fixture engine'}
    def __init__(self, scores=None):
        self.calls=[];self.scores=scores or {}
    def analyse(self,board,limit,**kwargs):
        root=kwargs['root_moves'][0];self.calls.append((board.fen(),limit,root))
        replay=board.copy();pv=[root];replay.push(root)
        while len(pv) < 6 and not replay.is_game_over():
            move=next(iter(replay.legal_moves));pv.append(move);replay.push(move)
        score=self.scores.get((root.uci(),limit.nodes),100 if root.uci() == 'e2e4' else 300)
        return {'pv':pv,'score':chess.engine.PovScore(chess.engine.Cp(score),board.turn),'depth':12,'nodes':limit.nodes}


def prepared():
    return prepare(FixtureEngine(),chess.STARTING_FEN,'e2e4','d2d4')


def commentary(evidence):
    return {'steps':[{'branch':branch['id'],'ply':move['ply'],'text':'Consider the piece’s destination.',
                     'fact_ids':['move'],'move_references':[]}
                    for branch in evidence['branches'] for move in branch['steps']]}


class WalkthroughTests(unittest.TestCase):
    def test_matched_budgets_legal_paths_and_fixed_perspective(self):
        for board,roots in [(chess.Board(),('e2e4','d2d4')),(chess.Board(),('e2e4','e2e4')),
                            (chess.Board('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'),('c7c5','e7e5'))]:
            engine=FixtureEngine();result=prepare(engine,board.fen(),*roots)
            self.assertEqual(result['same_move'],roots[0] == roots[1])
            self.assertEqual(len(result['branches']),1 if result['same_move'] else 2)
            self.assertEqual(result['perspective'],'white' if board.turn else 'black')
            self.assertEqual([(call[1].nodes,call[1].time) for call in engine.calls],[(50000,.5),(100000,1)]*len(result['branches']))
            for branch in result['branches']:
                replay=board.copy()
                for item in branch['steps']:
                    self.assertEqual(replay.fen(),item['before_fen']);replay.push_uci(item['uci'])
                    self.assertEqual(replay.fen(),item['after_fen'])
            self.assertEqual(result['walkthrough_id'],digest({k:v for k,v in result.items() if k != 'walkthrough_id'}))

    def test_unstable_ranking_and_illegal_roots(self):
        engine=FixtureEngine({('e2e4',50000):500,('e2e4',100000):100})
        self.assertTrue(prepare(engine,chess.STARTING_FEN,'e2e4','d2d4')['comparison_uncertain'])
        self.assertFalse(prepared()['comparison_uncertain'])
        with self.assertRaises(ValueError):prepare(engine,chess.STARTING_FEN,'e2e5','d2d4')
        engine=Mock(id={});engine.analyse.return_value={'pv':[chess.Move.from_uci('d2d4')]}
        with self.assertRaises(ValueError):prepare(engine,chess.STARTING_FEN,'e2e4','d2d4')

    def test_capture_en_passant_check_direct_attack_and_promotion(self):
        board=chess.Board('7k/8/8/3pP3/8/8/8/K7 w - d6 0 1')
        item=step(board,chess.Move.from_uci('e5d6'),1)
        self.assertEqual(item['material_change'],{'white':0,'black':-1})
        self.assertIn('d5',next(f for f in item['facts'] if f['id'] == 'capture')['squares'])
        board=chess.Board('7k/P7/8/8/8/8/8/7K w - - 0 1')
        item=step(board,chess.Move.from_uci('a7a8q'),1)
        self.assertEqual(item['material_change']['white'],8)
        self.assertTrue({'check','promotion'} <= {f['id'] for f in item['facts']})
        result=prepare(FixtureEngine(), '7k/P7/8/8/8/8/8/7K w - - 0 1','a7a8n','a7a8n')
        self.assertEqual(len(result['branches'][0]['steps']),1)
        self.assertIn('outcome',[f['id'] for f in result['branches'][0]['steps'][0]['facts']])
        board=chess.Board('7k/8/8/8/8/8/1r6/R6K w - - 0 1')
        item=step(board,chess.Move.from_uci('a1a2'),1)
        self.assertIn('attack-b2',[f['id'] for f in item['facts']])

    def test_commentary_structure_references_and_no_future_moves(self):
        evidence=prepared();valid=commentary(evidence)
        self.assertEqual(validate_walkthrough(valid,evidence),valid)
        for change in [lambda value:value['steps'].pop(),
                       lambda value:value['steps'].append(value['steps'][0]),
                       lambda value:value['steps'][0].update(branch='foreign'),
                       lambda value:value['steps'][0].update(ply=True),
                       lambda value:value['steps'][0].update(fact_ids=['invented']),
                       lambda value:value['steps'][0].update(text='Your bishop is trapped.'),
                       lambda value:value['steps'][0].update(text='Play Qh5.',move_references=['Qh5']),
                       lambda value:value['steps'][0].update(text='An attack on h8.',move_references=[])]:
            invalid=copy.deepcopy(valid);change(invalid)
            with self.assertRaises(ValueError):validate_walkthrough(invalid,evidence)
        # A square reference is allowed only through that step's supplied facts.
        valid['steps'][0].update(text='The pawn moves to e4.',fact_ids=['move'])
        validate_walkthrough(valid,evidence)
        invalid=copy.deepcopy(valid);invalid['steps'][0]['move_references']=[evidence['branches'][0]['steps'][1]['san']]
        with self.assertRaises(ValueError):validate_walkthrough(invalid,evidence)

    def test_provider_payload_excludes_identity_and_reflections(self):
        evidence=prepared() | {'email':'SECRET_EMAIL','username':'SECRET_USERNAME','takeaway':'SECRET_NOTE','original_reasoning':'SECRET_REASON'}
        captured=[]
        def transport(payload):
            captured.append(payload)
            return {'choices':[{'message':{'content':json.dumps(commentary(evidence))}}]}
        coach_walkthrough(evidence,'key','model',transport=transport)
        text=json.dumps(captured)
        for value in ('SECRET_EMAIL','SECRET_USERNAME','SECRET_NOTE','SECRET_REASON','walkthrough_id'):
            self.assertNotIn(value,text)
        self.assertEqual(captured[0]['max_completion_tokens'],4096)
