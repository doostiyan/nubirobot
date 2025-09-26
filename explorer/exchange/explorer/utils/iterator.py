from typing import List


def list_of_dicts2list_of_lists(list_of_dicts: List[dict]):
    list_of_lists = [list(d.values()) for d in list_of_dicts]
    return list_of_lists


def nested_dict2flat_dict(nested_dict: dict):
    flat_dict = {}
    for k, v in nested_dict.items():
        if isinstance(v, dict):
            flat_dict.update(nested_dict2flat_dict(v))
        else:
            flat_dict[k] = v
    return flat_dict


def list_of_nested_dict2list_of_flat_dict(list_of_nested_dict: List[dict]):
    return [nested_dict2flat_dict(item) for item in list_of_nested_dict]


def get_ordered_list_options(options):
    options_dict = {}
    for i, val in enumerate(options):
        index = i + 1
        options_dict[str(index)] = ('   {}) {}'.format(index, val))

    option_values = '\n'.join(options_dict.values())
    return option_values, options_dict
