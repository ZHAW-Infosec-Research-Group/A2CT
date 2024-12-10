# A2CT - Automated Access Control Testing of Web Applications

A2CT is a practical approach for the automated detection of access control vulnerabilities in web applications. A2CT requires only a small amount of configuration, supports most web applications, and can detect vulnerabilities in the context of all HTTP request types (GET, POST, PUT, PATCH, DELETE).

## Contributors
**ZHAW Institute of Computer Science (https://www.zhaw.ch/init), Information Security Research Group**
- Malte Kusshnir
- Olivier Favre
- Marc Rennhard
- Michael Schlaubitz
- Onur Veyisoglu

**scanmeter GmbH**
- Damiano Esposito
- Fabian Introvigne
- Valentin Zahnd

## Publications

Kushnir, Malte; Favre, Olivier; Rennhard, Marc; Esposito, Damiano; Zahnd, Valentin, 2021. Automated black box detection of HTTP GET request-based access control vulnerabilities in web applications. In: Proceedings of the 7th International Conference on Information Systems Security and Privacy. ICISSP 2021, online, 11-13 February 2021. Available at: https://doi.org/10.5220/0010300102040216

Rennhard, Marc; Kushnir, Malte; Favre, Olivier; Esposito, Damiano; Zahnd, Valentin, 2022. Automating the detection of access control vulnerabilities in web applications. SN Computer Science. 3(5), Available at: https://doi.org/10.1007/s42979-022-01271-1

Schlaubitz, Michael; Veyisoglu Onur; Rennhard, Marc, 2025. A2CT: Automated Detection of Function- and Object-Level Access Control Vulnerabilities in Web Applications. In: Proceedings of the 11th International Conference on Information Systems Security and Privacy. ICISSP 2025, Porto, Portugal, 20-22 February 2025. To appear.

## Detected Vulnerabilities

The following vulnerabilities were detected uasing A2CT: [CVE-2024-2730](https://nvd.nist.gov/vuln/detail/cve-2024-2730), [CVE-2024-2731](https://nvd.nist.gov/vuln/detail/cve-2024-2731), [CVE-2024-3448](https://nvd.nist.gov/vuln/detail/cve-2024-3448), [CVE-2024-12305](https://nvd.nist.gov/vuln/detail/cve-2024-12305), [CVE-2024-12306](https://nvd.nist.gov/vuln/detail/cve-2024-12306), [CVE-2024-12307](https://nvd.nist.gov/vuln/detail/cve-2024-12307)

# Installation

The following installation instructions are intended for a Ubuntu based system.

Install docker according to https://docs.docker.com/engine/install/ubuntu/. Follow *Install using the repository*.

Then allow to manage docker as non-root user according to https://docs.docker.com/engine/install/linux-postinstall/.

Install the docker compose plugin according to https://docs.docker.com/compose/install/.

Install Python 3.10, pip and Pipenv if they are not yet installed on your system. For Ubuntu 22.04 this can be done with:
```
sudo apt-get -y install python3 python3-pip
echo "alias python=\"python3\"" >> ~/.bashrc
echo "alias pip=\"pip3\"" >> ~/.bashrc
echo "PATH=\"\$PATH:~/.local/bin\"" >> ~/.bashrc
source ~/.bashrc
pip3 install --user pipenv
```
Install Node 16 or higher using the [Node.js installation instructions](https://nodejs.org/en/download/package-manager) (uses [nvm](https://github.com/nvm-sh/nvm)) oder other means available on your platform:

For example, for Node 16, use the following commands:
```
# installs nvm (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# download and install Node.js (you may need to restart the terminal)
nvm install 16

# verifies the right Node.js version is in the environment
node -v # should print `v16.20.2`

# verifies the right NPM version is in the environment
npm -v # should print `8.19.4`
```

Install SQLite:
```
sudo apt-get -y install sqlite
```

Clone the A2CT repository into a folder of your liking. Then, enter it and install the Python dependencies with Pipenv:

**If you are running Python 3.12 or newer, it may be necessary to delete the `Pipfile.lock` file before running the `pipenv install --dev` command below, as there are breaking changes for some dependencies between Python 3.10 and Python 3.12 versions.**
```
cd A2CT
pipenv install --dev
```

Navigate into the `auth_scripts` folder and run:
```
npm install
```
to install the JavaScript dependencies used by the JS-based auth scripts outside the docker containers.

Navigate to the `microservices/crawler/playwright-js` folder and run:
```
npm install
```
to install the JavaScript dependencies used by the playwright-js crawler.

## Setup database

The database stores all results during testing.  Create a file for it as follows:
```
sudo mkdir -p /opt/mitmproxy/db
sudo touch /opt/mitmproxy/db/responses.db
sudo chmod -R 777 /opt
```

## Docker images for crawling

Build images for crawling with `manage.py` utility script in the `A2CT` root folder:
```
./manage.py build image playwright-js
./manage.py build image mitmproxy
```

# Usage

Start a virtual environment in your A2CT folder:

`pipenv shell`

## Quick start

This repository includes **Marketplace**, a dockerized web application that can be used to showcase a fully working example of A2CT.

In order to run A2CT on Marketplace, the docker image included in this repository has to be loaded as follows:

```
cd microservices/testapps/marketplace/
cat marketplace_node.tar.gz.part* > marketplace_node.tar.gz
docker load < marketplace_node.tar.gz
```
**Note**: The Marketplace docker image **only supports the x86-64/AMD64 CPU architecture.** No ARM support (e.g., Apple M1 or M2 chips).

Marketplace also includes a config file, reset script, authentication script and payload file:
- `config_files/config_marketplace.yml`
- `reset_scripts/reset_marketplace.py`
- `auth_scripts/auth_marketplace.js`
- `vars/marketplace.yml`

Make sure to adjust the payloadfile path inside the config file so it contains the correct path to your A2CT folder.

To start A2CT on Marketplace, run the following command inside the virtual environment after completing all installation instructions above:

`python a2ct.py --config config_files/config_marketplace.yml --run_mode cfrv --full_mode on --deduplication_mode 3 --matching_mode m4i --matching_debug off --db_log_level dev-reduced --duplicate_check on --iteration_depth 2 --iteration_depth 2`

## Command line and config options

A2CT has the following command line options:

`python a2ct.py --config config_files/<config_file> --run_mode cfrv --full_mode on|off --deduplication_mode 1|2|3|4 --matching_mode m3i|m4i --matching_debug on|off --db_log_level dev|dev-reduced|prod --duplicate_check on|off --iteration_depth 1|2|3|4|5`

- `config`: a configuration file in yaml format
- `run_mode`: specifies the stages to be used: (c)rawling, (f)iltering, (r)eplay testing, findings (v)erification. E.g.: cfr does crawling, filtering and replay testing, but no findings verification. If crawling is not used, the test uses the results in responses.db from a previous run. E.g.: frv uses the available crawling results and performs the remaining three stages.
- `full_mode`: turns full mode on or off. If full mode is off, all non-GET HTTP requests (POST, PUT, DELETE, etc.) are dropped by mitmproxy during crawling.
- `deduplication_mode`: tells the filters how the request bodies should be compared. 1 = ignore request bodies, 2 = only compare parameter names in request bodies, 3 = (DeduplicationFilter: only compare parameter names in request bodies, PublicContentFilter/OtherUserContentFilter: compare parameter names and values in request bodies), 4 = compare parameter names and values in request bodies (all three filters)
- `matching_mode`: the content matching mode to use during replay testing. m3i and m4i do differing amount of content stripping and use the intersection to determine the similarity. See comments in `html_json_utils.py` for the other modes.
- `matching_debug`: computes and stores the matching results of all matching modes in the database.
- `db_log_level`: Database log level (dev, dev-reduced, prod), dev = full logging, database can become large, dev-reduced = drastically reduces matching results table size, prod = minimal logging, deletes tables as soon as possible and only keeps final vulnerability findings table
- `duplicate_check`: Optional switch (off by default). Checks for duplicates in the database before inserting a new request during crawling (on, off).
- ``iteration_depth``: Iteration depth for clicking clickable elements (default: 1). Configures how many recursive clicks the crawler is allowed to performed on each clickable element on a web page. Higher values can increase crawling duration significantly.

### Suggested command line options

The following command line options are suggested for an initial test of a web application:
`--run_mode cfrv --full_mode on --deduplication_mode 3 --matching_mode m4i --matching_debug off --db_log_level dev-reduced --duplicate_check on --iteration_depth 2`

Explanation:

If a web application should not be crawled again, the `c` in the `--run_mode` option should be omitted. This requires a `responses.db` with a `crawling_results` table to be present in the `/opt/mitmproxy/db/` folder of the virtual machine. Similarly, if the filter stage should also be skipped, both the `c` and `f` in the `--run_mode` option can be omitted. In addition to the `crawling_results` table, a populated `crawling_results_after_other_user_content_filter` has to exist in the `responses.db` file.

If a web application is available in a containerized format and a reset script has been written to restart and reset such a locally hosted web application, the `--full_mode` option can be set to `on`. Otherwise the option should be set to `off`, so that only non-modifying requests are stored during crawling and used during replay testing (i.e. 'GET mode'). More detailed instructions on what needs to be provided to run A2CT on a new web application, is described in the last section of this README "[Preparing a new test application](##Preparing a new test application)". 

Depending on the `--deduplication_mode` command line option, slightly different rules are used detect duplicate requests during the filtering stages. This command line option is only used in deduplication filter, public user content filter and other user content filters. Reasonable option values for `--deduplication_mode` are `3` or `4`.

`--matching_mode m4i` uses the most current content similarity comparison method of request bodies as described by the paper.

The `--db_log_level` option should be set to `dev` or `dev-reduced` if intermediate tables should be preserved for inspection after the run. If there is no intention of inspecting the `matching_results` table, the `dev-reduced` option should be used as this can save multiple GBs of storage size of the `responses.db` file.

### Config file entries

For every web application that A2CT is used on, a separate config file should be placed in the `config_files` folder of A2CT folder (e.g. `~/A2CT/config_files/config_my_web_app.yml`).

The config file has the following subsections: `target`, `auth`, `payloadfile`, `csrf_field`/`csrf_header` (either/or, both optional) and the `options` section for optional subentries.

- `target`:
    - Under the `target` section of the config file, the following config entries should be provided:
    - `target_url`: the full URL the web application under test is available
        - e.g. `target_url: http://172.17.0.1:8002/`
    - `target_domain`: the domain of the web application
        - e.g. `target_domain: 172.17.0.1`
    - `path_to_db`: the path to the local SQLite database that should be used to store the results of A2CT run 
        - e.g.,  `path_to_db: /opt/mitmproxy/db/`
    - `reset_script`: if the application needs to run with `--full_mode on`, the relative path to a python based reset script that restarts a web application and resets its state. If no reset script is used, this entry can be left blank.
        - e.g., `reset_script: ./reset_scripts/reset_web_app.py`
    - `auth_script`: the relative path to a JavaScript-based authentication script that retrieves and stores fresh authentication tokens while the application under test is running. See the section "Preparing a new test application" for more information about auth scripts.
        - e.g., `auth_script: ./auth_scripts/auth_web_app.js`
- `auth`:
    - Under the `auth` section, in the subentry named `users`, a list of key-value pairs of users with their corresponding password has to be defined, for which A2CT should crawl and test the configured web application.
        - e.g.
       ```yaml
        auth:
            users:
            - admin: password
            - seller1: password
        ```
       - Below that, the `tokens` node must be filled with entries of the same users in the `users` entry, but these key-value pairs will instead be used to hold the authentication tokens (session cookie(s), JWT(s) etc.) of each user. Every time an auth script is executed during an A2CT run, the auth script will fill the respective line with fresh authentication tokens.
        ```yaml
        auth:
            users:
              ...
            tokens:
            - admin: Cookie ...
            - seller1: JWT ...
        ```
		Here `...` would be replaced with a cookie or JWT value through an auth script later in the testing process.
    - For the configured `users` list, a `combinations` entry with subentry `type` has to be defined as well. The `type` entry can have the values `all` or `selected`. If `all` is used, all possible user combinations (user pairs) are automatically calculated and used during an A2CT run. If this is not desired, a manual list of user combinations can be entered by setting the `type` entry to `selected` and listing the user pairs in a separate `user_pairs` entry representing a list of user pairs.
    If `type` is set to `all`, this subentry `selected` of `combinations` can be completely omitted.
- `payloadfile`:
    - The last required config entry is the `payloadfile` entry. The `payloadfile` entry has to be set to path to a YAML based filed containing common HTML form values. This file is used during crawling to send valid POST requests. In any case, the crawler will attempt to insert dummy values for HTML form elements, if no predefined values can be found in the payload file. If no web application specific configuration is needed, it can be set to the default file:
        - e.g. `payloadfile: /home/user/A2CT/vars/default_vars.yml`
- `csrf_field`: an entry that is used to declare that the web application uses CSRF tokens in the request body of its requests, i.e., the synchronizer token pattern. This entry has two subentries: `fieldname` and `csrf_values`. The `fieldname` specifies the parameter name used for the CSRF token in the request body and attempts to replace the value of this request body parameter during replay testing to avoid getting false negatives because of invalid CSRF tokens. The `csrf_values` subentry acts as a receptacle of the auth script that retrieves these CSRF values for user and stores them in the config file. It does not need to filled manually.
    - e.g. `fieldname: form_key`, see `config_example_csrf_field.yml` for a full example
- `csrf_header`: and entry that is used to declare that the web application sends CSRF tokens in a custom request header. This entry has two subentries: `headername` and a `csrf_values`. Analogously to the `fieldname` entry of the `csrf_field` option, the `headername` specifies the request header name that is used to send the CSRF tokens in each request during replay testing.
    - e.g. `headername: X-CSRF-Token`, see `config_example_csrf_header.yml` for a full example
- If any of the two options is used, the auth script als has to be adjusted slightly (see section "How to write an auth script"). If neither the `csrf_field` or `csrf_header` options are required, they should be completely omitted in the config file.
- `options`:
    - In the `options` section of the config file, various optional configuration takes place:
    - `standard_pages`: a comma-separated list of strings can be provided to filter out additional undesired URLs during the crawling process.
        - e.g. `standard_pages: about.php,credits.php`
    - `do_not_call_pages`: a regular expression matching URLs that should not be called during crawling. This is used to prevent accidental logouts during crawling which would invalidate session cookies.
        - e.g. `do_not_call_pages: log-out|logout|logoff`
    - `static_content_extensions`: a comma-separated list of file extensions that should be filtered out by the the static content filter.
        - e.g. `static_content_extensions: js,css,img,jpg,png,svg,gif,woff2,ttf`
    - `ignore_tokens`: a regular expression that can be used to match, e.g., CSRF tokens in request bodies. If a request body is `application/x-www-form-urlencoded` encoded, parameter names matched by this regular expression will be ignored during the comparison with another request's request body. This allows for more accurate detection of duplicate requests during filtering. Without this, request bodies of two otherwise identical requests would be considered different, even if they only differed in their values of a request body parameter such as a CSRF token. 
        - e.g. `ignore_tokens: tokenCSRF|csrfmiddlewaretoken|form_key`
    - `html_stripping_tags`: A list of CSS selectors that is used to match and strip away HTML elements from a response body before using the response body for a similarity calculation with the `--matching_mode m4i` option. More information about the syntax for the CSS selectors can be found here: https://facelessuser.github.io/soupsieve/selectors/.
        - e.g. `html_stripping_tags: ['ul.nav.flex-column.pt-4']`
    - `regex_to_match`: A regular expression that can be used during replay testing to recognize access denied web applications responses.
    -  `inter_threshold_validating`: a threshold value used in the content matching validators in the validator phase. Necessary for the `--matching_mode m4i` option. Defaults to 80.
## Manage.py utility

The manage.py utility script can be used to build the Mitmproxy and playwright-js crawler docker images and to remove lingering docker containers. Run ./manage.py -h to see the help message. 

# Python Testing

Test runner: [pytest](https://docs.pytest.org/)

Test coverage plugin: [pytest-cov](https://pypi.org/project/pytest-cov/)

Mock framework: `unittest.mock` (part of the python standard library)

## How to run the tests

All tests are located in the `tests` folder. Every test name has to start with `test_`. The tests can be run from the root directory of the repository. Make sure to have activated the virtual environment and execute pytest with:

`$ pytest`

The `pytest.ini` file defines which test files are executed when running `pytest`.

Some tests run slowly. If you wish to deselect them for a run, you can do this as follows:

`pytest -k "not (crawler or replay_testing)"`

to exclude the tests crawler.py and replay_testing.py for example.

For more information on deselecting tests, read the documentation for the `-k` option of `pytest`.

## Test coverage

If you wish to see a test coverage report, add the `--cov-report` option, e.g. `pytest --cov-report cov_html` to generate a html coverage report in a new folder folder called `cov_html`. Inside this folder you will find a `index.html` file showing you all test details when opened with a web browser.

The `.coveragerc` file defines which source code files are included or excluded from the test coverage.

# Playwright-js Crawler Testing

The JavaScript-based crawler code in the `microservices/crawler/playwright-js/` folder contains its own unit tests which are using the [Jest](https://jestjs.io/docs/getting-started) JavaScript testing framework.

See the `pw_crawler.test.js` file for an example on how to write unit tests for JavaScript.

Functions from the crawler code that should be tested have to exported in the respective code file, as can be seen on the bottom of the `pw_crawler.js` file, e.g.:
```
module.exports.hasAllowedDomain = hasAllowedDomain;
```
to export the `hasAllowedDomain()` function, which can then be imported in the test file.

## How to run the tests

In the `microservices/crawler/playwright-js/` folder, run:
```
npm test
```
to run all test files.
# General overview

## The A2CT stages

A2CT currently consists of 4 different stages that are run sequentially. The stages all save process data and store them in different database tables that are contained in the sqlite database stored in `/opt/mitmproxy/db/responses.db`. We suggest you use the 'SQLite Database Browser' package (`sqlitebrowser`) to look at the outputs of A2CT after each processing stage.

A more detailed explanation the different stages of A2CT is available in the paper, but the following short overview contains some technical details that can be useful when trying to understand and operate the A2CT tool.

- Crawling stage
    - A dockerized playwright-js crawler is used in combination with a mitmproxy container that store all crawled HTTP requests in an SQLite database. The crawler is automatically started and stopped during the crawling process for each configured user account of the web application under test.
    - The requests that the crawler sends to the web application are sent through the mitmproxy, which records the requests in a SQLite database.
    - All crawling results for the configured web application users are stored in the `crawling_results` database table.
- Filtering stage
    - A series of filters is applied to crawled requests from the `crawling_results` table.
    - Deduplication filter
        - The deduplication filter reads the `crawling_results` table and removes duplicate requests. The main goal is to remove unnecessary duplicate HTTP requests that were recorded during crawling. 
        - The `crawling_results_after_deduplication_filter` table is the output of the deduplication filter.
    - Public content filter
        - The public content filter reads the `crawling_results_after_deduplication_filter` table and removes HTTP requests that were issued by the public (non-authenticated) user.
        - The `crawling_results_after_public_content_filter` table is the output of the public content filter.
    - Static content filter
        - The static content filter reads the `crawling_results_after_public_content_filter` table and removes requests made to URLs containing a set of configured file extensions to static content. By default, only .js and .css extensions are filtered. Additional ones can be configured in the config file with the optional `static_content_extensions` entry.
        - The `crawling_results_after_static_content_filter` table is the output of the static content filter.
    - Standard pages filter
        - The standard pages filter reads the `crawling_results_after_static_content_filter` table and removes the requests made to URLs containing a set of standard page keywords. By default, the following standard page keywords are used: `'index', 'contact', 'about', 'login', 'logout', 'help'` filter requests. Additional standard pages can be configured with the optional `standard_pages` config entry.
        - The `crawling_results_after_standard_pages_filter` table is the output of the standard pages filter.
    - Other user content filter
        - For a given pair of users, the other user content filter reads the `crawling_results_after_standard_pages_filter` table and removes request made by the first user if they have also been made by the second user. This filter is applied for all permutations of possible user pairs.
        - The `crawling_results_after_other_user_content_filter` table is the output of the other user content filter.
- Replaying stage
    - The replay testing stage is also applied for all combinations of user pairs. For each user pair, the requests of the first user are replayed with the second user and recorded in the `replay_testing_results` table.
    - During replaying, the configured cookies and CSRF tokens in the config file are used to modify the request before sending it to the web application.
    - A series of validators also looks at the response of each replayed request to check if the request might indicate an access control vulnerability. Requests that pass certain validators are also stored in the `vulnerabilities_after_replay_testing` table.
- Validating stage
    - The final findings verifier stage uses the requests stored in the `replay_testing_results` and `vulnerabilities_after_replay_testing` tables to perform a series of final validation steps to decide if a request is  considered vulnerable or not. All findings are stored in the `vulnerabilities_after_replay_testing` table.
     
### Miscellaneous

 There also exists a `matching_results` table that only contains debug information for similarity scores when request bodies are compared during replay testing and findings verification. It is not essential as it doesn't store any information that is needed to decide if a request is vulnerable or not.
    
# Preparing a new test application

To run A2CT on a new web application, the web application has to be either made resettable through containerization with docker and a reset script or only be used with the command line option `--full_mode off`. `--full_mode off` corresponds to the 'GET mode', where only non-modifying requests are sent to the web application during crawling and replay testing, making resetting the web application unnecessary.

In both cases, at least an auth script has to be provided that can be called automatically by A2CT to retrieve fresh session cookies and optionally also CSRF tokens from the running web application. Auth scripts are stored in the `auth_scripts/` folder. Files for test applications (e.g., their `Dockerfile` or `docker-compose.yml` file) can be put into the `microservices/testapps/` folder under a new folder name for each test application. Config files for each web application can be stored in the `config_files` folder.

### Full_mode

- `--full_mode off`:
    - `reset_script` entry in config file can be left blank
    - web application has to be running before A2CT is started

- `--full_mode on`:
    - reset script must be provided
    - web application will be started with the reset script, which requires the web application to be containerized

### How to write an auth script

Auth scripts are used during the crawling stage and the replay testing stage. An auth script is always necessary whether `--full_mode` is set to `on` or `off`. The auth script should be placed into the `auth_scripts` folder in the project directory. The auth script is passed a user name, password and config file for the authentication of a single user at a time, but should be written so it can be used to authenticate all users of a web application. Each auth script contains the logic that creates a `/tmp/state.json` file that contains the cookies and local storage as well as a `/tmp/session.json` file that contains the session storage of the authenticated browser. Only in case of the public user, are empty `state.json` and `session.json` files created. Both of these `.json` files eventually passed to the crawler container by means of docker volumes in the python crawler code (`modules/crawler.py`), where they are used to restore the authenticated browser context. In the replay testing stage, the python code relies on the authentication tokens (cookies, JWTs or CSRF tokens) to be stored in the config file of the web application under test.

See `auth_example_cookies.js` for a full example of an auth script for web applications that uses session cookies and `auth_example_sessionstorage.js` for an example of an auth script for web applications that store authentication tokens in session storage. These two templates can be adjusted for any web application that should be tested. Simply record the login of a user of the web application under test once manually with [Playwright codegen](https://playwright.dev/docs/codegen), which results in a few lines of Playwright code that 1. visit the login page 2. fill in the user name and password and 3. submit the credentials (see lines 26-39 in `auth_example_cookies.js` for an example). Then simply use the resulting lines of code to replace the ones in the template auth script in order to automated the login procedure for all future auth script calls.

The last section of the auth script is responsible for extracting specific authentication tokens from the authenticated browser context and storing them appropriately in the config file of the web application under test (see lines 47-56 `auth_example_cookies.js`). Whereas the crawling container automatically uses the fully authenticated browser context that results from executing the authentication commands generated by codegen, the replay testing stage relies on manually crafted HTTP requests, which require that we manually specify which cookies, JWTs or CSRF tokens should be inserted in a request. For this reason, the necessary authentication tokens need to be configured precisely in the config file. The replay testing code will then automatically select the corresponding authentication token entries for each user in the config file for replaying. This means that web applications that use session cookies, use slightly different sections of code in their auth script than web applications that use JWTs from local storage or session storage. Compare the last `if` statement of `auth_example_cookies.js` and `auth_example_sessionstorage.js` to see how the respective authentication tokens are extracted and stored in the config file and adjust this for your web application as needed.

As explained in the "Config file entries" section of this README, two different CSRF mechanisms can be configured in the config file. If they are configured, the auth script should contain code that stores the corresponding CSRF token in the config file. This can be done by, e.g., extracting the CSRF token value from a cookie inside the `if` statement (between line 47-56) and then storing the token by include one of the following lines of code before the `yaml.dump()` function call on line 53, where <csrf_token_value> is the extacted CSRF token variable:
```js
doc.csrf_header.csrf_values[userIndex][username] = <csrf_token_value>
```
or
```js
doc.csrf_field.csrf_values[userIndex][username] = <csrf_token_value>
```
depending on the type of CSRF mechanism the web application uses.

In summary, after inserting the recorded login instructions, adjusting config file storage instructions and optional CSRF token storage commands in the auth script template, the the auth script will now authenticate all users for the web application under test.
### How to write a reset script

Reset scripts are python scripts that reset a containerized web application. I.e., the script stops the container, removes it, resets any potential state changes the web application might have received during the previous uptime, and finally restarts the web application container(s). The goal is to restart the web application with a clean slate. Since setting up a whole web application can require the installation of lots of different dependencies and configuration steps, containerizing the web application is currently the favored way to make it easily resettable.

Depending on how a web application is containerized, a reset script can be very simple. In the example reset script (`reset_scripts/reset_example.py`), the web application container(s) are stopped via docker compose, the data is erased and replaced with new data,  permissions are adjusted and the container(s) are finally spun up again with another docker compose call.

```python
import subprocess
import time

# Stop docker container(s) of application under test
subprocess.call('docker compose -f <path_to_application>/docker-compose.yml down', shell=True)
# Add wait time for containers to be stopped
time.sleep(2) 
# Reset the application state by deleting the  application's docker volumes containing, e.g., database data
subprocess.call('rm -rf /opt/<application_name>/*', shell=True)
# Restore the application state by copying fresh data into the application folder
subprocess.call('cp -r <path_to_application_data> /opt/<application_name>', shell=True)
# Adjust the permissions of the application data if necessary
subprocess.call("chmod -R 777 /opt/<application_name>", shell=True)
# Start the docker container(s) of the application under test again
subprocess.run('docker compose -f <path_to_application>/docker-compose.yml up -d', shell=True)
# Check for readiness of the application under test or utilize a fixed timer
time.sleep(20) 
```


If certain docker containers take a long time to become fully running and reachable via a web browser, `time.sleep()` calls in waiting loops can be included in the reset script to wait before performing the next required action. 

If a reset script requires superuser permissions, e.g., in order to extract zip archives with the correct permissions, it is suggested to set the suid bit for the reset script and to change its ownership to a superuser.
### Containerization of a web application

The goal of containerizing a web application is to have it be resettable through a reset script so that A2CT can be run with `--full_mode on`. Reset scripts need to be able to issue a series of commands that always restart whole docker application in a deterministic manner.

To containerize a web application and make it locally runnable, the components of the web application should be set up in one more docker images, which each require a Dockerfile if the components aren't already available as docker images from a docker hub, e.g. https://hub.docker.com/search?q=mysql. If the web application can be dockerized in a single docker image, the docker image has to be only built once with the Dockerfile. Afterwards, running containers of that docker image can then be stopped, reset and restarted in the reset script. If the docker image needs to use some persistent data in then local filesystem, docker volumes can be used: https://docs.docker.com/storage/volumes/.

More complex web applications usually consist of multiple docker images that are orchestrated together in a docker compose file. Some applications can use generic, publicly available docker images like a mysql database image and a Wordrpess web application image. The two can then be configured together in a docker compose file for example, so that the whole docker application can be started with a single `docker compose` call.

For examples how a docker image can be created and how multiple docker images can be used with docker compose, please refer to https://docs.docker.com/samples/ for numerous examples of dockerized web applications.
