"""
tagcounter
----------------------------------
Tests for `tagcounter` module.
"""
import unittest
import yaml
import os
import datetime
from collections import Counter
from click.testing import CliRunner
from tagcounter import tagcounter


class TestTagcounter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.datadir = os.path.join(os.path.dirname(__file__), 'tagcounter_data')
        if not os.path.exists(cls.datadir):
            os.makedirs(cls.datadir)
        cls.testsyn_path = os.path.join(os.path.dirname(__file__), 'tagcounter_data/testsynonyms.yml')
        with open(cls.testsyn_path, 'w') as stream:
            yaml.safe_dump({'ggl':'google.com'}, stream)

    def test_synonyms_class(self):
        synonyms = tagcounter.Synonyms(self.testsyn_path)
        self.assertEqual(synonyms.check('ggl'),'google.com')
        self.assertEqual(synonyms.check('google.com'), 'google.com')
        synonyms.add('testsyn','testsite')
        self.assertEqual(synonyms.check('testsyn'), 'testsite')
        synonyms.update('testsyn', 'testsyn', 'testsite2')
        self.assertEqual(synonyms.check('testsyn'), 'testsite2')
        synonyms.delete('testsyn')
        self.assertEqual(synonyms.check('testsyn'), 'testsyn')

    def test_load_url(self):
        self.assertEqual(tagcounter.load_url('test',60)[0], 'Incorrect url')
        self.assertIsInstance(tagcounter.load_url('google.com', 60)[0], bytes)

    def test_html_parser(self):
        parser = tagcounter.MyHTMLParser()
        data = '<html><head><title>Test</title></head>'
        parser.feed(data)
        self.assertEqual(dict(Counter(parser.count)), {'head': 2, 'title': 2, 'html': 1})
        parser.reset()

    def test_add_check_db(self):
        tagcounter.add_item_db('testdata','google.com','http://google.com/')
        self.assertEqual(tagcounter.check_db('google.com')[0],'testdata')
        self.assertEqual(tagcounter.check_db('google.us')[0], None)
        self.assertIsInstance(type(tagcounter.check_db('google.com')[1]), type(datetime.datetime))

    def test_get_option(self):
        runner = CliRunner()
        result = runner.invoke(tagcounter.run, '--get test12345')
        self.assertEqual(0, result.exit_code)
        self.assertIn('Incorrect url', result.output)
        tagcounter.truncate_table()
        result = runner.invoke(tagcounter.run, '--get google.com')
        self.assertEqual(0, result.exit_code)
        self.assertIn('GET: Page loaded in', result.output)
        result = runner.invoke(tagcounter.run, '--get google.com')
        self.assertEqual(0, result.exit_code)
        self.assertIn('GET: Page has been loaded before:', result.output)

    def test_view_option(self):
        runner = CliRunner()
        result = runner.invoke(tagcounter.run, '--view test12345')
        self.assertEqual(0, result.exit_code)
        self.assertIn('was not found in the database, please use', result.output)
        result = runner.invoke(tagcounter.run, '--view google.com')
        self.assertEqual(0, result.exit_code)
        self.assertIn('Page has been loaded before:', result.output)

    @classmethod
    def tearDownClass(cls):
        tagcounter.session.close()
        tagcounter.teardown()
        os.remove(cls.testsyn_path)
        os.rmdir(cls.datadir)


if __name__ == '__main__':
    unittest.main()