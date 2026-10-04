"""SQLite backup/restore with new destinations only."""

import argparse
from pathlib import Path
import sqlite3

from chess_coach.storage import Store


def restore(source, destination):
    if Path(destination).exists() or not Path(source).is_file():
        raise ValueError('Restore requires an existing backup and a new destination')
    db = sqlite3.connect('file:' + str(Path(source).resolve()) + '?mode=ro', uri=True)
    try:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA user_version').fetchone()[0] != 1:
            raise ValueError('Invalid or unsupported backup')
        target = sqlite3.connect(destination)
        try:
            db.backup(target)
        finally:
            target.close()
    finally:
        db.close()
    Store(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup','restore'])
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    if args.action == 'restore':
        restore(args.source,args.destination)
    else:
        if not Path(args.source).is_file():
            parser.error('Database does not exist')
        Store(args.source).backup(args.destination)


if __name__ == '__main__':
    main()
