from dataclasses import replace
import unittest

import chess

from chess_coach.pgn import parse_pgn
from chess_coach.training import TrainingCard, build_training_card
from chess_coach.web import create_app


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

    def test_move_response_contains_canonical_san_and_updated_position(self):
        result = self.post(["e2e4"]).get_json()
        board = chess.Board()
        board.push_san("e4")
        self.assertEqual(result["fen"], board.fen())
        self.assertEqual(result["sans"], ["e4"])
        self.assertEqual(result["pieces"]["e4"], "P")
        self.assertEqual(result["turn"], "black")
        self.assertNotIn("e2", result["pieces"])

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
