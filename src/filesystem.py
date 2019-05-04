import json
import yaml
import os
import logging
import re
import shutil

import model


class FilesystemClient(object):

    def __init__(self, root_folder):
        self.root_folder = root_folder

    def _path_for(self, path):
        return os.path.join(self.root_folder, path)

    def save_text(self, path, data):
        full_path = self._path_for(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as fp:
            fp.write(data)
        return data

    def read_text(self, path):
        full_path = self._path_for(path)
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
        text = yaml.dump(data)
        self.save_text(path, text)
        return data

    def read_yaml(self, path):
        text = self.read_text(path)
        if text:
            return yaml.load(text)
        else:
            return {}

    def read_directories(self, path):
        full_path = self._path_for(path)
        if os.path.exists(full_path):
            return [d for d in os.listdir(full_path) if os.path.isdir(os.path.join(full_path, d)) and not d.startswith('.')]
        else:
            return []

    def read_files(self, path):
        full_path = self._path_for(path)
        if os.path.exists(full_path):
            return [f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))]
        else:
            return []

    def remove(self, path):
        full_path = self._path_for(path)
        if os.path.exists(full_path):
            os.remove(full_path)

    def remove_dir(self, path):
        full_path = self._path_for(path)
        if os.path.exists(full_path):
            shutil.rmtree(full_path)

    def move(self, old_path, new_path):
        old_full_path = self._path_for(old_path)
        new_full_path = self._path_for(new_path)
        if os.path.exists(old_full_path):
            shutil.move(old_full_path, new_full_path)


class Saver(object):

    def __init__(self, fs):
        self.fs = fs

    def _save_item(self, item):
        self.fs.save_json(item.meta_filepath, item.meta)
        self.fs.save_json(item.content_filepath, item.to_content())

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


class Loader(object):

    def __init__(self, fs):
        self.fs = fs

    def _load_category(self, category_path):
        category_name = os.path.basename(category_path)
        meta_path, content_path = model.Category.filepaths_from_path(category_path)
        meta = self.fs.read_json(meta_path)
        content = self.fs.read_json(content_path)
        content = content or {'name': os.path.basename(category_path)}
        return model.Category.from_dict(meta, content, category_name)

    def _load_section(self, category, section_name):
        meta_path, content_path = model.Section.filepaths_from_path(category, section_name)
        meta = self.fs.read_json(meta_path)
        content = self.fs.read_json(content_path)
        content = content or {'name': section_name}
        return model.Section.from_dict(category, meta, content, section_name)

    def _load_article(self, section, article_name):
        meta_path, content_path, body_path = model.Article.filepaths_from_path(section, article_name)
        meta = self.fs.read_json(meta_path)
        content = self.fs.read_json(content_path)
        content = content or {'name': article_name}
        body = self.fs.read_text(body_path)
        return model.Article.from_dict(section, meta, content, body, article_name)

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

    def load(self):
        categories = []
        for category_name in self.fs.read_directories(self.fs.root_folder):
            category = self._fill_category(category_name)
            categories.append(category)
        return categories

    def load_from_path(self, path):
        path = path.rstrip()
        if os.path.relpath(self.fs.root_folder, path) == '..':
            return self._fill_category(os.path.basename(path))
        elif os.path.relpath(self.fs.root_folder, path) == '../..':
            section_name = os.path.basename(path)
            category_path = os.path.dirname(path)
            category = self._load_category(category_path)
            section = self._load_section(category, section_name)
            self._fill_articles(section)
            return section
        elif os.path.relpath(self.fs.root_folder, path) == '../../..':
            article_name = os.path.basename(path)
            section_path = os.path.dirname(path)
            section_name = os.path.basename(section_path)
            category_path = os.path.dirname(section_path)
            category = self._load_category(category_path)
            section = self._load_section(category, section_name)
            article = self._load_article(section, article_name)
            return article
        else:
            return



class Remover(object):

    def __init__(self, fs):
        self.fs = fs

    def remove(self, item):
        self.fs.remove_dir(item.path)


class Mover(object):

    def __init__(self, fs):
        self.fs = fs

    def move(self, item, dest):
        self.fs.move(item.path, dest)


class Doctor(object):

    def __init__(self, fs):
        self.fs = fs

    def _fix_item_content(self, item):
        if not os.path.exists(item.content_filepath):
            print('Missing content file {} created'.format(item.content_filepath))
            content = item.to_content()
            for key, value in content.items():
                new_value = input('Please provide a {} for this item (default: {}):'.format(key, value))
                new_value = new_value or value
                content[key] = new_value
            self.fs.save_json(item.content_filepath, content)
        # else:
        #     content = self.fs.read_json(item.content_filepath)
        #     if 'name' not in content:
        #         print('Content {} is invalid'.format(item.content_filepath))
        #         item_content = item.to_content()
        #         for key, value in item_content.items():
        #             new_value = input('Please provide a {} for this item (default: {})'.format(key, value))
        #             new_value = new_value or value
        #             item_content[key] = new_value
        #         self.fs.save_json(item.content_filepath, item_content)

    def fix(self, categories):
        for category in categories:
            self._fix_item_content(category)
            for section in category.sections:
                self._fix_item_content(section)
                for article in section.articles:
                    self._fix_item_content(article)


def saver(root_folder):
    fs = FilesystemClient(root_folder)
    return Saver(fs)


def loader(root_folder):
    fs = FilesystemClient(root_folder)
    return Loader(fs)


def remover(root_folder):
    fs = FilesystemClient(root_folder)
    return Remover(fs)


def mover(root_folder):
    fs = FilesystemClient(root_folder)
    return Mover(fs)


def doctor(root_folder):
    fs = FilesystemClient(root_folder)
    return Doctor(fs)


def client(root_folder):
    return FilesystemClient(root_folder)
