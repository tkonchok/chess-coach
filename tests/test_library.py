from copy import deepcopy
import unittest
from beta_fixtures import snapshot
from chess_coach.library import grouped_library,game_metadata

class LibraryTests(unittest.TestCase):
    def test_order_groups_positions_versions_and_filters(self):
        original=snapshot();later=deepcopy(original);later['candidate']['source_ply_count']=6
        later['version_id']='later';later['analysis_created_at']='2026-10-03T00:00:00+00:00'
        other=deepcopy(original);other['source']['id']='another';other['analysis_created_at']='2026-10-04T00:00:00+00:00'
        old=deepcopy(original);old['version_id']='old';old['analysis_created_at']='2026-10-01T00:00:00+00:00'
        rows=[{'version':value['version_id'],'exercise':value,'completed':count} for value,count in [(later,0),(original,2),(other,0),(old,0)]]
        library=grouped_library(rows)
        self.assertEqual((library['total'],library['practiced'],library['remaining']),(4,1,3))
        self.assertEqual(library['groups'][0]['latest'],other['analysis_created_at'])
        group=library['groups'][1]
        self.assertEqual([item['move'] for item in group['items']],[1,1,4])
        self.assertTrue(group['items'][0]['repeated'])
        self.assertEqual(len(grouped_library(rows,'practiced')['groups'][0]['items']),1)
        self.assertEqual(grouped_library(rows,'remaining')['groups'][1]['practiced'],1)
    def test_color_groups_and_unknown_metadata(self):
        value=snapshot();black=deepcopy(value);black['player_color']='black'
        result=grouped_library([{'version':item['version_id'],'exercise':item,'completed':0} for item in (value,black)])
        self.assertEqual(len(result['groups']),2)
        self.assertNotEqual(result['groups'][0]['anchor'],result['groups'][1]['anchor'])
        metadata=game_metadata({'id':'unknown','headers':{}},'white')
        self.assertEqual(metadata['date'],'Game date unavailable')
        self.assertEqual(metadata['opponent'],'Unknown opponent')
        self.assertEqual(metadata['result'],'Result unavailable')
        self.assertEqual(game_metadata({'headers':{'Date':'2026.10.03'}},'white')['date'],'Oct 03, 2026')
