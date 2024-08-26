'use strict';

const pw_crawler = require('./pw_crawler');
const yaml = require('js-yaml');
const fs = require('fs');
const ArgumentParser = require('argparse').ArgumentParser
const parser = new ArgumentParser();

parser.add_argument('--target_url');
parser.add_argument('--target_domain');

// Events 
process.on('exit', (code) => {
    console.log('Process exit event with code: ', code);
});

// App
const myArgs = parser.parse_args()
const resultList = new Array();
let username = process.env.user;
let password = process.env.pass;
console.log(username+":"+password)
let inputParameters = {};
try {
    inputParameters = yaml.load(fs.readFileSync('/tmp/payload.yml', 'utf8'));
} catch (e) {
    console.log('Failed to load input parameters', e);
    process.exit(1);
}
let blocked_words = process.env.blocked_words;
if (!blocked_words) {
    console.log(`blocked_words environment variable is undefined`);
    blocked_words = null;
}
// Split comma separated list into array of strings
let static_content_extensions = process.env.static_content_extensions;
if (!static_content_extensions) {
    console.log(`static_content_extensions environment variable is undefined`);
    static_content_extensions = [];
} else {
    static_content_extensions = static_content_extensions.split(",");
}
let ignore_tokens = process.env.ignore_tokens;
if (!ignore_tokens) {
    console.log(`ignore_tokens environment variable is undefined`);
    ignore_tokens = null;
}
let iteration_depth = process.env.iteration_depth;
if (myArgs.target_url && new URL(myArgs.target_url)) {
    resultList.push(myArgs.target_url);
    const domainList = myArgs.target_domain ? myArgs.target_domain.split(',') : [];
    console.log(domainList);
    pw_crawler.start(myArgs.target_url, domainList, inputParameters, blocked_words, static_content_extensions, ignore_tokens, iteration_depth, username, password);
} else {
    console.log('Wrong args, try again');
}
