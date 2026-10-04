"""Synthetic engine evidence for network-free beta contract tests."""
from dataclasses import asdict
import chess
from chess_coach.analysis import EngineEvaluation, MoveComparison
from chess_coach.exercises import digest
from chess_coach.training import build_training_card
from chess_coach.workflow import pgn_digest, validated_game


def snapshot():
    pgn = '[White "PrivateName"]\n[Black "Opponent"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 1-0'
    game = validated_game(pgn)
    comparison = MoveComparison(chess.STARTING_FEN,'e4','d4',EngineEvaluation(200,None,200),EngineEvaluation(0,None,0),200)
    candidate = asdict(comparison) | {'source_ply_count':0,'played_move_uci':'e2e4'}
    card = build_training_card(game,0,continuation_san=['d4','d5'], explanation='Engine evidence fixture, not a teaching-quality claim.')
    payload = {'schema_version':2,'origin':'automatic-engine',
               'source':{'id':pgn_digest(pgn),'pgn':pgn,'headers':dict(game.headers)},
               'player_color':'white','engine':{'id':{'name':'Test engine'}, 'nodes_per_search':100000},
               'analysis_created_at':'2026-10-02T00:00:00+00:00','candidate':candidate,
               'verification':asdict(comparison),'lines':[{'moves':['d4','d5'],'centipawns':200}], 'card':asdict(card)}
    payload['version_id'] = digest(payload)
    return payload
