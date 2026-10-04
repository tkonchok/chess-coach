"""Local SVG snapshots with no inline CSS or external resources."""
from xml.etree import ElementTree
import chess
import chess.svg

ElementTree.register_namespace('', 'http://www.w3.org/2000/svg')
ElementTree.register_namespace('xlink', 'http://www.w3.org/1999/xlink')


def board_thumbnail(board, color):
    svg = chess.svg.board(board,size=128,coordinates=False,
        orientation=chess.BLACK if color == 'black' else chess.WHITE,
        colors={'square light':'#eeefd3','square dark':'#809c61'})
    root = ElementTree.fromstring(svg)
    for element in root.iter():
        # Presentation attributes work with the application's strict CSP.
        for declaration in element.attrib.pop('style','').split(';'):
            if declaration.strip():
                name,value = declaration.split(':',1)
                element.set(name.strip(),value.strip())
    # Keep piece IDs and internal <use> references: each image is isolated.
    return ElementTree.tostring(root,encoding='unicode')
