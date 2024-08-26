'''
Tests for add_header.py
'''


import pytest
from unittest.mock import Mock, patch
from microservices.crawler.mitmproxy import add_header

# INFOS for tests below:

# Example pretty_url
# flow.request.pretty_url: https://172.17.0.1:3443/cart_add

# Example pretty_host
# flow.request.pretty_host: 172.17.0.1

# Example headers from marketplace:
''' [(b'Host', b'172.17.0.1:3443'), (b'Connection', b'keep-alive'), (b'Sec-Fetch-Dest', b'style'), (b'If-None-Match', b'W/"2a1-17ba72b9340"'), \
        (b'If-Modified-Since', b'Thu, 02 Sep 2021 15:40:56 GMT'), (b'User-Agent', b'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) \
        HeadlessChrome/80.0.3987.0 Safari/537.36'), (b'Accept', b'text/css,*/*;q=0.1'), (b'Sec-Fetch-Site', b'same-origin'), (b'Sec-Fetch-Mode', b'no-cors'), \
        (b'Referer', b'https://172.17.0.1:3443/admin_area'), (b'Accept-Encoding', b'gzip, deflate, br'), (b'Accept-Language', b'en-US'), \
        (b'Cookie', b'marketplacecookie.sid=s%3A4YJM0EHEkDr00fA-2AqsE_42_wii-Cl-.yw63gm3cVyNjEw9FPE4LswrW517t6hFodbWRsTr6XCU; \
        marketplacecookie.sid=s%3A4YJM0EHEkDr00fA-2AqsE_42_wii-Cl-.yw63gm3cVyNjEw9FPE4LswrW517t6hFodbWRsTr6XCU')]
'''


def test_add_header_do_not_call_pages():

    # Positive case: do-not-call regex shouldn't match url
    flow = Mock()
    flow.request = Mock(pretty_url='https://172.17.0.1:3443/admin_area', pretty_host='172.17.0.1', method='GET', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': '172.17.0.1', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_not_called()

    # Negative case: do-not-call regex should match url
    flow = Mock()
    flow.request = Mock(pretty_url='https://172.17.0.1:3443/logout', pretty_host='172.17.0.1', method='GET', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': '172.17.0.1', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_called_once()


def test_add_header_full_mode():
    # Positive case #1: full_mode off with GET request => flow not killed
    flow = Mock()
    flow.request = Mock(pretty_url='https://172.17.0.1:3443/admin_area', pretty_host='172.17.0.1', method='GET', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': '172.17.0.1', 'blocked_words': 'log(-?out|off)', 'full_mode': 'off'}):
        add_header.request(flow)

    flow.kill.assert_not_called()

    # Positive case #2: full_mode on with POST request => flow not killed
    flow = Mock()
    flow.request = Mock(pretty_url='https://172.17.0.1:3443/admin_area', pretty_host='172.17.0.1', method='POST', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': '172.17.0.1', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_not_called()

    # Negative case: full_mode off with POST request => flow should be killed
    flow = Mock()
    flow.request = Mock(pretty_url='https://172.17.0.1:3443/admin_area', pretty_host='172.17.0.1', method='POST', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': '172.17.0.1', 'blocked_words': 'log(-?out|off)', 'full_mode': 'off'}):
        add_header.request(flow)

    flow.kill.assert_called_once()


def test_add_header_external_domain():
    # Positive case #1: URL on same domain should not be blocked
    flow = Mock()
    flow.request = Mock(pretty_url='https://site.com/test', pretty_host='site.com', method='GET', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': 'site.com', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_not_called()

    # Positive case #2: URL on same domain (IP) should not be blocked
    flow = Mock()
    flow.request = Mock(pretty_url='https://172.17.0.1:3443/admin_area', pretty_host='172.17.0.1', method='GET', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': '172.17.0.1', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_not_called()

    # Positive case #3: URL on subdomain should not be blocked
    flow = Mock()
    flow.request = Mock(pretty_url='https://test.site.com', pretty_host='test.site.com', method='GET', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': 'site.com', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_not_called()

    # Negative case #1: URL with partial match to domain should be blocked
    flow = Mock()
    flow.request = Mock(pretty_url='https://sitesite.com', pretty_host='sitesite.com', method='GET', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': 'site.com', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_called_once()

    # Negative case #2: Check if URLs to external domains are blocked when host is not below same subdomain as target_domain
    flow = Mock()
    flow.request = Mock(pretty_url='https://site.com', pretty_host='site.com', method='GET', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': 'test.site.com', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_called_once()

    # Disallow static.ghost.org:443
    flow = Mock()
    flow.request = Mock(pretty_url='static.ghost.org:443', pretty_host='static.ghost.org', method='CONNECT', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': '172.17.0.1', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_called_once()

    # Disallow http://google.com/search?q=HelloWorld&as_sitesearch=http%3A%2F%2F172.17.0.1%2F
    flow = Mock()
    flow.request = Mock(pretty_url='http://google.com/search?q=HelloWorld&as_sitesearch=http%3A%2F%2F172.17.0.1%2F', pretty_host='google.com', method='CONNECT', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': '172.17.0.1', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_called_once()

    # Check support for multiple allowed domains as comma-serparated domain list

    # Check that first domain in allowed domain list is recognized as valid domain
    flow = Mock()
    flow.request = Mock(pretty_url='https://172.17.0.1:3443/admin_area', pretty_host='172.17.0.1', method='GET', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': '172.17.0.1,192.168.178.1', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_not_called()

    # Check that the second domain in the allowed domain list is recognized as valid domain
    flow = Mock()
    flow.request = Mock(pretty_url='https://192.168.178.1:3443/admin_area', pretty_host='192.168.178.1', method='GET', headers={'Cookie': 'test-cookie-value'})
    flow.kill = Mock(return_value=None)

    # Set the environment vars (globals in add_header.py)
    with patch.dict('os.environ', {'auth': 'Cookie 1234', 'domain': '172.17.0.1,192.168.178.1', 'blocked_words': 'log(-?out|off)', 'full_mode': 'on'}):
        add_header.request(flow)

    flow.kill.assert_not_called()
