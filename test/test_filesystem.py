from unittest import TestCase
from unittest.mock import create_autospec

import filesystem
import model
from . import fixtures


class TestSaver(TestCase):

    def setUp(self):
        self.fs = create_autospec(filesystem.FilesystemClient)
        self.saver = filesystem.Saver(self.fs)
        self.category = fixtures.simple_category()

    def test_saves_category(self):
        self.saver.save([self.category])

        self.fs.save_json.assert_any_call('category/.group.meta',
                                          {'id': 'category id', 'webtranslateit_ids': ['category translate id']})
        self.fs.save_json.assert_any_call(
            'category/__group__.json', {'name': 'category', 'description': 'category desc'})

    def test_saves_section(self):
        self.saver.save([self.category])

        self.fs.save_json.assert_any_call('category/section/.group.meta',
                                          {'id': 'section id', 'webtranslateit_ids': ['section translate id']})
        self.fs.save_json.assert_any_call(
            'category/section/__group__.json', {'name': 'section', 'description': 'section desc'})

    def test_saves_article(self):
        self.saver.save([self.category])

        self.fs.save_json.assert_any_call('category/section/en-US/.article_article.meta',
                                          {'id': 'article id',
                                           'webtranslateit_ids': ['body translate id', 'article translate id']})
        self.fs.save_json.assert_any_call('category/section/en-US/article.json', {'name': 'article'})
        self.fs.save_text.assert_any_call('category/section/en-US/article.mkdown', 'body')


class TestLoader(TestCase):

    def setUp(self):
        self.fs = create_autospec(filesystem.FilesystemClient)
        self.loader = filesystem.Loader(self.fs, 'dummy_folder')
        self.fs.read_directories.return_value = ['dummy_group']
        self.fs.read_files.return_value = ['dummy-article.mkdown']
        self.fs.read_json.return_value = {'name': 'dummy name', 'description': 'dummy descrition'}
        self.fs.read_text.return_value = 'dummy body'

    def test_load_category(self):
        category = self.loader.load()[0]

        self.assertEqual('dummy name', category.name)
        self.assertEqual(1, len(category.sections))

    def test_load_section(self):
        category = self.loader.load()[0]
        section = category.sections[0]

        self.assertEqual('dummy name', section.name)
        self.assertEqual(category, section.category)
        self.assertEqual(1, len(section.articles))

    def test_load_article(self):
        category = self.loader.load()[0]
        section = category.sections[0]
        article = section.articles[0]

        self.assertEqual('dummy name', article.name)
        self.assertEqual(section, article.section)

    def test_filter_article_names(self):
        names = self.loader._filter_article_names(['dummy-article.mkdown', '.article_dummy-article.meta',
                                                   'dummy-article.json', 'new-article.mkdown',
                                                   '.article_new-article.meta', 'new-article.json'])
        self.assertEqual(['dummy-article', 'new-article'], list(names))

    def test_group_translations(self):
        category = fixtures.simple_category()
        self.fs.read_files.return_value = ['__group__.json', '__group__.pl.json', 'something-else']

        translations = self.loader._group_translations(category)

        self.assertEqual(1, len(translations))
        self.assertEqual('dummy name', translations[0].name)
        self.assertEqual('dummy descrition', translations[0].description)
        self.assertEqual('pl', translations[0].locale)

    def test_article_translations(self):
        category = fixtures.simple_category()
        article = category.sections[0].articles[0]
        self.fs.read_directories.return_value = [model.DEFAULT_LOCALE, 'pl']

        translations = self.loader._article_translations(article)

        self.assertEqual(1, len(translations))
        self.assertEqual('dummy name', translations[0].name)
        self.assertEqual('dummy body', translations[0].body)
        self.assertEqual('pl', translations[0].locale)