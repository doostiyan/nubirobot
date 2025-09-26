import os
import json
import re

from django.core.cache import cache


def get_data(filename):
    """ Read a JSON test data from file and return it as a python object
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(dir_path, 'data', filename + '.json')) as data_file:
        return json.load(data_file)


def mock_cache_keys(key_pattern):
    regex_pattern = key_pattern.replace('*', '.*')
    regex_pattern = cache.make_key(regex_pattern)
    all_keys = list(cache._cache.keys())
    key_prefix_len = len(cache.make_key(''))
    keys = {key[key_prefix_len:] for key in all_keys if re.search(regex_pattern, key)}
    return keys
