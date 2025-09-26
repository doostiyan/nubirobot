import os
import json


def get_data(filename):
    """ Read a JSON test data from file and return it as a python object
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(dir_path, 'data', filename + '.json')) as data_file:
        return json.load(data_file)
