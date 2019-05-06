import logging
import requests
import json
import hashlib
from operator import attrgetter
import os

import model
import utils

requests.packages.urllib3.disable_warnings()


class ZendeskRequest(object):
    _default_url = 'https://{}/api/v2/help_center/' + utils.to_zendesk_locale(model.DEFAULT_LOCALE) + '/{}'
    _translations_url = 'https://{}/api/v2/help_center/{}'

    item_url = '{}/{}.json'
    items_url = '{}.json?per_page=100'
    items_in_group_url = '{}/{}/{}.json?per_page=100'

    attachment_url = 'articles/attachments/{}.json'
    translation_url = '{}/{}/translations/{}.json'

    def __init__(self, company_uri, user, password, public_uri=None):
        super().__init__()
        self.company_uri = company_uri
        self.user = user
        self.password = password
        self.public_uri = public_uri

    def _url_for(self, path):
        return self._default_url.format(self.company_uri, path)

    def _translation_url_for(self, path):
        return self._translations_url.format(self.company_uri, path)

    def _parse_response(self, response):
        if response.status_code == 404:
            raise RecordNotFoundError('Missing record for {}'.format(response.url))
        if response.status_code not in [200, 201]:
            logging.error('getting data from %s failed. status was %s and message %s',
                          response.url, response.status_code, response.text)
            return {}
        return response.json()

    def _send_request(self, request_fn, url, data):
        full_url = self._url_for(url)
        response = request_fn(full_url, data=json.dumps(data),
                              auth=(self.user, self.password),
                              headers={'Content-type': 'application/json'},
                              verify=False)
        return self._parse_response(response)

    def _send_translation(self, request_fn, url, data):
        full_url = self._translation_url_for(url)
        response = request_fn(full_url, data=json.dumps(data),
                              auth=(self.user, self.password),
                              headers={'Content-type': 'application/json'},
                              verify=False)
        return self._parse_response(response)

    def get_item(self, item):
        url = self.item_url.format(item.zendesk_group, item.zendesk_id)
        full_url = self._url_for(url)
        response = requests.get(full_url, auth=(self.user, self.password), verify=False)
        return self._parse_response(response).get(item.zendesk_name, {})

    def get_items(self, item, parent=None):
        if parent:
            url = self.items_in_group_url.format(parent.zendesk_group, parent.zendesk_id, item.zendesk_group)
        else:
            url = self.items_url.format(item.zendesk_group)
        full_url = self._url_for(url)
        response = requests.get(full_url, auth=(self.user, self.password), verify=False)
        return self._parse_response(response).get(item.zendesk_group_list_prefix + item.zendesk_group, {})

    def get_translation(self, item):
        url = self.translation_url.format(item.zendesk_group, item.zendesk_id, model.DEFAULT_LOCALE)
        full_url = self._translation_url_for(url)
        response = requests.get(full_url, auth=(self.user, self.password), verify=False)
        return self._parse_response(response).get('translation', {})

    def put(self, item, data):
        url = self.item_url.format(item.zendesk_group, item.zendesk_id)
        return self._send_request(requests.put, url, data).get(item.zendesk_name, {})

    def put_translation(self, item, data):
        url = self.translation_url.format(item.zendesk_group, item.zendesk_id, model.DEFAULT_LOCALE)
        return self._send_translation(requests.put, url, data).get('translation', {})

    def post(self, item, data, parent=None):
        if parent:
            url = self.items_in_group_url.format(parent.zendesk_group, parent.zendesk_id, item.zendesk_group)
        else:
            url = self.items_url.format(item.zendesk_group)
        return self._send_request(requests.post, url, data).get(item.zendesk_name, {})

    def post_attachment(self, attachment, attachment_filepath):
        full_url = self._url_for(attachment.new_item_url)
        response = requests.post(full_url, 
                              data={'inline': 'true'},
                              files={'file': open(attachment_filepath, 'rb')},
                              auth=(self.user, self.password),
                              verify=False)
        return self._parse_response(response)

    def get_attachment(self, relative_path, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = 'https://' + self.public_uri + relative_path
        response = requests.get(url, stream=True, auth=(self.user, self.password))
        if response.status_code == 200:
            with open(path, 'wb') as file:
                for chunk in response:
                    file.write(chunk)
            return True
        else:
            return False

    def delete(self, item):
        if isinstance(item, model.Attachment):
            url = self.attachment_url.format(item.zendesk_id)
        else:
            url = self.item_url.format(item.zendesk_group, item.zendesk_id)
        full_url = self._url_for(url)
        return self.raw_delete(full_url)

    def raw_delete(self, full_url):
        response = requests.delete(full_url, auth=(self.user, self.password), verify=False)
        return response.status_code == 200


class Fetcher(object):

    def __init__(self, req):
        super().__init__()
        self.req = req

    def fetch(self):
        categories = []
        zendesk_categories = self.req.get_items(model.Category)
        for zendesk_category in zendesk_categories:
            category_filename = utils.slugify(zendesk_category['name'])
            category = model.Category(zendesk_category['name'], zendesk_category['description'], category_filename)
            print('Category %s created' % category.name)
            category.meta = zendesk_category
            zendesk_sections = self.req.get_items(model.Section, category)
            categories.append(category)
            for zendesk_section in zendesk_sections:
                section_filename = utils.slugify(zendesk_section['name'])
                section = model.Section(category, zendesk_section['name'],
                                        zendesk_section['description'], section_filename)
                print('Section %s created' % section.name)
                section.meta = zendesk_section
                zendesk_articles = self.req.get_items(model.Article, section)
                category.sections.append(section)
                for zendesk_article in zendesk_articles:
                    article = model.Article.from_zendesk(zendesk_article, section)
                    print('Article %s created' % article.name)
                    zendesk_attachments = self.req.get_items(model.Attachment, article)
                    section.articles.append(article)
                    for zendesk_attachment in zendesk_attachments:
                        attachment = model.Attachment(article, zendesk_attachment['file_name'])
                        attachment.meta = zendesk_attachment
                        article.attachments[attachment.filename] = attachment
        return categories


class Pusher(object):

    def __init__(self, req, fs, disable_comments):
        self.req = req
        self.fs = fs
        self.disable_comments = disable_comments

    def _have_attributes_changed(self, translation, item):
        zendesk_attributes = self.req.get_translation(item)
        for key in translation:
            zendesk_body = zendesk_attributes.get(key, '')
            zendesk_body = '' if zendesk_body == None else zendesk_body
            zendesk_hash = hashlib.md5(zendesk_body.encode('utf-8'))
            item_hash = hashlib.md5(translation[key].encode('utf-8'))
            if zendesk_hash.hexdigest() != item_hash.hexdigest():
                return True
        return False

    def _push_new_item(self, item, parent=None):
        data = {item.zendesk_name: item.to_dict()}
        meta = self.req.post(item, data, parent)
        meta = self.fs.save_json(item.meta_filepath, meta)
        item.meta = meta

    def _push_item_translation(self, item):
        translation = item.to_translation()
        if self._have_attributes_changed(translation, item):
            print('Updating translation')
            data = {'translation': translation}
            self.req.put_translation(item, data)
        else:
            print('Nothing changed')

    def _check_and_update_section_category(self, section):
        existing_category_id = section.meta.get('category_id', '')
        if section.category.zendesk_id != existing_category_id:
            logging.info('Updating category ID for section %s from %s to %s' % (section.name, existing_category_id, section.category.zendesk_id))
            data = {'category_id': section.category.zendesk_id}
            meta = self.req.put(section, data)
            meta = self.fs.save_json(section.meta_filepath, meta)
            section.meta = meta

    def _push_group(self, item, parent=None):
        if not item.zendesk_id:
            self._push_new_item(item, parent)
        else:
            self._push_item_translation(item)
        if isinstance(item, model.Section):
            self._check_and_update_section_category(item)

    def _has_article_body_changed(self, article):
        article_body_full_path = self.fs.path_for(article.body_filepath)
        article_md5_hash = utils.md5_hash(article_body_full_path)
        if article_md5_hash == article.meta.get('md5_hash', ''):
            return False
        return True

    def _push_new_article_translation(self, article):
        translation = article.to_translation_incl_body()
        data = {'translation': translation}
        self.req.put_translation(article, data)
        article_body_full_path = self.fs.path_for(article.body_filepath)
        article_md5_hash = utils.md5_hash(article_body_full_path)
        article.meta['md5_hash'] = article_md5_hash
        article.meta = self.fs.save_json(article.meta_filepath, article.meta)

    def _check_and_update_article_section(self, article):
        existing_section_id = article.meta.get('section_id', '')
        if article.section.zendesk_id != existing_section_id:
            logging.info('Updating section ID for article %s from %s to %s' % (article.name, existing_section_id, article.section.zendesk_id))
            data = {'section_id': article.section.zendesk_id}
            meta = self.req.put(article, data)
            meta = self.fs.save_json(article.meta_filepath, meta)
            article.meta = meta

    def _push_article(self, article, section, attachments_changed):
        if attachments_changed or self._has_article_body_changed(article):
            self._push_new_article_translation(article)
        self._check_and_update_article_section(article)

    def _has_attachment_changed(self, attachment):
        attachment_full_path = self.fs.path_for(attachment.filepath)
        attachment_md5_hash = utils.md5_hash(attachment_full_path)
        if attachment_md5_hash == attachment.meta.get('md5_hash', ''):
            return False
        return True

    def _push_new_attachment(self, attachment):
        attachment_full_path = self.fs.path_for(attachment.filepath)
        meta = self.req.post_attachment(attachment, attachment_full_path)['article_attachment']
        attachment_md5_hash = utils.md5_hash(attachment_full_path)
        meta['md5_hash'] = attachment_md5_hash
        meta = self.fs.save_json(attachment.meta_filepath, meta)
        attachment.meta = meta
    
    def _push_attachment(self, attachment):
        if not attachment.zendesk_id:
            self._push_new_attachment(attachment)
            return True
        elif self._has_attachment_changed(attachment):
            self.req.delete(attachment)
            self._push_new_attachment(attachment)
            return True
        return False

    def push(self, categories):
        for category in categories:
            print('Pushing category %s' % category.name)
            self._push_group(category)
            for section in category.sections:
                print('Pushing section %s' % section.name)
                self._push_group(section, category)
                for article in section.articles:
                    if not article.zendesk_id:
                        self._push_new_item(article, section)
                    print('Pushing attachments for article %s' % article.name)
                    attachments_changed = False
                    for _, attachment in article.attachments.items():
                        if self._push_attachment(attachment):
                            attachments_changed = True
                    print('Pushing article %s' % article.name)
                    self._push_article(article, section, attachments_changed)


class RecordNotFoundError(Exception):
    pass


def fetcher(company_uri, user, password):
    req = ZendeskRequest(company_uri, user, password)
    return Fetcher(req)

def pusher(company_uri, user, password, fs, disable_comments):
    req = ZendeskRequest(company_uri, user, password)
    return Pusher(req, fs, disable_comments)
