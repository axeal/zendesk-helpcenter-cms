import argparse
import os
import logging
import configparser

import zendesk
import filesystem

DEFAULE_LOG_LEVEL = 'WARNING'
CONFIG_FILE = 'zendesk-help-cms.config'


class ImportTask(object):

    def execute(self, args):
        logging.info('Running import task...')
        categories = zendesk.fetcher(args['company_uri'], args['user'], args['password']).fetch()
        zendesk_client = zendesk.ZendeskRequest(args['company_uri'], args['user'], args['password'], args['public_uri'])
        filesystem.saver(args['root_folder'], zendesk_client).save(categories)
        logging.info('Import task completed')


class ExportTask(object):

    def execute(self, args):
        logging.info('Running export task...')
        categories = filesystem.loader(args['root_folder']).load()
        filesystem_client = filesystem.client(args['root_folder'])
        zendesk.pusher(args['company_uri'], args['user'], args['password'],
                       filesystem_client, args['disable_article_comments']).push(categories)
        logging.info('Export task completed')


class ConfigTask(object):

    """
    Creates config file in the current directory by asking a user to provide the data.
    """

    def _read_existing_config(self):
        if not os.path.exists(CONFIG_FILE):
            return {}

        print('There is a config alread present, press ENTER to accept already existing value')
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        return dict(config[config.default_section])

    def _read_config_from_input(self, default_config):
        if default_config:
            default_company_uri = default_config.get('company_uri', '')
            company_uri = input('Zendesk\'s company uri (for example test_company.zendesk.com) ({}):'.format(default_company_uri)) or default_company_uri
            default_user = default_config.get('user', '')
            user = input('Zendesk\'s user name ({}):'.format(default_user)) or default_user
            default_password = default_config.get('password', '')
            password = input('Zendesk\'s password ({}):'.format(default_password)) or default_password
            default_disable_article_comments = default_config.get('disable_article_comments', '')
            disable_article_comments = input('Disable article comments ({}):'.format(default_disable_article_comments))
            disable_article_comments = disable_article_comments or default_disable_article_comments
        else:
            company_uri = input('Zendesk\'s company uri:')
            user = input('Zendesk\'s user name:')
            password = input('Zendesk\'s password:')
            disable_article_comments = input('Disable article comments:')

        return {
            'company_uri': company_uri,
            'user': user,
            'password': password,
            'disable_article_comments': disable_article_comments
        }

    def execute(self, args):
        existing_config = self._read_existing_config()
        user_config = self._read_config_from_input(existing_config)

        config = configparser.ConfigParser()
        config[config.default_section] = user_config

        with open(CONFIG_FILE, 'w') as config_file:
            config.write(config_file)

tasks = {
    'import': ImportTask(),
    'export': ExportTask(),
    'config': ConfigTask()
}


def parse_args():
    parser = argparse.ArgumentParser()

    # Subparsers
    subparsers = parser.add_subparsers(help='Task to be performed.', dest='task')
    for task_parser in tasks:
        subparsers.add_parser(task_parser)

    # Global settings
    parser.add_argument('-l', '--loglevel',
                        help='Specify log level (DEBUG, INFO, WARNING, ERROR, CRITICAL), default: %s'
                        % DEFAULE_LOG_LEVEL,
                        default=DEFAULE_LOG_LEVEL)
    parser.add_argument('-r', '--root_folder',
                        help='Article\'s root folder, default: .',
                        default=os.getcwd())
    parser.add_argument('-f', '--force', help='Don\'t ask questions. YES all the way',
                        action='store_true', default=False)
    parser.add_argument('-v', '--version', help='Show version', action='store_true')

    return parser.parse_args()


def init_log(loglevel):
    num_level = getattr(logging, loglevel.upper(), 'WARNING')
    logging.basicConfig(level=num_level)


def parse_config(args):
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    options = dict(config[config.default_section])
    options.update(vars(args))
    options['disable_article_comments'] = bool(options.get('disable_article_comments', False))
    return options


def main():
    args = parse_args()
    if args.version:
        import pkg_resources
        version = pkg_resources.require('zendesk-helpcenter-cms')[0].version
        print(version)
        return
    init_log(args.loglevel)
    options = parse_config(args)
    task_name = options.get('task')
    if task_name:
        task = tasks[task_name]
        task.execute(options)
    else:
        print('No task provided, run with -h to see available options')


if __name__ == '__main__':
    main()
