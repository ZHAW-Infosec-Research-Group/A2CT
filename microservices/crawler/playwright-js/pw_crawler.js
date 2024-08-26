const playwright = require('playwright');
const dompath = require('playwright-dompath');
const fs = require('fs');
var crypto = require('crypto');

const urlQueue = [];
const finishedUrls = new Set();
const visitCounts = [];
const clickableInputSelector = 'button, input[type=submit], a[href=""], a[href^="#"], a[href^="javascript:"]' ;
const errorLogs = [];
const LOAD_TIMEOUT = 30000;
const NETWORKIDLE_TIMEOUT = 10000;
const NAVIGATION_LOAD_TIMEOUT = 3000;
const NAVIGATION_NETWORKIDLE_TIMEOUT = 10000;
const CLICKABLE_ELEMENT_LOCATOR_TIMEOUT = 2000;
const CLICKABLE_ELEMENT_HANDLE_TIMEOUT = 1000;
const CONTEXT_LIMIT = 300;
const DEBUG = 1;
var contextCtr = 0;

let allowedDomainList;
let doNotCallRegEx;
let filteredExtensions;
let maxIterationDepth;
let inputParameters = {};
let user, pass;
let ignoredTokens;
let sessionStorage;


const start = async (url, domainList, inputParams, blocked_words, static_content_extensions, ignore_tokens, iteration_depth, username, password) => {
    console.log('Proxy Server at: ' + process.env.http_proxy);
    ignoredTokens = ignore_tokens;
    inputParameters = inputParams;
    user = username;
    pass = password;
    if (blocked_words) {
        try {
            doNotCallRegEx = new RegExp(blocked_words);
        } catch {
            console.log(`doNotCallRegEx "${blocked_words}" is invalid regex`);
            doNotCallRegEx = null;
        };
    } else {
        doNotCallRegEx = null;
    }
    if (ignore_tokens) {
        try {
            ignoredTokens = new RegExp(ignore_tokens);
        } catch {
            console.log(`ignored_tokens "${ignoredTokens}" is invalid regex`);
            ignoredTokens = null;
        };
    } else {
        ignoredTokens = null;
    }
    filteredExtensions = static_content_extensions;
    maxIterationDepth = Number(iteration_depth);
    console.log(`doNotCallRegex: ${doNotCallRegEx}`);
    console.log(`filteredExtensions: ${filteredExtensions}`)
    console.log(`ignored_tokens: ${ignoredTokens}`)
    console.log(`Max Iteration depth set to: ${maxIterationDepth}`)

    // Fill domain whitelist
    try {
        const baseUrl = new URL(url);
        allowedDomainList = domainList;
        if (!(allowedDomainList && allowedDomainList.length)) {
            allowedDomainList = [baseUrl.domain] // Fallback
            console.log(`Using fallback domain whitelist: ${allowedDomainList}`)
        }
    } catch (e) {
        console.log(`Failed setting domain whitelist: ${e}`)
    }

    // Add seed
    addToQueue(url, crypto.createHash('md5').update(url).digest('hex'), url);

    // Start playwright
    const browser = await playwright.chromium.launch({ headless: true });

    sessionFile = fs.readFileSync('/tmp/session.json', 'utf-8');
    sessionStorage = await JSON.parse(sessionFile);
    console.log(sessionFile)
    

    await queueWorker(browser);
    await browser.close();

    if (DEBUG) console.log(`errorLogs: ${errorLogs}`) // Only use when debugging pageFunction for filling form fields
    return inputParameters;
};

const evaluatePage = async (url, clickableElementIndices, context, hashId) => {
    console.log('-------> STARTING PAGE EVALUATION ' + url + ' clickable indices: ' + clickableElementIndices);
    //In a multithread setting, context can be initiated here
    const page = await context.newPage();
    
    // While inside the execution of a page function, you log error messages here by calling console.error("your message")
    page.on('console', (message) => {
        if (message.type() === 'error') {
            console.log(message.text())
        }
    })

    page.on('request', req => {
        // If a request is detected, add the destination URL to the queue without the clickable element indices
        if (DEBUG) console.log('DEBUG: Detected new request, adding URL to queue');
        addToQueue(req.url(), crypto.createHash('md5').update(req.url()).digest('hex'), url)
    });

    // Load page and wait for 'load' event
    let pageLoadSuccessful = false;

    const resp = await page.goto(url, {
        timeout: LOAD_TIMEOUT,
        waitUntil: 'load'
    }).catch(e => {
        console.log('Something went wrong with URL ' + url + ' with error' + e.stack);
        return;
    });
    
    
    // After a successful 'load' event, also wait for the 'networkidle' event wait for the network to quiet down
    // in order to increase the chnace that dynamically loaded content has succeeded in loading and rendering
    try {
        await page.waitForLoadState('networkidle', {timeout: NETWORKIDLE_TIMEOUT});
        pageLoadSuccessful = true;
    } catch (e) {
        console.log(`Caught execption during page.waitForLoadState('networkidle'): ${e}`)
    }

    if (resp && pageLoadSuccessful) {
        const sessionStorage = await page.evaluate(() => JSON.stringify(sessionStorage));
        fs.writeFileSync('/tmp/session.json', JSON.stringify(sessionStorage), 'utf-8');
        if (DEBUG) console.log('current sessionStorage' + sessionStorage);
        if (!isUndefined(clickableElementIndices) && clickableElementIndices.length !== 0) {
            await evaluateClickableElement(page, clickableElementIndices, hashId);
        } else {
            await evaluateLink(page, url);
        }
    }
    if (DEBUG) console.log(`errorLogs: ${errorLogs}`); // Only use when debugging pageFunction for filling form fields
    await page.close();
    console.log('-------> FINISHED PAGE EVALUATION ' + url + ' clickable indices: ' + clickableElementIndices);
}

const evaluateClickableElement = async (page, clickableElementIndices, hashId) => {
    try {
        if (DEBUG) console.log('DEBUG: evaluateClickableElement');
        // Start recursively clicking the clickable elements by iterating through the clickable element indices list
        let iterationDepth = 0;
        for (const clickableElementIndex of clickableElementIndices) {
            if (DEBUG) console.log(`DEBUG: iterationDepth = ${iterationDepth}`);
            if (iterationDepth > maxIterationDepth) {
                // Max. iteration depth reached, stop recursively clicking
                return;
            }
            let elementsToClickLocator
            try {
                elementsToClickLocator = await page.locator(clickableInputSelector);
                if (clickableElementIndex >= await elementsToClickLocator.count()) {
                    if (DEBUG) console.log("Element isn't there anymore.");
                    return;
                }
            } catch (e) {
                console.log(`Failed to get count(): ${e.stack}`)
            }
            
            page.on('dialog', async dialog => {
                console.log('Dialog popped up with message: ' + dialog.message());
                try {
                    await dialog.accept();
                } catch (e) {
                    console.log(`Failed accepting dialog: ${e.stack}`)
                }
            });
            
            let clickableElementLocator;
            try {  // When there is nothing located, it halts the execution. 
                clickableElementLocator = await elementsToClickLocator.nth(clickableElementIndex);
            } catch (e) {
                if (DEBUG) console.log(`Could not get nth clickable element with locator: ${e.stack}.`)
            }

            let clickableElement;
            try {
                clickableElement = await clickableElementLocator.elementHandle({timeout: CLICKABLE_ELEMENT_HANDLE_TIMEOUT});
            } catch (e) {
                console.log(`Could not get element handle for clickable element with locator: ${clickableElementLocator}.`)
            }
            if (DEBUG) console.log('DEBUG: before filling forms');
            // Fill out form fields in the current page
            let changedInputParameters = {};
            try {
                changedInputParameters = await fillFormFields(page, clickableElement, inputParameters);
            } catch (e) {
                console.log('Filling forms failed.');
            }
            
            if (DEBUG) console.log('DEBUG: after filling forms');

            // Only accept changed input parameters if they were not set to undefined
            if (!isUndefined(changedInputParameters)) {
                if (DEBUG) console.log(`changedInputParams received a valid dictionary.`);
                inputParameters = changedInputParameters;
            } else {
                // The fillFormFields function failed, but we continue recursively clicking
                if (DEBUG) console.log(`changedInputParams was undefined.`);
            }

            // Set up flags for page navigation checks
            let clickSucceeded = false;
            let navigationSuccessful = false;

            // We check if we can click the current clickable element and whether this leads to a page navigation
            try {
                // If button isn't visible, enabled and stable, timeout of 2000 ms will be reached
                await clickableElementLocator.evaluate(b => b.click(), {timeout: CLICKABLE_ELEMENT_LOCATOR_TIMEOUT});
                // await clickableElement.evaluate(b => b.click(), {timeout: 2000});
                clickSucceeded = true;
                if (DEBUG) console.log(`Clicking button succeeded`);
            } catch (e) {
                if (DEBUG) console.log(`Clicking button did not succeed: ${e.stack}`);
            }

            if (clickSucceeded) {
                try {
                    // Only if clicking the element succeeded, we await a page navigation, since it takes a lot of unneccessary time otherwise
                    await page.waitForNavigation({timeout: NAVIGATION_LOAD_TIMEOUT, waitUntil: 'load'});
                    await page.waitForLoadState('networkidle', {timeout: NAVIGATION_NETWORKIDLE_TIMEOUT});
                    // If this point is reached the navigationPromise resolved successfully and we changed URL or reloaded the page
                    navigationSuccessful = true;
                } catch (e) {
                    console.log(`Clicking button did not result in page navigation: ${e}`) // print e.stack if reason unclear. Normally no navigation occurs
                }
            }
            if (navigationSuccessful) {
                // Stop recursive clicking; break out of the for-loop, since page context was most likely destroyed
                clickableElementIndices = [];
                await evaluateLink(page, page.url(), clickableElementIndices);
                return;
            }
            // Page navigation didn't succeed, continue recursive clicking
            iterationDepth++;
        }
        // We iterated over all clickable indices or reached max. iteration depth

        // Consider the current page's state one more time and gather links and clickable elements and add them to the queue

        await evaluateLink(page, page.url(), clickableElementIndices);
    } catch (e) {
        console.log(`Something went wrong evaluating clickable element: ${e}`)
    }
}

 /**
  * Fill the potentially existing form fields which can be around the given clickable element on the given page
  * @param page - current Playwright 'Page' object
  * @param clickableElement - elementHandle of the current clickable element being evaluated
  * @param inputParameters - global dictionary of  input parameters
  * @return inputParams - potentially changed inputParameters dictionary if new form field entries were found in the form
  */
const fillFormFields = async (page, clickableElement, inputParameters) => {
    return page.evaluate(([el, inputParams]) => {
            const parentForm = el.form;
            if (!parentForm) {
                return inputParams;
            }

            const inputElements = parentForm.elements;
            for (const inputElement of inputElements) {
                const fieldName = inputElement.name;
                let isValid = inputParams.hasOwnProperty('input') && inputParams.input.hasOwnProperty(inputElement.type)
                //check if the dictionaries contain relevant keys 
                const isKnownFieldName = fieldName && inputParams[fieldName];
                let fieldValue = '';

                if (inputElement.tagName === 'INPUT') {
                    if (inputElement.type === 'hidden') {
                        // we shouldn't modify hidden form fields, they may contain IDs or similar
                        continue;
                    }
                    
                    if (inputElement.type === 'file') {
                        // file uploads must be handled separately, skip for now
                        continue;
                    }

                    if (isKnownFieldName) {
                        fieldValue = inputParams[fieldName];
                    } else if (inputElement.type && isValid) {
                        fieldValue = inputParams.input[inputElement.type];
                    } else {
                        fieldValue = fieldName;
                    }

                    inputElement.value = fieldValue;
                } else if (inputElement.tagName === 'TEXTAREA') {
                    if (isKnownFieldName) {
                        fieldValue = inputParams[fieldName];
                    } else if (inputParams.input.textarea) {
                        fieldValue = inputParams.input.textarea;
                    } else {
                        fieldValue = fieldName;
                    }

                    inputElement.value = fieldValue;
                } else if (inputElement.tagName === 'SELECT') {
                    if (isKnownFieldName) {
                        fieldValue = inputParams[fieldName];
                    } else if (inputElement.options.length > 0) {
                        fieldValue = inputElement.options[0].value;
                    } else {
                        fieldValue = fieldName;
                    }
                    
                    inputElement.value = fieldValue;
                } else {
                    continue; // do not handle buttons or similar form fields
                }

                if (!isKnownFieldName && fieldName) {
                    inputParams[fieldName] = fieldValue;
                }
            }

            return inputParams;
        }, [clickableElement, inputParameters]);
}

/**
 * Evaluate the given URL on the page to find all new links and clickable elements and add them to the queue
 * @param {*} page - Current Playwright 'Page' object
 * @param {string} url - Current page's URL
 * @param {Array.<number>} clickableElementIndices - List of the clickable element indices used to get to the current clickable element
 */
 const evaluateLink = async (page, url, clickableElementIndices) => {
    try {
        if (DEBUG) console.log('DEBUG: evaluateLink');
        page.on('dialog', async dialog => {
            console.log('Dialog popped up with message: ' + dialog.message());
            try {
                await dialog.accept();
            } catch (e) {
                console.log(`Failed accepting dialog: ${e.stack}`)
            }
        });
        let linkElements;
        let elementsToClick;
        try {
            // Get all link elements without dummy hrefs, i.e., actual URLs
            linkElementsLocator = await page.locator('a:not([href=""]):not([href="#"]):not([href^="javascript:"])'); 
            linkElements = await linkElementsLocator.evaluateAll(anchors => anchors.map(function(anchor)
            {
                return anchor.href; //anchor.action
            } 
            ));
        } catch (e) {
            console.log(`evaluateLink: Could not get link elements: ${e.stack}`);
            return;
        }
        try {
            elementsToClick = await page.locator(clickableInputSelector);
        } catch (e) {
            console.log(`evaluateLink: Could not get clickable elements: ${e.stack}`)
            return;
        }
        if (DEBUG) console.log(url + ': Found ' + elementsToClick.length + ' clickable elements');
        if (DEBUG) console.log(url + ': Found ' + linkElements.length + ' links');

        if (DEBUG) console.log(`DEBUG: evaluateLink: queue length before adding new links: ${urlQueue.length}`)
        for (let link of linkElements) {
            if (DEBUG) console.log(`DEBUG: link: ${link}`);
            if (link)  // Undefined links are added some reason
                addToQueue(link, crypto.createHash('md5').update(link).digest('hex'), url);
        }
        console.log(`DEBUG: evaluateLink: new queue length after adding new links: ${urlQueue.length}`)
        
        if (DEBUG) console.log(`DEBUG: evaluateLink: queue length before adding clickable elements: ${urlQueue.length}`)
        for (let index = await elementsToClick.count() - 1; index >= 0; index--) {
            // Add the clickable index to the potentially already existing clickable element indices list
            let newClickableIndices = []
            if (isUndefined(clickableElementIndices)) {
                newClickableIndices = [index]
            } else {
                newClickableIndices = clickableElementIndices.concat([index]) // e.g. [1, 0, 3].concat([5]) => [1, 0, 3, 5]
                // Don't add new clickable elements if their clickable indices list cannot be reconstructed with the current maxIterationDepth
                if (newClickableIndices.length > maxIterationDepth) {
                    continue; // Skip adding the current clickable element
                }
            }
            if (DEBUG) console.log(`DEBUG: newClickableIndices: ${newClickableIndices}`)
            let elHandle;
            let cssPathVal;
            let outer;
            let outerForm;
            let hashId;
            let regex = new RegExp('value="(.*?)"','g');

            try {
                elHandle =  await (await elementsToClick.nth(index));
                elHandle = await elHandle.elementHandle( {timeout: 1000} );
                cssPathVal = await dompath.cssPath(elHandle);
                outer = await elHandle.evaluate(e=>e.outerHTML);
                if(ignoredTokens != null && outer.match(ignoredTokens)) {
                    outer = outer.split('<').map(element => {
                        if(element.match(ignoredTokens))
                            element = element.replace(regex, 'value=""');
                        return element;
                    }).join('');
                }

                hashId = crypto.createHash('md5').update(cssPathVal + outer).digest('hex');
                addToQueue(url, hashId, outer, newClickableIndices);
            } catch (e) {
                console.log('Something went wrong');
                continue;
            }
            
            try {
            const parentForm = await elHandle.evaluate(e=>e.form);
            if(parentForm){
                outerForm = await elHandle.evaluate(e=>e.form.outerHTML);
                if(ignoredTokens != null && outerForm.match(ignoredTokens)){
                        outerForm = (outerForm + ' ' + outer).split('<').map(element => {
                            if(element.match(ignoredTokens))
                                element = element.replace(regex,'value=""');
                            return element;
                }).join('');
                }
                let regex2 = new RegExp('input|form');
                outerForm = outerForm.split('<').filter(element => element.match(regex2)).join('');
                hashId = crypto.createHash('md5').update(cssPathVal + outerForm).digest('hex');
                addToQueue(url, hashId, outerForm, newClickableIndices);
            }} catch (e) {
                console.log('No form')
                continue;
            } 
        }
    } catch (e) {
        console.log(`Something went wrong evaluating links: ${e}`)
    }

    if (DEBUG) console.log(`DEBUG: evaluateLink: new queue length after adding clickable elements: ${urlQueue.length}`)
} 
const queueWorker = async (browser) => {
    // Different from puppeteer, created a context
    context = await browser.newContext({
        storageState: '/tmp/state.json', 
        ignoreHTTPSErrors: true});
    console.log(user)
    sessionFile = fs.readFileSync('/tmp/session.json', 'utf-8');
    sessionStorage = await JSON.parse(sessionFile);
    console.log(sessionStorage)
        await context.addInitScript((storage) => {
            const entries = JSON.parse(storage);
           for (const [key, value] of Object.entries(entries)) {
             window.sessionStorage.setItem(key, value);
           }
         }, sessionStorage);
    
    console.log('Sessionstorage in queueworker: ' + sessionStorage);
    while (urlQueue.length > 0) {

        const url = urlQueue[0].url;

        const clickableElementIndices = urlQueue[0].clickableElementIndices;
        const hashId = urlQueue[0].hashId;

        // Memory usage measurements
        const used = process.memoryUsage().heapUsed / 1024 / 1024;
        console.log(`The script uses approximately ${Math.round(used * 100) / 100} MB of memory`);
        console.log(`urlQueue: current nr. of elements: ${urlQueue.length}`)
        console.log(`finishedUrls: current nr. of elements: ${finishedUrls.size}`)

        if (contextCtr >= CONTEXT_LIMIT ) { // Every 300 elements added to the queues, context is renewed
            await context.storageState({path: '/tmp/state.json'});
            context.close();
            context = await browser.newContext({
                storageState: '/tmp/state.json', 
                ignoreHTTPSErrors: true});
            sessionFile = fs.readFileSync('/tmp/session.json', 'utf-8');
            sessionStorage = await JSON.parse(sessionFile);
            await context.addInitScript((storage) => {
                const entries = JSON.parse(storage);
               for (const [key, value] of Object.entries(entries)) {
                 window.sessionStorage.setItem(key, value);
               }
             }, sessionStorage);
            contextCtr = 0;
        }
        await evaluatePage(url, clickableElementIndices, context, hashId);
        markAsFinished(hashId);
    }
};

const addToQueue = (url, hashId, outer, clickableElementIndices) => {
    if (!url) {
        return;
    }
    url = url.split('#')[0]; // remove 'anchor fragment', so we don't call duplicate URLs

    const queueItem = {
        url,
        isClickableElement: !isUndefined(clickableElementIndices),
        clickableElementIndices: clickableElementIndices,
        hashId,
    };

    if (!hasAllowedDomain(url, allowedDomainList)
        || contentFilter(url)
        || doNotClick(url)) {
        if (DEBUG) console.log(`DEBUG: Prevented new queue item from being added to queue. URL: ${url}, clickable indices: ${clickableElementIndices}, outer: ${outer}`)
        return;
    }

    // Counter for endpoints
    let urlObj = new URL(url);
    const endpoint = urlObj.hostname + urlObj.pathname;
    if (DEBUG) console.log(`DEBUG: Endpoint ${endpoint}`)
    var counterItem = {
        endpoint: endpoint,
        counter: 0
    };

    let isFound = false;

    for (let i = 0; i < visitCounts.length; i++) {
        if (visitCounts[i].endpoint === counterItem.endpoint) {
            if (DEBUG) console.log(`DEBUG: ${visitCounts[i].endpoint} has been added ${visitCounts[i].counter} times`)
            if(visitCounts[i].counter > 150)
            {
                if (DEBUG) console.log(`DEBUG: Prevented ${url} that has been added to the queue more than 150 times.`);
                return;
            }
            isFound = true;
            break;
        }
    }
    if(!isFound)
        visitCounts.push(counterItem);

    if (DEBUG) console.log(`DEBUG: url: ${url}`)
    if (DEBUG) console.log(`DEBUG: finishedUrls.has(hashId) ${hashId}: ${finishedUrls.has(hashId)}`)
    if (DEBUG) console.log(`DEBUG: !hasAllowedDomain: ${!hasAllowedDomain(url, allowedDomainList)}`)
    if (DEBUG) console.log(`DEBUG: contentFilter(url): ${contentFilter(url)}`)
    if (DEBUG) console.log(`DEBUG: doNotClick(url): ${doNotClick(url)}`)
    if (finishedUrls.has(hashId)) {
        console.log(`DEBUG: Prevented new queue item from being added to queue. URL: ${url}, clickable indices: ${clickableElementIndices}, outer: ${outer}`)
        return;
    }

    let firstClickableIndex = urlQueue.length;
    for (let i = 0; i < urlQueue.length; i++) {
        if (urlQueue[i].hashId === queueItem.hashId) {
            if (DEBUG) console.log(`DEBUG: duplicate found:\n${urlQueue[i].url}\n${queueItem.url} with outer: \n${outer}`)
            return;
        }

        if (urlQueue[i].isClickableElement && i < firstClickableIndex) {
            firstClickableIndex = i;
        }
    }
    
    if (queueItem.isClickableElement) {
        if (DEBUG) console.log('Adding clickable element with indices ' + queueItem.clickableElementIndices + ' at url ' + url + ' to Queue');
        if (DEBUG) console.log('Adding clickable element ' +  'at url ' + url + ' outer: ' + outer + ' hash id: ' + hashId);
        urlQueue.push(queueItem);
        let ind = visitCounts.findIndex(element => element.endpoint === endpoint)
        if (ind!=-1)
            visitCounts[ind].counter++;
        finishedUrls.add(hashId); 
        contextCtr++;
    } else {
        console.log('Adding URL ' + url + ' to Queue');
        // Add in front of clickable elements, so that we process links first
        urlQueue.splice(firstClickableIndex, 0, queueItem);
        let ind = visitCounts.findIndex(element => element.endpoint === endpoint)
        if (ind!=-1)
            visitCounts[ind].counter++;
        finishedUrls.add(hashId);
    }
}


/**
 * Marks the crawled URL with the given hash finished by adding it to the finished URLs set
 * @param {*} hashId The passed hash of the finished task
 */
const markAsFinished = (hashId) => {
    contextCtr++;
    // We cannot just remove the first element, since we may have found new URLs which were appended at the front
    const index = urlQueue.findIndex(item => item.hashId === hashId);
    if (index > -1) {
        urlQueue.splice(index, 1);
    }
}


const isDuplicateQueueElement = (element1, element2) => {
    if (DEBUG)  console.log(`DEBUG COMPARISON:\n${element1.url}\n${element1.clickableElementIndices}\n${element2.url}\n${element2.clickableElementIndices}\n`)
    if (element1.isClickableElement && element2.isClickableElement) {
        // Case for clickable elements
        return element1.url === element2.url && element1.clickableElementIndices.toString() === element2.clickableElementIndices.toString();
    } else if (!element1.isClickableElement && !element2.isClickableElement) {
        // Case for pure URLs
        return element1.url === element2.url
    } else {
        // Case for comparison of pure URL and clickable element
        return false
    }
}


/**
 * Returns whether two clickableElementIndices lists are equal
 * @param {Array.<number>} clickableElementIndices1 - First list, potentially undefined
 * @param {Array.<number>} clickableElementIndices2 - Second list, potentially undefined
 * @returns whether the params are equal
 */
const compareClickableElementIndices = (clickableElementIndices1, clickableElementIndices2) => {
    if (!isUndefined(clickableElementIndices1) && !isUndefined(clickableElementIndices2)) {
        return clickableElementIndices1.toString() === clickableElementIndices2.toString();
    } else if (isUndefined(clickableElementIndices1) && isUndefined(clickableElementIndices2)) {
        return true;
    } else {
        return false;
    }
}


/**
 * Returns whether the passed URL is under the allowed domain(s)
 * @param {*} url the URL to check
 * @param {*} allowedDomainList the allowed domains
 * @returns whether or not the domain check is passed
 */
const hasAllowedDomain = (url, allowedDomainList) => {
    let domainCheckPassed = false;
    try {
        // URL could be invalid
        const urlObj = new URL(url);
        const host = urlObj.hostname;
        for (const index in allowedDomainList) {
            const domain = allowedDomainList[index];
            // URL must either have same domain or is a subdomain of the allowed domains
            if ((domain === host) || host.endsWith('.' + domain)) {
                domainCheckPassed = true;
                break;
            }
        }
    } catch (e) {
        console.log(`Failed evaluating host on allowed domain list: ${e}`);
    }
    return domainCheckPassed;
}


/**
 * Returns whether the path of the provided URL string ends in one of the declared static content extensions.
 */
const contentFilter = (urlStr) => {
    const url = new URL(urlStr);
    try {
        const [head, ...tail] = url.pathname.split('.').reverse();
        if (head) {
            if (filteredExtensions.some(elem => elem === head)) {
                if (DEBUG) console.log(`Excluding ${urlStr} due to static content extensions filter`);
                return true;
            } else {
                return false;
            }
        } else {
            return false;
        }
    } catch (e) {
        console.log(e.stack);
        return false
    }
};

/**
 * Returns whether the do-not-call regular expression matches the path of the provided URL string.
 */
const doNotClick = (urlStr) => {
    // Early return if doNotCallRegEx is intentionally unused
    if (doNotCallRegEx === null) {
        return false;
    }
    try {
        const url = new URL(urlStr);
        const path = url.pathname;
        if (path) {
            if (path.match(doNotCallRegEx)) {
                if (DEBUG) console.log(`Excluding ${urlStr} due to DoNotCall-Filter`);
                return true;
            }
        }
        return false;
    } catch (e) {
        console.log(e.stack);
        return false
    }
};

const isUndefined = (variable) => {
    return typeof variable === 'undefined';
}

module.exports.start = start;
module.exports.hasAllowedDomain = hasAllowedDomain;
module.exports.doNotClick = doNotClick;
module.exports.contentFilter = contentFilter;
