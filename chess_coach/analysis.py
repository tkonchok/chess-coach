"""Compare a played chess move with an engine's preferred move."""

from dataclasses import dataclass

import chess
import chess.engine


MATE_SCORE = 100_000


@dataclass(frozen=True)
class EngineEvaluation:
    """An engine score plus a numeric value suitable for ranking."""

    centipawns: int | None
    mate_in: int | None
    ranking_value: int

    def __post_init__(self) -> None:
        if (self.centipawns is None) == (self.mate_in is None):
            raise ValueError(
                "Exactly one of centipawns and mate_in must be populated"
            )

        if self.centipawns is not None:
            expected_ranking_value = self.centipawns
        else:
            expected_ranking_value = chess.engine.Mate(self.mate_in).score(
                mate_score=MATE_SCORE
            )

        if self.ranking_value != expected_ranking_value:
            raise ValueError("ranking_value does not match the represented score")


@dataclass(frozen=True)
class MoveComparison:
    """Engine comparison for one played move from one position."""

    position_fen: str
    played_move_san: str
    best_move_san: str
    best_evaluation: EngineEvaluation
    played_evaluation: EngineEvaluation
    evaluation_loss: int


def compare_move(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    played_move: chess.Move,
    *,
    nodes: int = 100_000,
) -> MoveComparison:
    """Compare a legal played move with an engine candidate using paired analysis."""
    if nodes <= 0:
        raise ValueError("nodes must be greater than zero")

    if played_move not in board.legal_moves:
        raise ValueError("played_move must be legal in the supplied position")

    point_of_view = board.turn
    position_fen = board.fen()
    played_move_san = board.san(played_move)
    limit = chess.engine.Limit(nodes=nodes)
    requested_info = chess.engine.INFO_SCORE | chess.engine.INFO_PV

    seed_result = engine.analyse(
        board,
        limit,
        info=requested_info,
    )
    candidate_move = _principal_move(seed_result, "seed")
    seed_evaluation = _engine_evaluation(seed_result, point_of_view, "seed")

    if candidate_move == played_move:
        return MoveComparison(
            position_fen=position_fen,
            played_move_san=played_move_san,
            best_move_san=played_move_san,
            best_evaluation=seed_evaluation,
            played_evaluation=seed_evaluation,
            evaluation_loss=0,
        )

    paired_results = engine.analyse(
        board,
        limit,
        info=requested_info,
        multipv=2,
        root_moves=[candidate_move, played_move],
    )
    if not isinstance(paired_results, list):
        raise RuntimeError("Engine paired analysis did not return multiple lines")

    expected_roots = {candidate_move, played_move}
    evaluations_by_root: dict[chess.Move, EngineEvaluation] = {}

    for result in paired_results:
        root_move = _principal_move(result, "paired")
        if root_move not in expected_roots:
            raise RuntimeError("Engine paired analysis returned an unexpected root move")
        if root_move in evaluations_by_root:
            raise RuntimeError("Engine paired analysis returned a duplicate root move")

        evaluations_by_root[root_move] = _engine_evaluation(
            result, point_of_view, "paired"
        )

    missing_roots = expected_roots - evaluations_by_root.keys()
    if missing_roots:
        raise RuntimeError("Engine paired analysis omitted a requested root move")

    candidate_evaluation = evaluations_by_root[candidate_move]
    played_evaluation = evaluations_by_root[played_move]

    if played_evaluation.ranking_value > candidate_evaluation.ranking_value:
        best_move = played_move
        best_evaluation = played_evaluation
    else:
        best_move = candidate_move
        best_evaluation = candidate_evaluation

    return MoveComparison(
        position_fen=position_fen,
        played_move_san=played_move_san,
        best_move_san=board.san(best_move),
        best_evaluation=best_evaluation,
        played_evaluation=played_evaluation,
        evaluation_loss=max(
            0, best_evaluation.ranking_value - played_evaluation.ranking_value
        ),
    )


def _principal_move(result: chess.engine.InfoDict, analysis_name: str) -> chess.Move:
    principal_variation = result.get("pv")
    if not principal_variation:
        raise RuntimeError(
            f"Engine {analysis_name} analysis did not return a principal variation"
        )

    return principal_variation[0]


def _engine_evaluation(
    result: chess.engine.InfoDict,
    point_of_view: chess.Color,
    analysis_name: str,
) -> EngineEvaluation:
    score = result.get("score")
    if score is None:
        raise RuntimeError(f"Engine {analysis_name} analysis did not return a score")

    relative_score = score.pov(point_of_view)
    ranking_value = relative_score.score(mate_score=MATE_SCORE)
    if ranking_value is None:
        raise RuntimeError(f"Engine {analysis_name} score could not be converted")

    mate_in = relative_score.mate()
    if mate_in is not None:
        return EngineEvaluation(
            centipawns=None,
            mate_in=mate_in,
            ranking_value=ranking_value,
        )

    return EngineEvaluation(
        centipawns=ranking_value,
        mate_in=None,
        ranking_value=ranking_value,
    )
