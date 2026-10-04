"""Internal worker protocol. stdout is result JSON; errors never expose PGNs."""

import json
import sys

from chess_coach.exercises import prepare_game
from chess_coach.live import analyze_position
from chess_coach.walkthrough import analyze_walkthrough


def main():
    if sys.platform == 'linux':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (235, 240))
    try:
        data = json.loads(sys.stdin.read(1_100_001))
        if data.get('mode') == 'position':
            result = analyze_position(data['fen'], data['engine_path'])
        elif data.get('mode') == 'walkthrough':
            result = analyze_walkthrough(data['fen'],data['proposed'],data['recommended'],data['engine_path'])
        else:
            result = prepare_game(data['pgn'], data['color'], engine_path=data['engine_path'])
        sys.stdout.write(json.dumps(result, allow_nan=False))
        return 0
    except Exception:
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
