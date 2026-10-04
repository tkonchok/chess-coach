import json
import unittest

from beta_fixtures import snapshot
from unittest.mock import Mock, patch
from chess_coach.coaching import coach,request_payload,validate_response


class CoachingTests(unittest.TestCase):
    def test_http_request_identifies_application_and_uses_positions_only_evidence(self):
        result={'explanation':'Consider d4.', 'suggestion':'Check replies.', 'move_references':['d4']}
        response=Mock()
        response.read.return_value=json.dumps({'choices':[{'message':{'content':json.dumps(result)}}]}).encode()
        response.__enter__=Mock(return_value=response)
        response.__exit__=Mock(return_value=False)
        opener=Mock()
        opener.open.return_value=response
        with patch('chess_coach.coaching.build_opener',return_value=opener):
            self.assertEqual(coach(snapshot(),'test-private-key'),result)
        request=opener.open.call_args.args[0]
        self.assertEqual(request.get_header('User-agent'),'ChessCoach/0.1')
        self.assertNotIn('PrivateName',request.data.decode())
        self.assertNotIn('test-private-key',request.data.decode())

    def test_payload_allowlist_and_no_private_data(self):
        value = snapshot()
        value['notes'] = 'SECRET REFLECTION'
        value['email'] = 'private@example.invalid'
        payload = request_payload(value,'test')
        encoded = json.dumps(payload)
        for secret in ('SECRET REFLECTION','PrivateName','private@example.invalid',value['source']['pgn']):
            self.assertNotIn(secret,encoded)
        data=json.loads(payload['messages'][1]['content'])
        self.assertEqual(set(data),{'fen','played_move','recommended_move','best_cp','played_cp','lines'})

    def test_valid_response_and_move_reference_checks(self):
        result={'explanation':'Consider d4, followed by d5. This is illustrative.',
                'suggestion':'Check the opponent reply before choosing.', 'move_references':['d4','d5']}
        transport=lambda payload:{'choices':[{'message':{'content':json.dumps(result)}}]}
        self.assertEqual(coach(snapshot(),'key',transport=transport),result)
        for updates in ({'move_references':['Qh5']},{'explanation':'Play Qh5.'}, {'suggestion':''}, {'move_references':None}):
            with self.subTest(updates=updates),self.assertRaises(ValueError):
                validate_response(result|updates,snapshot())
