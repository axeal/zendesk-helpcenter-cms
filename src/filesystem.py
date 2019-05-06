import json
import yaml
import os
import logging
import re
import shutil

import model
import utils


class FilesystemClient(object):

    def __init__(self, root_folder):
        self.root_folder = root_folder

    def path_for(self, path):
        return os.path.join(self.root_folder, path)

    def save_text(self, path, data):
        full_path = self.path_for(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as fp:
            fp.write(data)
        return data

    def read_text(self, path):
        full_path = self.path_for(path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as fp:
                return fp.read()
        else:
            return ''

    def save_json(self, path, data):
        if os.path.exists(path):
            new_data = data
            data = self.read_json(path)
            data.update(new_data)
        text = json.dumps(data, indent=4, sort_keys=True)
        self.save_text(path, text)
        return data

    def read_json(self, path):
        text = self.read_text(path)
        if text:
            return json.loads(text)
        else:
            return {}

    def save_yaml(self, path, data):
        if os.path.exists(path):
            new_data = data
            data = self.read_yaml(path)
            data.update(new_data)
        text = yaml.dump(data, width=float("inf"))
        self.save_text(path, text)
        return data

    def read_yaml(self, path):
        text = self.read_text(path)
        if text:
            return yaml.load(text, Loader=yaml.FullLoader)
        else:
            return {}

    def read_directories(self, path):
        full_path = self.path_for(path)
        if os.path.exists(full_path):
            return [d for d in os.listdir(full_path) if os.path.isdir(os.path.join(full_path, d)) and not d.startswith('.')]
        else:
            return []

    def read_files(self, path):
        full_path = self.path_for(path)
        if os.path.exists(full_path):
            return [f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))]
        else:
            return []

    def remove(self, path):
        full_path = self.path_for(path)
        if os.path.exists(full_path):
            os.remove(full_path)

    def remove_dir(self, path):
        full_path = self.path_for(path)
        if os.path.exists(full_path):
            shutil.rmtree(full_path)

    def move(self, old_path, new_path):
        old_full_path = self.path_for(old_path)
        new_full_path = self.path_for(new_path)
        if os.path.exists(old_full_path):
            shutil.move(old_full_path, new_full_path)


class Saver(object):

    def __init__(self, fs, zd):
        self.fs = fs
        self.zd = zd

    def _save_item(self, item):
        self.fs.save_json(item.meta_filepath, item.meta)
        self.fs.save_yaml(item.attributes_filepath, item.to_attributes())

    def _save_attachment(self, attachment):
        attachment_path = self.fs.path_for(attachment.filepath)
        self.zd.get_attachment(attachment.meta['relative_path'], attachment_path)
        attachment.meta['md5_hash'] = utils.md5_hash(attachment_path)
        self.fs.save_json(attachment.meta_filepath, attachment.meta)

    def save(self, categories):
        for category in categories:
            self._save_item(category)
            logging.info('Category %s saved' % category.name)
            for section in category.sections:
                self._save_item(section)
                logging.info('Section %s saved' % section.name)
                for article in section.articles:
                    self._save_item(article)
                    logging.info('Article %s saved' % article.name)
                    self.fs.save_text(article.body_filepath, article.body)
                    self.fs.save_text(article.html_filepath, article.html)
                    for _, attachment in article.attachments.items():
                        self._save_attachment(attachment)
                        logging.info('Attachment %s saved' % attachment.name)


class Loader(object):

    def __init__(self, fs):
        self.fs = fs

    def _load_category(self, category_path):
        category_name = os.path.basename(category_path)
        meta_path, attributes_path = model.Category.filepaths_from_path(category_path)
        meta = self.fs.read_json(meta_path)
        attributes = self.fs.read_yaml(attributes_path)
        attributes =  {
            'name': attributes.get('name', os.path.basename(category_path)),
            'description': attributes.get('description', '')
        }
        return model.Category.from_dict(meta, attributes, category_name)

    def _load_section(self, category, section_name):
        meta_path, attributes_path = model.Section.filepaths_from_path(category, section_name)
        meta = self.fs.read_json(meta_path)
        attributes = self.fs.read_yaml(attributes_path)
        attributes = {
            'name': attributes.get('name', section_name),
            'description': attributes.get('description', '')
        }
        return model.Section.from_dict(category, meta, attributes, section_name)

    def _load_article(self, section, article_name):
        meta_path, attributes_path, body_path = model.Article.filepaths_from_path(section, article_name)
        meta = self.fs.read_json(meta_path)
        attributes = self.fs.read_yaml(attributes_path)
        attributes = {
            'name': attributes.get('name', article_name),
            'synced': attributes.get('synced', True),
            'draft': attributes.get('draft', True)
        }
        body = self.fs.read_text(body_path)
        return model.Article.from_dict(section, meta, attributes, body, article_name)

    def _load_attachment(self, article, attachment_name):
        meta_path = model.Attachment.filepaths_from_path(article, attachment_name)
        meta = self.fs.read_json(meta_path)
        return model.Attachment.from_dict(article, meta, attachment_name)
    
    def _filter_attachment_names(self, files):
        return [a for a in files if not a.endswith(model.Attachment._meta_exp) and not a.startswith('.')]

    def _fill_category(self, category_name):
        category = self._load_category(os.path.join(self.fs.root_folder, category_name))
        self._fill_sections(category)
        return category

    def _fill_sections(self, category):
        for section_name in self.fs.read_directories(category.path):
            section = self._load_section(category, section_name)
            category.sections.append(section)
            self._fill_articles(section)

    def _fill_articles(self, section):
        for article_name in self.fs.read_directories(section.path):
            article = self._load_article(section, article_name)
            section.articles.append(article)
            self._fill_attachments(article)

    def _fill_attachments(self, article):
        attachments_path = model.Attachment.path_from_article(article)
        attachment_names = self._filter_attachment_names(self.fs.read_files(attachments_path))
        for attachment_name in attachment_names:
            attachment = self._load_attachment(article, attachment_name)
            article.attachments[attachment_name] = attachment

    def load(self):
        categories = []
        for category_name in self.fs.read_directories(self.fs.root_folder):
            category = self._fill_category(category_name)
            categories.append(category)
        return categories


def saver(root_folder, zendesk_client=None):
    fs = FilesystemClient(root_folder)
    return Saver(fs, zendesk_client)


def loader(root_folder):
    fs = FilesystemClient(root_folder)
    return Loader(fs)


def client(root_folder):
    return FilesystemClient(root_folder)
