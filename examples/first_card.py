"""Generate the first local practice page: python -m examples.first_card."""

from pathlib import Path

from chess_coach.pgn import parse_pgn
from chess_coach.presentation import render_training_card
from chess_coach.training import build_training_card


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    game = parse_pgn(Path(__file__).with_name("game.pgn").read_text(encoding="utf-8"))
    card = build_training_card(
        game, 30,
        continuation_san=("Bxf7+", "Kg7", "Bxe8", "Qxe8"),
        explanation=(
            "Look at forcing checks before quieter moves. Bxf7+ captures a pawn "
            "with check. After the illustrated reply Kg7, Bxe8 captures the rook. "
            "Black can recapture with Qxe8: White has exchanged a bishop for a rook "
            "and a pawn in this line. This is one continuation, not a forced or "
            "unique solution; Ne5 is also a strong option in deeper analysis."
        ),
    )
    output = project_root / "generated" / "first-card.html"
    output.parent.mkdir(exist_ok=True)
    output.write_text(render_training_card(card), encoding="utf-8")
    print(f"Open this file in your browser: {output}")


if __name__ == "__main__":
    main()
