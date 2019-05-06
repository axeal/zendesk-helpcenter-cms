import os
import utils
import markdown
import html2text
import re

DEFAULT_LOCALE = 'en-US'


class Base(object):
    _meta_exp = '.meta'
    _content_exp = '.yaml'
    _zendesk_id_key = 'id'
    meta_filename = ''
    content_filename = ''
    path = ''
    zendesk_group_list_prefix = ''

    def __init__(self, name, filename):
        super().__init__()
        self.name = name
        self.filename = filename
        self._meta = {}

    @property
    def meta(self):
        return self._meta
        
    @meta.setter
    def meta(self, value):
        self._meta = value or {}

    @property
    def zendesk_id(self):
        return self._meta.get(self._zendesk_id_key)

    @property
    def meta_filepath(self):
        return os.path.join(self.path, self.meta_filename + self._meta_exp)

    @property
    def content_filepath(self):
        return os.path.join(self.path, self.content_filename + self._content_exp)


class Group(Base):
    meta_filename = '.group'
    content_filename = '__group__'

    def __init__(self, name, description, filename):
        super().__init__(name, filename)
        self.description = description

    def to_content(self):
        return {
            'name': self.name,
            'description': self.description
        }

    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description
        }

    def to_translation(self):
        return {
            'title': self.name,
            'body': self.description
        }

    def paths(self):
        return [self.content_filepath]


class Category(Group):
    zendesk_name = 'category'
    zendesk_group = 'categories'

    def __init__(self, name, description, filename):
        super().__init__(name, description, filename)
        self.sections = []

    @property
    def path(self):
        return self.filename

    @staticmethod
    def from_dict(meta, content, filename):
        name = content['name']
        description = content.get('description', '')
        category = Category(name, description, filename)
        category.meta = meta
        return category

    @classmethod
    def filepaths_from_path(cls, path):
        meta_path = os.path.join(path, cls.meta_filename + cls._meta_exp)
        content_path = os.path.join(path, cls.content_filename + cls._content_exp)
        return meta_path, content_path

    @property
    def new_item_url(self):
        return 'categories.json'


class Section(Group):
    zendesk_name = 'section'
    zendesk_group = 'sections'

    def __init__(self, category, name, description, filename):
        super().__init__(name, description, filename)
        self.articles = []
        self.category = category

    @property
    def path(self):
        return os.path.join(self.category.path, self.filename)

    @classmethod
    def filepaths_from_path(cls, category, path):
        meta_path = os.path.join(category.path, path, cls.meta_filename + cls._meta_exp)
        content_path = os.path.join(category.path, path, cls.content_filename + cls._content_exp)
        return meta_path, content_path

    @staticmethod
    def from_dict(category, meta, content, filename):
        name = content['name']
        description = content.get('description', '')
        section = Section(category, name, description, filename)
        section.meta = meta
        return section

    @property
    def new_item_url(self):
        return 'categories/{}/sections.json'.format(self.category.zendesk_id)


class Article(Base):
    zendesk_name = 'article'
    zendesk_group = 'articles'

    body_filename = 'README.md'
    meta_filename = '.article'
    content_filename = '__article__'

    def __init__(self, section, name, body, filename):
        super().__init__(name, filename)
        self.attachments = {}
        self.body = body
        self.section = section

    @property
    def body_filepath(self):
        return os.path.join(self.path, self.body_filename)

    @property
    def path(self):
        return os.path.join(self.section.path, self.filename)

    def to_dict(self):
        return {
            'title': self.name
        }

    def to_translation(self):
        return {
            'title': self.name
        }

    def to_translation_incl_body(self):
        body = self.generate_body()
        return {
            'title': self.name,
            'body': body
        }

    def to_content(self):
        return {
            'name': self.name
        }

    def generate_body(self):
        body = self.body
        for _, attachment in self.attachments.items():
            zendesk_url = '('+attachment.meta['relative_path']
            regex = r'\((./|/)attachments/'+attachment.filename
            body = re.sub(regex, zendesk_url, body)

        body = markdown.markdown(body)
        return body

    def paths(self):
        return [self.content_filepath, self.body_filepath]

    @classmethod
    def filepaths_from_path(cls, section, name):
        path = os.path.join(section.path, name)
        meta_path = os.path.join(path, cls.meta_filename + cls._meta_exp)
        content_path = os.path.join(path, cls.content_filename + cls._content_exp)
        body_path = os.path.join(path, cls.body_filename)
        return meta_path, content_path, body_path

    @staticmethod
    def from_dict(section, meta, content, body, filename):
        article = Article(section, content['name'], body, filename)
        article.meta = meta
        return article

    @staticmethod
    def from_zendesk(zendesk_article, section):
        zendesk_body = zendesk_article.get('body', '')
        zendesk_body = '' if zendesk_body == None else zendesk_body
        body = html2text.html2text(zendesk_body)
        article_filename = utils.slugify(zendesk_article['title'])
        article = Article(section, zendesk_article['title'], body, article_filename)
        article.meta = zendesk_article
        return article

    @property
    def new_item_url(self):
        return 'sections/{}/articles.json'.format(self.section.zendesk_id)

class Attachment(Base):
    zendesk_name = 'attachment'
    zendesk_group = 'attachments'
    zendesk_group_list_prefix = 'article_'
    _meta_filename = '.{}'

    def __init__(self, article, filename):
        super().__init__(filename, filename)
        self.article = article

    @property
    def path(self):
        return os.path.join(self.article.path, 'attachments')

    @property
    def filepath(self):
        return os.path.join(self.path, self.filename)

    @property
    def meta_filename(self):
        return self._meta_filename.format(self.name)

    @staticmethod
    def from_dict(article, meta, filename):
        attachment = Attachment(article, filename)
        attachment.meta = meta
        return attachment

    @classmethod
    def filepaths_from_path(cls, article, filename):
        path = cls.path_from_article(article)
        meta_path = os.path.join(path, cls._meta_filename.format(filename) + cls._meta_exp)
        return meta_path

    @staticmethod
    def path_from_article(article):
        return os.path.join(article.path, 'attachments')

    @property
    def new_item_url(self):
        return 'articles/{}/attachments.json'.format(self.article.zendesk_id)
