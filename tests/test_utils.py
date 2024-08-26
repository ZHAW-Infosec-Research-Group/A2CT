"""
Tests for utils.py and html_json_utils.py
"""


import uuid
import random
import json
import pytest
from modules.utils import deduplicate_dicts, is_json
from modules.html_json_utils import (remove_tags, get_text_values, roll_out_json, roll_out_json_as_dict, decode_as_list)


def test_deduplicate_dicts():
    test_dict_1 = {}
    test_dict_2 = {}
    test_dict_3 = {}
    test_dict_4 = {}

    test_dict_1['test'] = 'test_value'
    test_dict_2['test'] = 'test_value'
    test_dict_3['test'] = 'test_value'
    test_dict_4['test'] = 'test_value'

    for i in range(20):
        random_key_1 = uuid.uuid1()
        random_value_1 = random.randint(0, 100)
        test_dict_1[str(random_key_1)] = str(random_value_1)

        random_key_2 = uuid.uuid1()
        random_value_2 = random.randint(0, 100)

        test_dict_2[str(random_key_2)] = str(random_value_2)

        random_key_3 = uuid.uuid1()
        random_value_3 = random.randint(0, 100)

        test_dict_3[str(random_key_3)] = str(random_value_3)

        random_key_4 = uuid.uuid1()
        random_value_4 = random.randint(0, 100)

        test_dict_4[str(random_key_4)] = str(random_value_4)

    result_dict = deduplicate_dicts([test_dict_1, test_dict_2, test_dict_3, test_dict_4])

    assert len(result_dict) == 81


def test_remove_tags():

    # Replaces old test_remove_tags_meta_script_link test (stripping method 1)
    test_html = '<html><meta><script>console.log("hello world")</script><link><body><p>test text </p><aside>aside </aside><nav>nav </nav><header>header </header><footer>footer </footer><body></html>'
    selectors = ['meta', 'script', 'link']
    result = remove_tags(test_html, selectors).decode('utf-8')
    assert '<meta>' not in result
    assert '<script>' not in result
    assert '<link>' not in result
    assert 'console' not in result
    assert '<aside>' in result
    assert '<nav>' in result
    assert '<header>' in result
    assert '<footer>' in result
    assert 'test text' in result

    # Replaces old test_remove_tags_meta_script_link_aside_nav_header_footer test (stripping method 2)
    test_html = '<html><meta><script>console.log("hello world")</script><link><body><p>test </p><aside>aside </aside><nav>nav </nav><header>header </header><footer>footer </footer><body></html>'
    selectors = ['meta', 'script', 'link', 'aside', 'nav', 'header', 'footer']
    result = remove_tags(test_html, selectors).decode('utf-8')
    assert '<meta>' not in result
    assert '<script>' not in result
    assert '<link>' not in result
    assert '<aside>' not in result
    assert '<nav>' not in result
    assert '<header>' not in result
    assert '<footer>' not in result
    assert 'console' not in result
    assert 'aside' not in result
    assert 'nav' not in result
    assert 'header' not in result
    assert 'footer' not in result
    assert 'test' in result

    # Replaces old test_remove_tags_meta_script_link_get_text_values test (stripping method 3)
    test_html = '<html><meta><script>console.log("hello world")</script><link><body><p>test text </p><aside>aside </aside><nav>nav </nav><header>header </header><footer>footer </footer><body></html>'
    selectors = ['meta', 'script', 'link']
    stripped_result = remove_tags(test_html, selectors, prettify=False)
    result = get_text_values(stripped_result)
    assert result == ['test text aside nav header footer']

    # Replaces old remove_tags_meta_script_link_aside_nav_header_footer_get_texts_values test (stripping method 4)
    # Default selectors
    test_html = '''
                <html>
                <meta>
                <script>console.log("hello world")</script>
                <link>
                <body>
                    <p>test text</p>
                    <aside>aside </aside>
                    <nav>nav </nav>
                    <header>header </header>
                    <footer>footer </footer>
                    <ul class='nav flex-column pt-4'>
                        <li>1</li>
                        <li>2</li>
                        <li>3</li>
                    </ul>
                    <aside class='main-sidebar'>aside</aside>
                    <div class='box-tools'
                        <p>my box-tools div</p>
                    </div>
                    <div class='hidden-xs'
                        <p>my hidden-xs div</p>
                    </div>
                    <body>
                </html>
                '''
    selectors = ['meta', 'script', 'link', 'aside', 'nav', 'header', 'footer']
    stripped_result = remove_tags(test_html, selectors, prettify=False)
    result = get_text_values(stripped_result)
    assert result == ['test text', '1', '2', '3', 'my box-tools div', 'my hidden-xs div']

    # Custom Test app 1 selectors
    test_html = '''
                <html>
                <meta>
                <script>console.log("hello world")</script>
                <link>
                <body>
                    <p>test text</p>
                    <aside>aside </aside>
                    <nav>nav </nav>
                    <header>header </header>
                    <footer>footer </footer>
                    <ul class='nav flex-column pt-4'>
                        <li>1</li>
                        <li>2</li>
                        <li>3</li>
                    </ul>
                    <aside class='main-sidebar'>aside</aside>
                    <div class='box-tools'
                        <p>my box-tools div</p>
                    </div>
                    <div class='hidden-xs'
                        <p>my hidden-xs div</p>
                    </div>
                    <body>
                </html>
                '''
    selectors = ['meta', 'script', 'link', 'aside', 'nav', 'header', 'footer', 'ul.nav.flex-column.pt-4', 'aside.main-sidebar', 'div.box-tools', 'div.hidden-xs']
    stripped_result = remove_tags(test_html, selectors)
    result = get_text_values(stripped_result)
    assert result == ["test text"]

    # <select> test non-prettified input, prettify=False
    test_html = '''<select id="state" name="state" class="selectpicker form-control" data-width="100%" data-minimum-results-for-search="Infinity"><option value="1" selected="selected">All</option><option value="2">Active</option><option value="3">Stopped</option></select>'''
    selectors = ['meta', 'script', 'link', 'aside', 'nav', 'header', 'footer', 'ul.nav.flex-column.pt-4', 'aside.main-sidebar', 'div.box-tools', 'div.hidden-xs']
    stripped_result = remove_tags(test_html, selectors, prettify=False)
    result = get_text_values(stripped_result)
    assert result == ['AllActiveStopped']

    # <select> test non-prettified input, prettify=True
    test_html = '''<select id="state" name="state" class="selectpicker form-control" data-width="100%" data-minimum-results-for-search="Infinity"><option value="1" selected="selected">All</option><option value="2">Active</option><option value="3">Stopped</option></select>'''
    selectors = ['meta', 'script', 'link', 'aside', 'nav', 'header', 'footer', 'ul.nav.flex-column.pt-4', 'aside.main-sidebar', 'div.box-tools', 'div.hidden-xs']
    stripped_result = remove_tags(test_html, selectors, prettify=True)
    result = get_text_values(stripped_result)
    assert result == ['All', 'Active', 'Stopped']

    # <select> test prettified input, prettify=False (should have no effect)
    test_html = '''
    <select class="selectpicker form-control" data-minimum-results-for-search="Infinity" data-width="100%" id="state" name="state">
        <option selected="selected" value="1">
            All
        </option>
        <option value="2">
            Active
        </option>
        <option value="3">
            Stopped
        </option>
    </select>
    '''
    selectors = ['meta', 'script', 'link', 'aside', 'nav', 'header', 'footer', 'ul.nav.flex-column.pt-4', 'aside.main-sidebar', 'div.box-tools', 'div.hidden-xs']
    stripped_result = remove_tags(test_html, selectors, prettify=False)
    result = get_text_values(stripped_result)
    assert result == ['All', 'Active', 'Stopped']

    # <select> test prettified input, prettify=True (should have no effect)
    test_html = '''
    <select class="selectpicker form-control" data-minimum-results-for-search="Infinity" data-width="100%" id="state" name="state">
        <option selected="selected" value="1">
            All
        </option>
        <option value="2">
            Active
        </option>
        <option value="3">
            Stopped
        </option>
    </select>
    '''
    selectors = ['meta', 'script', 'link', 'aside', 'nav', 'header', 'footer', 'ul.nav.flex-column.pt-4', 'aside.main-sidebar', 'div.box-tools', 'div.hidden-xs']
    stripped_result = remove_tags(test_html, selectors, prettify=True)
    result = get_text_values(stripped_result)
    assert result == ['All', 'Active', 'Stopped']


def test_roll_out_json():
    json_data = json.loads('''
                {
                    "id": 6,
                    "likes": 2,
                    "last_likes": [
                        {
                            "id": 4,
                            "username": "member1"
                        },
                        {
                            "id": 2,
                            "username": "moderator1"
                        }
                    ],
                    "is_liked": true,
                    "detail": [
                        "ok"
                    ]
                }
                ''')
    result = roll_out_json(json_data=json_data, debug=False)
    assert len(result) == 8
    assert result == ['id:6', 'likes:2', 'last_likes_id:4', 'last_likes_username:member1', 'last_likes_id:2',
                      'last_likes_username:moderator1', 'is_liked:True', 'detail:ok']


def test_roll_out_json_as_dict():
    # Simple test case
    json_data = json.loads('{"id":"1","name":"user1"}', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 2
    assert result == {'id': ['1'], 'name': ['user1']}

    # Simple test case with list
    json_data = json.loads('{"id":["1","2"],"name":"user1"}', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 2
    assert result == {'id': ['1 2'], 'name': ['user1']}

    # Simple nested JSON
    json_data = json.loads('''{"id":"1", "outer":{"inner":"2"}}''', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 2
    assert result == {'id': ['1'], 'outer_inner': ['2']}

    # Complex nested case
    json_data = json.loads('''
                {
                    "id": 6,
                    "likes": 2,
                    "last_likes": [
                        {
                            "id": 4,
                            "username": "member1"
                        },
                        {
                            "id": 2,
                            "username": "moderator1"
                        }
                    ],
                    "is_liked": true,
                    "detail": [
                        "ok"
                    ]
                }
                ''', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 6
    assert result == {'detail': ['ok'], 'id': ['6'], 'is_liked': ['True'], 'last_likes_id': ['4', '2'], 'likes': ['2'], 'last_likes_username': ['member1', 'moderator1']}

    # Test app 2 test case
    json_data = json.loads('''{"data":{"type":"discussions","id":"1","attributes":{"isHidden":true}}}''', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 3
    assert result == {'data_type': ['discussions'], 'data_id': ['1'], 'data_attributes_isHidden': ['True']}

    # Deep nesting test case
    json_data = json.loads('''{"level1":{"level2":{"level3":{"level4":{"level5":"value"}}}}}''', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 1
    assert result == {'level1_level2_level3_level4_level5': ['value']}

    # Object with duplicate keys and different values
    json_data = json.loads('{"id":"1","name":"user1","id":"2"}', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 2
    assert result == {'id': ['1', '2'], 'name': ['user1']}

    # Object with duplicate keys and different values (arrays)
    json_data = json.loads('{"id":["1","2"],"name":"user1","id":["3","4"]}', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 2
    assert result == {'id': ['1 2', '3 4'], 'name': ['user1']}

    # List of objects with duplicate keys and different values (arrays)
    json_data = json.loads('[{"id":["1","2"],"name":"user1"}, {"id":["3","4"]}]', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 2
    assert result == {'id': ['1 2', '3 4'], 'name': ['user1']}

    # Object with duplicate keys and duplicate values
    json_data = json.loads('{"id":"1","name":"user1","id":"1"}', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 2
    assert result == {'id': ['1', '1'], 'name': ['user1']}

    # List of two objects with identical keys and different values
    json_data = json.loads('[{"id":"1","name":"user1"},{"id":"2","name":"user2"}]', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 2
    assert result == {'id': ['1', '2'], 'name': ['user1', 'user2']}

    # List of two objects with identical keys and identical values
    json_data = json.loads('[{"id":"1","name":"user"},{"id":"1","name":"user"}]', object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    assert len(result) == 2
    assert result == {'id': ['1', '1'], 'name': ['user', 'user']}

    # Unsupported cases, should throw ValueErrors/DecodeErrors
    # Flat list
    with pytest.raises(ValueError):
        json_data = json.loads('[1,2,3]', object_pairs_hook=decode_as_list)
        result = roll_out_json_as_dict(json_data)

    # Nested list
    with pytest.raises(ValueError):
        json_data = json.loads('[[1,2],[3,4],[5,6]]', object_pairs_hook=decode_as_list)
        result = roll_out_json_as_dict(json_data)

    # Single values: string
    with pytest.raises(json.JSONDecodeError):
        json_data = json.loads("test", object_pairs_hook=decode_as_list)
        result = roll_out_json_as_dict(json_data)

    # Bytes
    with pytest.raises(ValueError):
        json_data = json.loads(b'\x12\x34\x56\x78', object_pairs_hook=decode_as_list)
        result = roll_out_json_as_dict(json_data)

    # Concrete test app tests
    # Test app 3 test case: flat list
    with pytest.raises(ValueError):
        json_data = json.loads('["hbg7qr5ypjdjjbpgrt94s3osac","w1nhdw38it8exxgbo81turafjo","hq3csqwuwiniimj1s7nxikc9gr"]', object_pairs_hook=decode_as_list)
        result = roll_out_json_as_dict(json_data)

    # Test app 3 test case: list of two objects
    data = '''[{"id":"kepebxjymfnxfedqo6bzt1udur","name":"channel_user","display_name":"authentication.roles.channel_user.name","description":"authentication.roles.channel_user.description","create_at":1620737113470,"update_at":1620737114082,"delete_at":0,"permissions":["manage_private_channel_properties","add_reaction","delete_private_channel","use_channel_mentions","delete_public_channel","read_public_channel_groups","manage_public_channel_members","read_channel","create_post","manage_private_channel_members","read_private_channel_groups","edit_post","manage_public_channel_properties","use_group_mentions","use_slash_commands","delete_post","upload_file","remove_reaction","get_public_link"],"scheme_managed":true,"built_in":true},{"id":"3rda4jzggtnpumucirsih3neur","name":"channel_admin","display_name":"authentication.roles.channel_admin.name","description":"authentication.roles.channel_admin.description","create_at":1620737113482,"update_at":1620737114091,"delete_at":0,"permissions":["use_channel_mentions","read_public_channel_groups","remove_reaction","manage_public_channel_members","manage_private_channel_members","manage_channel_roles","create_post","use_group_mentions","read_private_channel_groups","add_reaction"],"scheme_managed":true,"built_in":true}]'''
    json_data = json.loads(data, object_pairs_hook=decode_as_list)
    result = roll_out_json_as_dict(json_data)
    # The values from the duplicate 'id' keys get merged into a list, same for 'name' keys
    assert result == {'id': ['kepebxjymfnxfedqo6bzt1udur', '3rda4jzggtnpumucirsih3neur'], 'name': ['channel_user', 'channel_admin'], 'display_name': ['authentication.roles.channel_user.name', 'authentication.roles.channel_admin.name'], 'description': ['authentication.roles.channel_user.description', 'authentication.roles.channel_admin.description'], 'create_at': ['1620737113470', '1620737113482'], 'update_at': ['1620737114082', '1620737114091'], 'delete_at': ['0', '0'], 'permissions': ['manage_private_channel_properties add_reaction delete_private_channel use_channel_mentions delete_public_channel read_public_channel_groups manage_public_channel_members read_channel create_post manage_private_channel_members read_private_channel_groups edit_post manage_public_channel_properties use_group_mentions use_slash_commands delete_post upload_file remove_reaction get_public_link', 'use_channel_mentions read_public_channel_groups remove_reaction manage_public_channel_members manage_private_channel_members manage_channel_roles create_post use_group_mentions read_private_channel_groups add_reaction'], 'scheme_managed': ['True', 'True'], 'built_in': ['True', 'True']}


def test_is_json():
    test_json = '''
                {
                    "id": 6,
                    "likes": 2,
                    "last_likes": [
                        {
                            "id": 4,
                            "username": "member1"
                        },
                        {
                            "id": 2,
                            "username": "moderator1"
                        }
                    ],
                    "is_liked": true,
                    "detail": [
                        "ok"
                    ]
                }
                '''
    assert is_json(test_json)

    result = is_json("""@""")
    assert result is False

    result = is_json(None)
    assert result is False
