const playwright = require('playwright');
const yaml = require('js-yaml');
const fs   = require('fs');
const path = require('path');

const start = async (username, password, config_file, browser) => {
    // Start playwright
    if (!browser)
        browser = await playwright.chromium.launch({ headless: true });
    
    let context = await browser.newContext({ ignoreHTTPSErrors: true });

    console.log(`Authenticating as user: ${username}, password: ${password}`);
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
    let page = await context.newPage();
    await page.goto('https://172.17.0.1:3443/', { timeout: 10000 });
    await page.waitForURL('https://172.17.0.1:3443/');
    await page.waitForLoadState('networkidle', { timeout: 10000 });
    await page.getByRole('button', { name: 'Admin area' }).click();
    await page.waitForURL('https://172.17.0.1:3443/login');
    await page.locator('input[name="username"]').click();
    await page.locator('input[name="username"]').fill(username);
    await page.locator('input[name="username"]').press('Tab');
    await page.locator('input[name="password"]').fill(password);
    await page.getByRole('button', { name: 'Login' }).click();
    await page.waitForURL('https://172.17.0.1:3443/admin_area');
    // Authentication ends here

    console.log('Storage is being processed')
    await context.storageState({ path: '/tmp/state.json' }) // Store storageState (cookies and local storage)
    const sessionStorage = await page.evaluate(() => JSON.stringify(sessionStorage)); // Store session storage
    fs.writeFileSync('/tmp/session.json', JSON.stringify(sessionStorage), 'utf-8');

    // Store cookies in the provided config file
    if (config_file) {
        const cookies = await context.cookies();
        const formattedCookies = cookies.map(cookie => `${cookie.name}=${cookie.value}`).join('; ');
        const doc = yaml.load(fs.readFileSync(path.resolve(__dirname, '../' + config_file), 'utf8'));
        const userIndex = doc.auth.tokens.findIndex(user=> user.hasOwnProperty(username));
        doc.auth.tokens[userIndex][username] = 'Cookie' + ' ' + formattedCookies;
        const updatedYaml = yaml.dump(doc, {lineWidth: -1});
        fs.writeFileSync(path.resolve(__dirname, '../' + config_file), updatedYaml, 'utf8');
        console.log(doc.auth.tokens[userIndex]);
    } 
    await context.close();
    await browser.close();
    return;
};

module.exports.start = start;