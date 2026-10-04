"""Presentation of retained practice; saved attempts are not solve grades."""
from collections import Counter
from datetime import datetime
from hashlib import sha256


def game_metadata(source, color):
    headers = source.get('headers', {})
    date = headers.get('UTCDate') or headers.get('Date', '')
    try:
        date = datetime.strptime(date, '%Y.%m.%d').strftime('%b %d, %Y')
    except ValueError:
        date = 'Game date unavailable'
    return {'player': headers.get(color.capitalize()) or 'Unknown player',
            'opponent': headers.get('Black' if color == 'white' else 'White') or 'Unknown opponent',
            'date': date, 'result': headers.get('Result') if headers.get('Result') in ('1-0','0-1','1/2-1/2') else 'Result unavailable',
            'color': color, 'anchor': 'game-' + sha256((source.get('id','') + ':' + color).encode()).hexdigest()[:16]}


def position_items(rows):
    items = []
    for row in rows:
        exercise = row['exercise']
        item = dict(row, move=exercise['candidate']['source_ply_count'] // 2 + 1,
                    color=exercise['player_color'], analyzed=exercise.get('analysis_created_at',''), repeated=False)
        items.append(item)
    counts = Counter((item['exercise']['source']['id'], item['color'], item['exercise']['candidate']['source_ply_count']) for item in items)
    for item in items:
        item['repeated'] = counts[(item['exercise']['source']['id'],item['color'],item['exercise']['candidate']['source_ply_count'])] > 1
    return sorted(items, key=lambda item:(item['exercise']['candidate']['source_ply_count'],item['analyzed'],item['version']))


def grouped_library(rows, status='all'):
    groups = {}
    items = position_items(rows)
    for item in items:
        exercise = item['exercise']
        key = (exercise['source']['id'],item['color'])
        if key not in groups:
            groups[key] = dict(game_metadata(exercise['source'],item['color']), items=[], latest='')
        group = groups[key]
        group['items'].append(item)
        group['latest'] = max(group['latest'],item['analyzed'])
    visible = []
    for group in groups.values():
        group['total'] = len(group['items'])
        group['practiced'] = sum(bool(item['completed']) for item in group['items'])
        group['items'] = [item for item in group['items'] if status == 'all' or bool(item['completed']) == (status == 'practiced')]
        if group['items']: visible.append(group)
    return {'groups':sorted(visible,key=lambda group:(group['latest'],group['anchor']),reverse=True),
            'total':len(items),'practiced':sum(bool(item['completed']) for item in items),
            'remaining':sum(not item['completed'] for item in items)}
