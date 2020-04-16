import logging
import requests
import json
import hashlib
from operator import attrgetter
import html2text
import os

import model
import utils

requests.packages.urllib3.disable_warnings()


class ZendeskRequest(object):
    _default_url = 'https://{}/api/v2/help_center/' + utils.to_zendesk_locale(model.DEFAULT_LOCALE) + '/{}'
    _translations_url = 'https://{}/api/v2/help_center/{}'
    _users_url = 'https://{}/api/v2/users/{}'
    _search_url = 'https://{}/api/v2/search.json'
    _user_segments_url = 'https://{}/api/v2/help_center/user_segments/applicable.json'
    _permission_groups_url = 'https://{}/api/v2/guide/permission_groups.json'

    item_url = '{}/{}.json'
    items_url = '{}.json?per_page=100'
    items_in_group_url = '{}/{}/{}.json?per_page=100'

    attachment_url = 'articles/attachments/{}.json'
    translation_url = '{}/{}/translations/{}.json'

    user_url = '{}.json'

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

    def _user_url_for(self, path):
        return self._users_url.format(self.company_uri, path)

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

    def get_user(self, uid):
        full_url = self._user_url_for(self.user_url.format(uid))
        response = requests.get(full_url,
                              auth=(self.user, self.password),
                              verify=False)
        return self._parse_response(response).get('user', {})

    def search_user(self, query):
        full_url = self._search_url.format(self.company_uri)
        response = requests.get(full_url,
                              params={'query': query},
                              auth=(self.user, self.password),
                              verify=False)
        results = self._parse_response(response).get('results', [])
        if len(results) == 0:
            return False
        else:
            uid = results[0]['id']
            return self.get_user(uid)

    def get_user_segments(self):
        full_url = self._user_segments_url.format(self.company_uri)
        response = requests.get(full_url,
                              auth=(self.user, self.password),
                              verify=False)
        return self._parse_response(response).get('user_segments', [])

    def get_permission_groups(self):
        full_url = self._permission_groups_url.format(self.company_uri)
        response = requests.get(full_url,
                              auth=(self.user, self.password),
                              verify=False)
        return self._parse_response(response).get('permission_groups', [])

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
        self.users = {}
        self.user_segments = {segment['id']: utils.slugify(segment['name']) for segment in self.req.get_user_segments()}
        self.user_segments[None] = 'all'

    def _get_user_by_uid(self, uid):
        if uid in self.users:
            return self.users[uid]
        else:
            user = self.req.get_user(uid)
            self.users[uid] = user
            return user

    def _get_group_attributes_and_filename(self, group):
        attributes = {
            'name': group['name'],
            'description': group['description']
        }
        filename = utils.slugify(group['name'])
        return attributes, filename

    def _instantiate_category(self, zendesk_category):
        attributes, filename = self._get_group_attributes_and_filename(zendesk_category)
        category = model.Category(attributes, filename)
        category.meta = zendesk_category
        return category

    def _instantiate_section(self, category, zendesk_section):
        attributes, filename = self._get_group_attributes_and_filename(zendesk_section)
        section = model.Section(category, attributes, filename)
        section.meta = zendesk_section
        return section

    def _instantiate_article(self, section, zendesk_article):
        user = self._get_user_by_uid(zendesk_article['author_id'])
        user_segment_id = zendesk_article.get('user_segment_id', None)
        attributes = {
            'name': zendesk_article['title'],
            'synced': False,
            'draft': zendesk_article['draft'],
            'author': user['email'],
            'visibility': self.user_segments[user_segment_id]
        }
        filename = utils.slugify(zendesk_article['title'])
        zendesk_body = zendesk_article.get('body', '')
        zendesk_body = '' if zendesk_body == None else zendesk_body
        body = html2text.html2text(zendesk_body)
        article = model.Article(section, attributes, body, filename)
        article.html = zendesk_body
        article.meta = zendesk_article
        article.meta.update(attributes)
        return article

    def _instantiate_attachment(self, article, zendesk_attachment):
        attachment = model.Attachment(article, zendesk_attachment['file_name'])
        attachment.meta = zendesk_attachment
        return attachment

    def fetch(self):
        categories = []
        zendesk_categories = self.req.get_items(model.Category)
        for zendesk_category in zendesk_categories:
            category = self._instantiate_category(zendesk_category)
            print('Category %s created' % category.name)
            zendesk_sections = self.req.get_items(model.Section, category)
            categories.append(category)
            for zendesk_section in zendesk_sections:
                section = self._instantiate_section(category, zendesk_section)
                print('Section %s created' % section.name)
                zendesk_articles = self.req.get_items(model.Article, section)
                category.sections.append(section)
                for zendesk_article in zendesk_articles:
                    article = self._instantiate_article(section, zendesk_article)
                    print('Article %s created' % article.name)
                    zendesk_attachments = self.req.get_items(model.Attachment, article)
                    section.articles.append(article)
                    for zendesk_attachment in zendesk_attachments:
                        attachment = self._instantiate_attachment(article, zendesk_attachment)
                        article.attachments[attachment.filename] = attachment
        return categories


class Pusher(object):

    def __init__(self, req, fs, disable_comments):
        self.req = req
        self.fs = fs
        self.disable_comments = False if disable_comments == 0 else True
        self.users = {}
        self.user_segments = {utils.slugify(segment['name']): segment['id'] for segment in self.req.get_user_segments()}
        self.user_segments['all'] = None
        self.permission_groups = {utils.slugify(segment['name']): segment['id'] for segment in self.req.get_permission_groups()}

    def _get_user_id_from_email(self, email):
        if email in self.users:
            return self.users[email]['id']
        else:
            query = 'type:user email:"'+email+'"'
            user = self.req.search_user(query)
            self.users[email] = user
            return user['id']

    def _have_attributes_changed(self, attributes, item):
        for key in attributes:
            zendesk_body = item.meta.get(key, '')
            zendesk_body = '' if zendesk_body == None else zendesk_body
            zendesk_hash = hashlib.md5(zendesk_body.encode('utf-8'))
            item_body = attributes.get(key, '')
            item_body = '' if item_body == None else item_body
            item_hash = hashlib.md5(item_body.encode('utf-8'))
            if zendesk_hash.hexdigest() != item_hash.hexdigest():
                print('key: %s meta: %s attribute: %s' %(key, zendesk_body, attributes[key]))
                return True
        return False

    def _push_new_article(self, article, parent=None):
        data = {article.zendesk_name: article.to_dict()}
        data['article']['user_segment_id'] = self.user_segments[article.visibility]
        data['article']['permission_group_id'] = self.permission_groups['agents-and-managers']
        data['article']['comments_disabled'] = self.disable_comments
        data['article']['section_id'] = article.section.zendesk_id
        data['article']['author_id'] = self._get_user_id_from_email(article.author)
        meta = self.req.post(article, data, parent)
        meta = self.fs.save_json(article.meta_filepath, meta)
        article.meta = meta

    def _push_group_translation(self, item):
        translation = item.to_translation()
        if self._have_attributes_changed(item.to_attributes(), item):
            logging.info('Updating translation')
            data = {'translation': translation}
            self.req.put_translation(item, data)
            meta = self.req.get_item(item)
            meta = self.fs.save_json(item.meta_filepath, meta)
            item.meta = meta

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
            data = {item.zendesk_name: item.to_dict()}
            meta = self.req.post(item, data, parent)
            meta = self.fs.save_json(item.meta_filepath, meta)
            item.meta = meta
        else:
            self._push_group_translation(item)
        if isinstance(item, model.Section):
            self._check_and_update_section_category(item)

    def _has_article_body_changed(self, article, generated_body):
        if generated_body == article.meta.get('generated_body', ''):
            return False
        return True

    def _check_and_update_article_translation(self, article, attachments_changed):
        data = {}
        translation_changed = False

        existing_draft_status = article.meta.get('draft', False)
        if article.draft != existing_draft_status:
            logging.info('Updating draft status for article %s from %s to %s' % (article.name, existing_draft_status, article.draft))
            data['draft'] = article.draft
            translation_changed = True

        existing_title = article.meta.get('title', '')
        if article.title != existing_title:
            logging.info('Updating article title for article %s from %s to %s' % (article.name, existing_title, article.title))
            data['title'] = article.title
            translation_changed = True
        
        body = article.generate_body()
        if attachments_changed or self._has_article_body_changed(article, body):
            logging.info('Updating article body for article %s' % (article.name))
            data['body'] = body
            translation_changed = True

        if translation_changed:
            self.req.put_translation(article, {'translation': data})
            translation = article.to_translation()
            translation['generated_body'] = body
            meta = self.req.get_item(article)
            meta.update(translation)            
            article.meta = self.fs.save_json(article.meta_filepath, meta)
            

    def _check_and_update_article_attributes(self, article):
        data = {}
        attributes_changed = False

        existing_section_id = article.meta.get('section_id', '')
        if article.section.zendesk_id != existing_section_id:
            logging.info('Updating section ID for article %s from %s to %s' % (article.name, existing_section_id, article.section.zendesk_id))
            data['section_id'] = article.section.zendesk_id
            attributes_changed = True
        
        existing_author = article.meta.get('author', '')
        if article.author != existing_author:
            logging.info('Updating author for article %s from %s to %s' % (article.name, existing_author, article.author))
            data['author_id'] = self._get_user_id_from_email(article.author)
            attributes_changed = True

        existing_visibility = article.meta.get('visibility', '')
        if article.visibility != existing_visibility:
            logging.info('Updating visibility for article %s from %s to %s' % (article.name, existing_visibility, article.visibility))
            data['user_segment_id'] = self.user_segments[article.visibility]
            attributes_changed = True

        if attributes_changed:
            meta = self.req.put(article, {'article':data})
            meta.update(article.to_attributes())
            article.meta = self.fs.save_json(article.meta_filepath, meta)

    def _push_article(self, article, section, attachments_changed):
        self._check_and_update_article_translation(article, attachments_changed)
        self._check_and_update_article_attributes(article)

    def _has_attachment_changed(self, attachment):
        attachment_full_path = self.fs.path_for(attachment.filepath)
        attachment_md5_hash = utils.md5_hash(attachment_full_path)
        if attachment_md5_hash == attachment.meta.get('md5_hash', ''):
            return False
        return True

    def _push_new_attachment(self, attachment):
        attachment_full_path = self.fs.path_for(attachment.filepath)
        meta = self.req.post_attachment(attachment, attachment_full_path)['article_attachment']
        meta['md5_hash']  = utils.md5_hash(attachment_full_path)
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
            logging.debug('Pushing category %s' % category.name)
            self._push_group(category)
            for section in category.sections:
                logging.debug('Pushing section %s' % section.name)
                self._push_group(section, category)
                for article in section.articles:
                    if article.synced == True:
                        if not article.zendesk_id:
                            self._push_new_article(article, section)
                        logging.debug('Pushing attachments for article %s' % article.name)
                        attachments_changed = False
                        for _, attachment in article.attachments.items():
                            if self._push_attachment(attachment):
                                attachments_changed = True
                        logging.debug('Pushing article %s' % article.name)
                        self._push_article(article, section, attachments_changed)
                    else:
                        logging.debug('Skipping un-synced article %s' % article.name)


class RecordNotFoundError(Exception):
    pass


def fetcher(company_uri, user, password):
    req = ZendeskRequest(company_uri, user, password)
    return Fetcher(req)

def pusher(company_uri, user, password, fs, disable_comments):
    req = ZendeskRequest(company_uri, user, password)
    return Pusher(req, fs, disable_comments)
