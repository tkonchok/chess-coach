from dataclasses import replace
from html.parser import HTMLParser
import unittest

import chess

from chess_coach.pgn import parse_pgn
from chess_coach.presentation import render_training_card
from chess_coach.training import build_training_card


class PageElements(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.elements = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class RenderTrainingCardTests(unittest.TestCase):
    def setUp(self):
        self.card = build_training_card(
            parse_pgn("1. e4 e5 *"), 0,
            continuation_san=("d4", "d5", "c4"),
            explanation="An example of contesting the center.",
        )

    def test_precomputes_legal_frames_without_mutating_card(self):
        page = render_training_card(self.card)
        frames = [attrs for tag, attrs in PageElements(page).elements
                  if attrs.get("class") == "board-frame"]
        board = chess.Board()
        expected = [board.fen()]
        for san in self.card.continuation_san:
            board.push_san(san)
            expected.append(board.fen())

        self.assertEqual([frame["data-fen"] for frame in frames], expected)
        self.assertEqual(
            [frame["data-context"] for frame in frames],
            ["White to move · Move 1", "Black to move · Move 1",
             "White to move · Move 2", "Black to move · Move 2"],
        )
        self.assertNotIn("hidden", frames[0])
        self.assertTrue(all("hidden" in frame for frame in frames[1:]))
        self.assertEqual(self.card.position_fen, chess.STARTING_FEN)

    def test_reveal_is_initially_hidden_and_controls_are_at_start(self):
        elements = PageElements(render_training_card(self.card)).elements
        by_id = {attrs["id"]: attrs for _, attrs in elements if "id" in attrs}

        self.assertIn("hidden", by_id["reveal"])
        self.assertIn("hidden", by_id["playback"])
        self.assertIn("disabled", by_id["previous"])
        self.assertNotIn("disabled", by_id["next"])
        self.assertEqual(by_id["reveal-button"]["aria-expanded"], "false")
        self.assertEqual(by_id["move"]["autocomplete"], "off")

    def test_escapes_card_text_as_content_not_markup(self):
        hostile = '<script>alert("x")</script><img src="https://example.com/x">'
        card = replace(self.card, prompt=hostile, explanation=hostile,
                       played_move_san=hostile)
        page = render_training_card(card)

        self.assertNotIn(hostile, page)
        self.assertIn("&lt;script&gt;", page)
        self.assertFalse(any(tag == "img" for tag, _ in PageElements(page).elements))

    def test_page_has_no_external_resource_dependencies_or_duplicate_ids(self):
        elements = PageElements(render_training_card(self.card)).elements
        ids = [attrs["id"] for _, attrs in elements if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for tag, attrs in elements:
            if tag in ("script", "link", "img", "use"):
                for name in ("src", "href", "xlink:href"):
                    if name in attrs:
                        self.assertTrue(attrs[name].startswith("#"))

    def test_black_card_uses_black_orientation_and_move_numbers(self):
        card = build_training_card(
            parse_pgn("1. e4 e5 *"), 1,
            continuation_san=("c5", "Nf3"), explanation="Contest d4.",
        )
        page = render_training_card(card)
        self.assertIn('data-orientation="black"', page)
        self.assertIn("1... c5", page)
        self.assertIn("2. Nf3", page)

    def test_source_label_is_escaped(self):
        page = render_training_card(self.card, source_label='<img src="https://example.com">')
        self.assertIn("&lt;img", page)
        self.assertFalse(any(tag == "img" for tag, _ in PageElements(page).elements))
