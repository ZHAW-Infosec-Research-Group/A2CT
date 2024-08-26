const playwright = require('playwright');
const yaml = require('js-yaml');
const fs   = require('fs');
const path = require('path');

const start = async (username, password, config_file, browser) => {
    // Start playwright
    if (!browser)
        browser = await playwright.chromium.launch({ headless: true });
    
    context = await browser.newContext({ ignoreHTTPSErrors: true });

    console.log(`Authenticating as user: ${username}, password: ${password}`)
    if (username == 'public') {
        await context.storageState({path: '/tmp/state.json'});
        const page = await context.newPage();
        context = await browser.newContext({
            ignoreHTTPSErrors: true,
            storageState: '/tmp/state.json'});
        fs.writeFileSync('/tmp/session.json', JSON.stringify(''), 'utf-8');
        await page.close();
        await context.close();
        await browser.close();
        return;
    }

    // Authentication starts here












    // Authentication ends here

    console.log('Storage is being processed')
    await context.storageState({ path: '/tmp/state.json' }) // Store storageState (cookies and local storage)
    const sessionStorage = await page.evaluate(() => JSON.stringify(sessionStorage)); // Store session storage
    fs.writeFileSync('/tmp/session.json', JSON.stringify(sessionStorage), 'utf-8');
     
    // Store JWTs originating from session storage in the provided config file
    if (config_file) {
        const sessionStorage = await page.evaluate(() => JSON.stringify(sessionStorage));
        process.env.SESSION_STORAGE = sessionStorage;
        const parsedData = JSON.parse(sessionStorage);
        const doc = yaml.load(fs.readFileSync(path.resolve(__dirname, '../' + config_file), 'utf8'));
        const userIndex = doc.auth.users.findIndex(user=> user.hasOwnProperty(username))
        doc.auth.tokens[userIndex][username] = 'JWT' + " " + parsedData.accessToken;
        const updatedYaml = yaml.dump(doc, {lineWidth: -1});
        fs.writeFileSync(path.resolve(__dirname, '../' + config_file), updatedYaml, 'utf8');
        console.log(doc.auth.tokens[userIndex]);
    } 
    await context.close();
    await browser.close();
    return;
};

module.exports.start = start;
