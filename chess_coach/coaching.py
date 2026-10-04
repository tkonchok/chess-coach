"""Positions-only external coaching. Identity and notes cannot enter this API."""

import json
import re
import ssl
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler

import certifi


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def evidence(snapshot):
    # Explicit allowlist: never serialize a snapshot, PGN, user, or attempt.
    return {'fen': snapshot['card']['position_fen'],
            'played_move': snapshot['card']['played_move_san'],
            'recommended_move': snapshot['verification']['best_move_san'],
            'best_cp': snapshot['verification']['best_evaluation']['centipawns'],
            'played_cp': snapshot['verification']['played_evaluation']['centipawns'],
            'lines': snapshot['lines']}


def request_payload(snapshot, model):
    data = evidence(snapshot)
    schema = {'type': 'object', 'properties': {
        'explanation': {'type': 'string'}, 'suggestion': {'type': 'string'},
        'move_references': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['explanation', 'suggestion', 'move_references'], 'additionalProperties': False}
    return {'model': model, 'max_completion_tokens': 2048,
            'messages': [{'role': 'system', 'content':
                'Explain only the supplied chess evidence briefly. Scores are from the mover perspective. '
                'Lines are illustrative, not unique or forced. Do not infer intention, habits or rating improvement. '
                'Use only supplied moves, list all mentioned moves in move_references. '
                'Give one practical suggestion; express uncertainty. Return the requested JSON.'},
                {'role': 'user', 'content': json.dumps(data, allow_nan=False)}],
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'chess_explanation', 'strict': True, 'schema': schema}}}


def validate_response(value, snapshot):
    if not isinstance(value, dict) or set(value) != {'explanation', 'suggestion', 'move_references'}:
        raise ValueError('Unexpected coaching response')
    for key in ('explanation', 'suggestion'):
        if not isinstance(value[key], str) or not 1 <= len(value[key].strip()) <= 1200:
            raise ValueError('Invalid coaching text')
    allowed = {snapshot['card']['played_move_san']}
    allowed.update(m for line in snapshot['lines'] for m in line['moves'])
    refs = value['move_references']
    if not isinstance(refs, list) or len(refs) > 30 or any(not isinstance(m, str) or m not in allowed for m in refs):
        raise ValueError('Unsupported coaching move reference')
    mentioned = re.findall(r'(?<!\w)(?:O-O(?:-O)?[+#]?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)(?!\w)',
                           value['explanation'] + ' ' + value['suggestion'])
    if any(m not in allowed or m not in refs for m in mentioned):
        raise ValueError('Unreferenced move in coaching text')
    return value


def coach(snapshot, api_key, model='openai/gpt-oss-120b', *, transport=None):
    payload = request_payload(snapshot, model)
    return validate_response(completion(payload,api_key,transport),snapshot)


def completion(payload, api_key, transport=None):
    if transport is not None:
        response = transport(payload)
    else:
        request = Request('https://api.groq.com/openai/v1/chat/completions',
                          data=json.dumps(payload).encode(),
                          headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json',
                                   'User-Agent': 'ChessCoach/0.1'})
        context = ssl.create_default_context(cafile=certifi.where())
        with build_opener(NoRedirect(), HTTPSHandler(context=context)).open(request, timeout=20) as result:
            body = result.read(65537)
        if len(body) > 65536:
            raise ValueError('Oversized coaching response')
        response = json.loads(body)
    text = response['choices'][0]['message']['content']
    return json.loads(text)


def walkthrough_payload(evidence, model):
    # This object originates solely from the bounded engine worker, never from
    # an attempt or browser-supplied evidence. Exclude internal IDs/settings.
    data = {key:evidence[key] for key in ('initial_fen','perspective','comparison_uncertain','same_move')}
    data['branches'] = [{'id':branch['id'],'root_san':branch['root_san'],
        'searches':[{key:search[key] for key in ('nodes_limit','seconds_limit','centipawns','mate')} for search in branch['searches']],
        'steps':[{key:step[key] for key in ('ply','san','before_fen','after_fen','facts')} for step in branch['steps']]}
        for branch in evidence['branches']]
    item = {'type':'object','properties':{
        'branch':{'type':'string'},'ply':{'type':'integer'},'text':{'type':'string'},
        'fact_ids':{'type':'array','items':{'type':'string'}},
        'move_references':{'type':'array','items':{'type':'string'}}},
        'required':['branch','ply','text','fact_ids','move_references'],'additionalProperties':False}
    return {'model':model,'max_completion_tokens':4096,
            'messages':[{'role':'system','content':
                'Write one concise chess coaching sentence per supplied branch/ply, in steps JSON. '
                'Explain the move through its supplied facts and the position, not merely score numbers. '
                'Reference at least one fact_id from that exact step. Use only moves already played '
                'through that ply in that branch; list mentioned SAN moves in move_references. '
                'Name board squares only when they occur in the squares of your cited facts. '
                'Do not invent candidate moves or reference a different branch. '
                'Use exact supplied SAN notation, never long notation such as Qd3-c4. '
                'Do not include fact IDs in the prose. Explain one salient fact rather than listing all attacks. '
                'Say captures or recaptures, not wins a piece, when the line is a material exchange. '
                'Do not spoil future moves. These lines are illustrative, not forced. '
                'Do not claim trapped pieces, guaranteed loss, missed opportunities or inferred intentions. '
                'An attack does not prove a capture is unavoidable. Root scores describe the starting '
                'choice only, not intermediate positions. If comparison_uncertain, do not claim one root '
                'is better. No statements about habits, rating or improved learning. '
                'Keep each text below 180 characters, with natural useful wording and uncertainty when needed.'},
                {'role':'user','content':json.dumps(data,allow_nan=False)}],
            'response_format':{'type':'json_schema','json_schema':{'name':'walkthrough_steps','strict':True,
                'schema':{'type':'object','properties':{'steps':{'type':'array','items':item}},
                          'required':['steps'],'additionalProperties':False}}}}


def validate_walkthrough(value, evidence):
    if not isinstance(value,dict) or set(value) != {'steps'} or not isinstance(value['steps'],list):
        raise ValueError('Unexpected walkthrough commentary')
    expected = {(branch['id'],step['ply']):(branch,step)
                for branch in evidence['branches'] for step in branch['steps']}
    seen = set()
    for item in value['steps']:
        if not isinstance(item,dict) or set(item) != {'branch','ply','text','fact_ids','move_references'}:
            raise ValueError('Unexpected step commentary')
        if not isinstance(item['branch'],str) or type(item['ply']) is not int:raise ValueError('Invalid step identity')
        key = (item['branch'],item['ply'])
        if key not in expected or key in seen:raise ValueError('Mismatched step identity')
        seen.add(key);branch,step = expected[key]
        if not isinstance(item['text'],str) or not 1 <= len(item['text'].strip()) <= 500:
            raise ValueError('Invalid step text')
        if re.search(r'\b(trapped|forced|guaranteed|inevitable)\b|lost your chance',item['text'],re.I):
            raise ValueError('Unsupported certainty claim')
        facts = {fact['id'] for fact in step['facts']}
        refs = item['fact_ids'];moves = item['move_references']
        if not isinstance(refs,list) or not 1 <= len(refs) <= len(facts) or any(not isinstance(ref,str) or ref not in facts for ref in refs):
            raise ValueError('Unsupported fact reference')
        allowed = {s['san'] for s in branch['steps'] if s['ply'] <= step['ply']}
        if not isinstance(moves,list) or len(moves) > 6 or any(not isinstance(move,str) or move not in allowed for move in moves):
            raise ValueError('Unsupported step move reference')
        squares = set(re.findall(r'\b[a-h][1-8]\b',item['text']))
        allowed_squares = {square for fact in step['facts'] if fact['id'] in refs for square in fact['squares']}
        mentioned = re.findall(r'(?<!\w)(?:O-O(?:-O)?[+#]?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)(?!\w)',item['text'])
        if any(move not in moves and move not in allowed_squares for move in mentioned):raise ValueError('Unreferenced step move')
        if not squares <= allowed_squares:raise ValueError('Unsupported square reference')
    if seen != set(expected):raise ValueError('Missing step commentary')
    return value


def coach_walkthrough(evidence, api_key, model, *, transport=None):
    return validate_walkthrough(completion(walkthrough_payload(evidence,model),api_key,transport),evidence)
