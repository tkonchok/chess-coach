from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import chess

from chess_coach.pgn import parse_pgn
from chess_coach.analysis import EngineEvaluation, MoveComparison
from chess_coach.training import TrainingCard, build_training_card
from chess_coach.web import create_app, create_app_from_review
from chess_coach.workflow import analyze_pgn, review_candidate


def position_card(fen, line):
    return TrainingCard(0, fen, line[0], "Choose a move.", tuple(line), "An illustrative line.")


class PracticeWebTests(unittest.TestCase):
    def setUp(self):
        self.card = build_training_card(parse_pgn("1. e4 e5 *"), 0,
                                        continuation_san=["d4", "d5", "c4"],
                                        explanation="Contest the center; one possible line.")
        self.app = create_app(self.card)
        self.app.testing = True
        self.client = self.app.test_client()
        self.initial = self.client.get("/api/position").get_json()

    def post(self, moves, **kwargs):
        return self.client.post("/api/position", json={
            "card_id": self.initial["card_id"], "moves": moves}, **kwargs)

    def test_page_has_board_and_separate_reflections_without_the_answer(self):
        response = self.client.get("/")
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(page.count('class="square '), 64)
        self.assertIn('id="reasoning"', page)
        self.assertIn('id="takeaway"', page)
        self.assertIn('id="promotion"', page)
        # Piece templates are cloned for every piece; their internal IDs would
        # otherwise be repeated across the rendered board.
        self.assertNotIn('id="white-pawn"', page)
        self.assertNotIn('id="black-pawn"', page)
        self.assertNotIn(self.card.explanation, page)
        self.assertNotIn("continuation_san", self.initial)
        self.assertNotIn("played_move_san", self.initial)
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

    def test_initial_page_shows_original_move_without_revealing_example_or_playing_it(self):
        black_card = build_training_card(parse_pgn("1. e4 e5 *"), 1,
                                         continuation_san=["c5", "Nf3"],
                                         explanation="An alternative response to e4.")
        for card in (self.card, black_card):
            with self.subTest(played_move=card.played_move_san):
                client = create_app(card).test_client()
                page = client.get("/").get_data(as_text=True)
                self.assertIn(
                    f'In your game, you played <strong>{card.played_move_san}</strong>.',
                    page,
                )
                self.assertNotIn(card.explanation, page)
                self.assertIn('<p id="example-line" class="line"></p>', page)
                initial = client.get("/api/position").get_json()
                self.assertEqual(initial["fen"], card.position_fen)
                self.assertEqual(initial["sans"], [])

    def test_piece_colors_use_svg_attributes_instead_of_blocked_inline_styles(self):
        from xml.etree import ElementTree
        from chess_coach.web import piece_svg
        for symbol in 'PNBRQKpnbrqk':
            markup=str(piece_svg(symbol))
            self.assertNotIn('style=',markup)
            self.assertNotIn('id=',markup)
            ElementTree.fromstring(markup)
        for symbol,fill in [('N','#ffffff'),('n','#000000')]:
            root=ElementTree.fromstring(str(piece_svg(symbol)))
            paths=root.findall('.//{http://www.w3.org/2000/svg}path')
            self.assertEqual([path.get('fill') for path in paths[:2]],[fill,fill])

    def test_move_response_contains_canonical_san_and_updated_position(self):
        result = self.post(["e2e4"]).get_json()
        board = chess.Board()
        board.push_san("e4")
        self.assertEqual(result["fen"], board.fen())
        self.assertEqual(result["sans"], ["e4"])
        self.assertEqual(result["pieces"]["e4"], "P")
        self.assertEqual(result["turn"], "black")
        self.assertNotIn("e2", result["pieces"])

    def test_reflections_are_optional_and_original_reasoning_is_separate(self):
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn('<details id="original-reflection">', page)
        self.assertIn('id="original-reasoning"', page)
        self.assertIn('id="dont-remember"', page)
        self.assertIn('<details id="attempt-reflection">', page)
        self.assertIn('id="reasoning"', page)
        self.assertIn('id="takeaway"', page)
        self.assertIn('>Reveal reviewed example</button>', page)
        self.assertNotIn('id="skip"', page)
        self.assertNotIn(' required', page)

    def test_illegal_move_rejected_and_requests_do_not_share_board_state(self):
        self.assertEqual(self.post(["e2e5"]).status_code, 400)
        self.post(["e2e4", "e7e5"])
        other = self.app.test_client().get("/api/position").get_json()
        self.assertEqual(other["fen"], chess.STARTING_FEN)
        self.assertEqual(self.post([]).get_json()["fen"], chess.STARTING_FEN)

    def test_bad_paths_and_excessive_input_are_rejected(self):
        for path in (None, "e2e4", [None], ["0000"], ["<script>"], ["e2e4"] * 129):
            with self.subTest(path=path):
                self.assertEqual(self.post(path).status_code, 400)
        self.assertEqual(self.client.post("/api/position", data="{}", content_type="text/plain").status_code, 415)
        self.assertEqual(self.client.post("/api/position", data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/api/position", data=" " * 9000, content_type="application/json").status_code, 413)

    def test_stale_card_and_arbitrary_fen_are_rejected(self):
        self.assertEqual(self.client.post("/api/position", json={
            "card_id": "old", "moves": []}).status_code, 409)
        self.assertEqual(self.client.post("/api/position", json={
            "card_id": self.initial["card_id"], "moves": [], "fen": chess.STARTING_FEN}).status_code, 400)

    def test_reveal_returns_reviewed_line_and_no_grade(self):
        result = self.client.get("/api/reveal").get_json()
        self.assertEqual(result["moves"], ["d2d4", "d7d5", "c2c4"])
        self.assertEqual(result["explanation"], self.card.explanation)
        self.assertEqual(result["played_move_san"], "e4")
        self.assertNotIn("correct", result)

    def test_security_rejects_foreign_origins_and_hosts(self):
        self.assertEqual(self.post([], headers={"Origin": "https://other.example"}).status_code, 403)
        self.assertEqual(self.post([], headers={"Sec-Fetch-Site": "cross-site"}).status_code, 403)
        self.assertEqual(self.client.get("/", headers={"Host": "other.example"}).status_code, 400)
        self.assertEqual(self.post([], headers={"Origin": "http://localhost"}).status_code, 200)

    def test_promotions_require_a_choice_and_support_underpromotion(self):
        card = position_card("7k/P7/8/8/8/8/8/7K w - - 0 1", ["a8=Q+"])
        client = create_app(card).test_client()
        state = client.get("/api/position").get_json()
        self.assertTrue(all("a7a8" + p in state["legal_moves"] for p in "qrbn"))
        for uci in ("a7a8", "a7a8k"):
            self.assertEqual(client.post("/api/position", json={"card_id": state["card_id"], "moves": [uci]}).status_code, 400)
        result = client.post("/api/position", json={"card_id": state["card_id"], "moves": ["a7a8n"]}).get_json()
        self.assertEqual(result["pieces"]["a8"], "N")

    def test_castling_and_en_passant_update_all_affected_squares(self):
        board = chess.Board()
        for san in ("e4", "a6", "e5", "d5"):
            board.push_san(san)
        cases = [("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "O-O", "e1g1", {"g1": "K", "f1": "R"}, ["e1", "h1"]),
                 (board.fen(), "exd6", "e5d6", {"d6": "P"}, ["d5", "e5"])]
        for fen, san, uci, pieces, empty in cases:
            with self.subTest(move=uci):
                client = create_app(position_card(fen, [san])).test_client()
                identity = client.get("/api/position").get_json()["card_id"]
                result = client.post("/api/position", json={"card_id": identity, "moves": [uci]}).get_json()
                for square, piece in pieces.items():
                    self.assertEqual(result["pieces"][square], piece)
                for square in empty:
                    self.assertNotIn(square, result["pieces"])

    def test_black_orientation_and_escaped_source_text(self):
        card = build_training_card(parse_pgn("1. e4 e5 *"), 1,
                                   continuation_san=["c5"], explanation="Contest d4.")
        page = create_app(card, source_label="<script>unsafe</script>").test_client().get("/").get_data(as_text=True)
        self.assertIn('data-orientation="black"', page)
        self.assertLess(page.index('data-square="h1"'), page.index('data-square="a8"'))
        self.assertIn("&lt;script&gt;unsafe&lt;/script&gt;", page)

    def test_illegal_card_line_is_rejected_at_startup(self):
        with self.assertRaises(ValueError):
            create_app(replace(self.card, continuation_san=("e5",)))

    def test_checkmate_stops_exploration_but_reset_still_works(self):
        moves = ["f2f3", "e7e5", "g2g4", "d8h4"]
        result = self.post(moves).get_json()
        self.assertEqual(result["outcome"], "0-1")
        self.assertEqual(result["check"], "e1")
        self.assertEqual(result["legal_moves"], [])
        self.assertEqual(self.post(moves + ["a2a3"]).status_code, 400)
        self.assertEqual(self.post([]).get_json()["fen"], chess.STARTING_FEN)

    def test_default_card_reveal_replays_legally(self):
        client = create_app().test_client()
        initial = client.get("/api/position").get_json()
        reveal = client.get("/api/reveal").get_json()
        result = client.post("/api/position", json={
            "card_id": initial["card_id"], "moves": reveal["moves"]})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()["sans"], ["Bxf7+", "Kg7", "Bxe8", "Qxe8"])


class ReviewedAppTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "review.json"

    def snapshot(self, second=False):
        examples = Path(__file__).resolve().parents[1] / "examples"
        pgn = (examples / ("second-game.pgn" if second else "game.pgn")).read_text(encoding="utf-8")
        review = json.loads((examples / ("second-review.json" if second else "first-review.json"))
                            .read_text(encoding="utf-8"))
        card = build_training_card(parse_pgn(pgn), review["source_ply_count"],
                                   continuation_san=review["continuation_san"],
                                   explanation=review["explanation"])
        score = EngineEvaluation(0, None, 0)
        comparison = MoveComparison(card.position_fen, card.played_move_san,
                                    card.played_move_san, score, score, 0)
        with patch("chess_coach.workflow.analyze_player_moves", return_value=[comparison]):
            report = analyze_pgn(Mock(id={"name": "Test engine"}), pgn,
                                 "black" if second else "white")
        return review_candidate(report, review)

    def test_loads_both_example_reviews_with_source_and_version_labels(self):
        for second in (False, True):
            with self.subTest(second=second):
                snapshot = self.snapshot(second)
                self.path.write_text(json.dumps(snapshot), encoding="utf-8")
                client = create_app_from_review(str(self.path)).test_client()
                initial = client.get("/api/position").get_json()
                reveal = client.get("/api/reveal").get_json()
                self.assertEqual(initial["fen"], snapshot["card"]["position_fen"])
                self.assertEqual(reveal["explanation"], snapshot["card"]["explanation"])
                replay = client.post("/api/position", json={
                    "card_id": initial["card_id"], "moves": reveal["moves"]})
                self.assertEqual(replay.get_json()["sans"], list(snapshot["card"]["continuation_san"]))
                page = client.get("/").get_data(as_text=True)
                self.assertIn(f"source {snapshot['source']['id'][:12]}", page)
                self.assertIn(f"review {snapshot['version_id'][:12]}", page)

    def test_accepts_file_at_exact_byte_limit(self):
        content = json.dumps(self.snapshot(), ensure_ascii=False).encode("utf-8")
        self.path.write_bytes(content)
        with patch("chess_coach.web.MAX_REVIEW_BYTES", len(content), create=True):
            client = create_app_from_review(str(self.path)).test_client()
            self.assertEqual(client.get("/api/position").status_code, 200)

    def test_rejects_oversized_file_instead_of_accepting_valid_prefix(self):
        content = json.dumps(self.snapshot()).encode("utf-8")
        self.assertLess(len(content), 8192)
        self.path.write_bytes(content.ljust(8192) + b"invalid trailing content")
        with patch("chess_coach.web.MAX_REVIEW_BYTES", 8192, create=True):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                create_app_from_review(str(self.path))

    def test_invalid_files_fail_before_app_creation(self):
        changed = self.snapshot()
        changed["card"]["explanation"] = "Unreviewed change"
        rejected = self.snapshot()
        rejected["review"]["decision"] = "reject"
        rejected["card"] = None
        for content in (b"{", b"\xff", b"null", json.dumps(changed).encode(),
                        json.dumps(rejected).encode()):
            with self.subTest(content=content[:30]):
                self.path.write_bytes(content)
                with patch("chess_coach.web.create_app") as factory:
                    with self.assertRaises(ValueError):
                        create_app_from_review(str(self.path))
                    factory.assert_not_called()

    def test_missing_file_does_not_fall_back_to_default_card(self):
        with patch("chess_coach.web.create_app") as factory:
            with self.assertRaises(FileNotFoundError):
                create_app_from_review(str(self.path))
            factory.assert_not_called()
