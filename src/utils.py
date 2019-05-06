import unicodedata
import re
import hashlib

BLOCKSIZE = 65536

def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and underscores) and converts spaces to
    hyphens. Also strips leading and trailing whitespace.
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)


def to_zendesk_locale(locale):
    return locale.lower()


def to_iso_locale(locale):
    if '-' in locale:
        first, second = locale.split('-')
        return first + '-' + second.upper()
    else:
        return locale

def md5_hash(path):
    hasher = hashlib.md5()
    with open(path, 'rb') as f:
        buf = f.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(BLOCKSIZE)
    return hasher.hexdigest()