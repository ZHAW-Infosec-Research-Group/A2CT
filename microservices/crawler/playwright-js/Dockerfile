FROM mcr.microsoft.com/playwright:v1.34.0-jammy

# pwuser is the defaul user of this image from microsoft
USER pwuser
WORKDIR /home/pwuser

# Copy project
COPY --chown=pwuser:pwuser package.json package-lock.json entrypoint.js pw_crawler.js /home/pwuser/

# Install dependencies without test dependencies
RUN npm install
# Install playwright, browser etc.
RUN npx playwright install
# Enable Node.js process to use a lot of memory (actor has limit of 32GB)
ENV NODE_OPTIONS="--max_old_space_size=30000"

# Run playwright test
ENTRYPOINT ["node","entrypoint.js"]
