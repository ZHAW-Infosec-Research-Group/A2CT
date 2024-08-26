"""
Utility functions for HTML and JSON preprocessing

Functions:
remove_tags
get_text_values
roll_out_json
get_key_value_pairs
roll_out_json_as_dict
roll_out_json_tuple_based
get_key_value_pairs_tuple_based
is_tuple
is_list_of_tuples
is_list_of_list_of_tuples
decode_as_list
"""


import logging
from bs4 import BeautifulSoup


def remove_tags(html, stripping_tags, prettify=True):
    """
    Generic stripping method that takes HTML and a list of CSS selectors that are then used to find and strip the tags from the HTML.
    Returns the stripped HTML.
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Couldn't parse HTML correctly, probably arbitrary bytes and not a string
        if soup.contains_replacement_characters:
            return html

        # Remove all tags found with the given list of selectors
        for selector in stripping_tags:
            [tag.decompose() for tag in soup.select(selector)]
        if prettify:
            return soup.prettify().encode()
        else:
            return soup.encode()
    except Exception as e:
        # input may have been arbitrary bytes
        logging.debug(e)
        return html


def get_text_values(html):
    """
    Get the text from an HTML input.
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Couldn't parse HTML correctly, probably arbitrary bytes and not a string
        if soup.contains_replacement_characters:
            return [html]

        texts = soup.get_text().splitlines()
        inputtags = soup.find_all('input', {type != "hidden"})
        values = []
        for tag in inputtags:
            value = tag.get('value')
            if (value is not None):
                values.append(value)
        joinedlist = texts + values
        stripped = list(filter(None, list(map(str.strip, joinedlist))))
        return stripped
    except Exception as e:
        # input may have been arbitrary bytes
        logging.debug(e)
        return [html]


# stripping method for JSON: Returns all key-value pairs as a rolled out list
def roll_out_json(json_data, debug):
    rolled_out_list = []
    if (type(json_data) == list):
        # json_data is a list of json data
        if (debug):
            logging.debug("Is a List")
            logging.debug(f'LEN: {len(json_data)}')
        for json_data_item in json_data:
            if (debug):
                logging.debug(f'ITEM: {json_data_item}')
                logging.debug(f'KEYS IN : {len(json_data_item.keys())}')
            for key in json_data_item.keys():
                if (debug):
                    logging.debug(f'KEY: {key}')
                rolled_out_list.extend(get_key_value_pairs("", key, json_data_item[key]))
    else:
        for key in json_data.keys():
            # json_data is just json data (not a list)
            rolled_out_list.extend(get_key_value_pairs("", key, json_data[key]))
    return rolled_out_list


def get_key_value_pairs(prefix_key, json_key, json_value):
    try:
        key_value_list = []
        if (type(json_value) == dict):
            for key in json_value.keys():
                key_value_list.extend(get_key_value_pairs(prefix_key + json_key + "_", key, json_value[key]))
        elif (type(json_value) == list):
            if (len(json_value) > 0):
                if (type(json_value[0]) == dict):
                    for dictitem in json_value:
                        for key in dictitem.keys():
                            key_value_list.extend(get_key_value_pairs(prefix_key + json_key + "_", key, dictitem[key]))
                else:
                    key_value_list.append(prefix_key + json_key + ":" + " ".join([str(n) for n in json_value]))
            else:
                key_value_list.append(prefix_key + json_key + ":")
        else:
            key_value_list.append(prefix_key + json_key + ":" + str(json_value))
        return key_value_list
    except Exception as inst:
        logging.debug(f'Exception during {inst}')


def roll_out_json_as_dict(json_data):
    """Converts JSON data into a rolled out dict

    Converts a rolled out json list from roll_out_json() into a dict parseable by parse_qs
    Made for parsing JSON request bodies that contain query strings in JSON format (objects) or
    lists of objects.
    Not all JSON is handled by this function as there is no meaningful way to convert e.g. flat
    or nested lists into dictionaries
    """
    rolled_out_list = roll_out_json_tuple_based(json_data, False)
    json_dict = {}
    for element in rolled_out_list:
        key = element.split(':')[0]
        value = element.split(':')[1]
        if json_dict.get(key) is None:
            json_dict[key] = [value]
        else:
            json_dict[key] = json_dict[key] + [value]
    return json_dict


def roll_out_json_tuple_based(json_data, debug):
    """Returns all key-value pairs as a rolled out list

    Achieves the same rolled out JSON like the roll_out_json function but takes JSON data that has
    been decoded with 'object_pairs_hook=decode_as_list' to allow for duplicate keys in the JSON
    """
    if type(json_data) == list:
        rolled_out_list = []
        # Iterate over the decoded JSON key-value pair list
        for json_data_item in json_data:
            if (type(json_data_item) == list):
                # JSON data is a list containing lists of tuples: [[(), ...], [(), ...], ...]
                # Iterate over sublist
                for element in json_data_item:
                    if is_tuple(element):
                        key = element[0]
                        value = element[1]
                        rolled_out_list.extend(get_key_value_pairs_tuple_based("", key, value))
                    else:
                        logging.debug(f"Couldn't parse JSON {json_data}")
                        raise ValueError("Unsupported JSON format")
            elif is_tuple(json_data_item):
                # JSON data is a list of tuples corresponding to the key-value pairs in a object: [(),(),(),...]
                key = json_data_item[0]
                value = json_data_item[1]
                rolled_out_list.extend(get_key_value_pairs_tuple_based("", key, value))
            else:
                # JSON data contained neiher a normal JSON object nor a list objects
                # i.e. flat or nested lists of single types like strings, booleans, ints etc. lead to this code path
                logging.debug(f"Couldn't parse JSON {json_data}")
                raise ValueError("Unsupported JSON format")
        return rolled_out_list
    else:
        logging.debug(f"Couldn't parse JSON {json_data}")
        raise ValueError("Unsupported JSON format")


def get_key_value_pairs_tuple_based(prefix_key, json_key, json_value):
    """Recursively evaluate key-value pairs and chain them together into strings to flatten the structure"""
    try:
        key_value_list = []
        # Check if value is itself an object (list of tuples)
        if is_list_of_tuples(json_value):
            for tuple in json_value:
                key = tuple[0]
                value = tuple[1]
                key_value_list.extend(get_key_value_pairs_tuple_based(prefix_key + json_key + "_", key, value))
        # Check if value is itself a list of objects (list containing lists of tuples)
        elif (type(json_value) == list):
            if (len(json_value) > 0):
                if (is_list_of_list_of_tuples(json_value)):
                    for sublist in json_value:
                        for tuple in sublist:
                            key = tuple[0]
                            value = tuple[1]
                            key_value_list.extend(get_key_value_pairs_tuple_based(prefix_key + json_key + "_", key, value))
                else:
                    # List doesn't contain list of tuples
                    key_value_list.append(prefix_key + json_key + ":" + " ".join([str(n) for n in json_value]))
            else:
                # List is empty
                key_value_list.append(prefix_key + json_key + ":")
        else:
            # Normal value
            key_value_list.append(prefix_key + json_key + ":" + str(json_value))
        return key_value_list
    except Exception:
        logging.debug(f"Couldn't parse JSON {json_value}")
        raise


def is_tuple(object):
    """Check if object is a 2-tuple (key-value pair)"""
    return isinstance(object, tuple) and len(object) == 2


def is_list_of_tuples(object):
    """Checks if object is a list of 2-tuples"""
    return type(object) == list and all([is_tuple(element) for element in object])


def is_list_of_list_of_tuples(object):
    """Checks if object is a list of lists of 2-tuples"""
    return type(object) == list and all([is_list_of_tuples(element) for element in object])


def decode_as_list(ordered_pairs):
    """Return key-value vairs in a list instead of a dict

    Makes json.loads() return a list of parsed JSON values instead of a dict if used
    as the optional object_pairs_hook= argument
    This allows us to keep the values of duplicate keys in the JSON data, as they would get overriden
    otherwise"""
    return ordered_pairs
