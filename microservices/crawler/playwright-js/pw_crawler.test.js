const pw_crawler = require('./pw_crawler');
const hasAllowedDomain = pw_crawler.hasAllowedDomain;

describe('hasAllowedDomain function', () => {
    test('hasAllowedDomain allows allowed URL', () => {
        const allowedDomainList = ['172.17.0.1'];
        const legalUrl = "http://172.17.0.1/signup_user_complete";
        expect(hasAllowedDomain(legalUrl, allowedDomainList)).toBe(true);
    });

    test('hasAllowedDomain allows allowed URL with port number', () => {
        const allowedDomainList = ['172.17.0.1'];
        const legalUrl = "http://172.17.0.1:3443/signup_user_complete";
        expect(hasAllowedDomain(legalUrl, allowedDomainList)).toBe(true);
    });

    test('hasAllowedDomain allows allowed URL when from subdomain of allowed domain', () => {
        const allowedDomainList = ['mydomain.com'];
        const legalUrl = "http://mysubdomain.mydomain.com/signup_user_complete";
        expect(hasAllowedDomain(legalUrl, allowedDomainList)).toBe(true);
    });

    test('hasAllowedDomain allows allowed URL when from subdomain of disallowed domain', () => {
        const allowedDomainList = ['mydomain.com'];
        const legalUrl = "http://mysubdomain.TESTmydomain.com/signup_user_complete";
        expect(hasAllowedDomain(legalUrl, allowedDomainList)).toBe(false);
    });

    test('hasAllowedDomain allows allowed URL when using multiple allowed domains', () => {
        const allowedDomainList = ['172.17.0.1', '10.0.0.0'];
        const legalUrl = "http://10.0.0.0/signup_user_complete";
        expect(hasAllowedDomain(legalUrl, allowedDomainList)).toBe(true);
    });

    test('hasAllowedDomain disallows external URL', () => {
        const allowedDomainList = ['172.17.0.1'];
        const illegalUrl = "https://about.mattermost.com/default-terms/";
        let returnValue = hasAllowedDomain(illegalUrl, allowedDomainList)
        console.log(`returnValue: ${returnValue}`);
        expect(hasAllowedDomain(illegalUrl, allowedDomainList)).toBe(false);
    });

    test('hasAllowedDomain disallows URL when allowed domains are empty', () => {
        const allowedDomainList = [];
        const illegalUrl = "https://about.mattermost.com/default-terms/";
        let returnValue = hasAllowedDomain(illegalUrl, allowedDomainList)
        expect(hasAllowedDomain(illegalUrl, allowedDomainList)).toBe(false);
    });
});
