FROM node:16.14-slim

RUN mkdir /opt/marketplace

COPY Marketplace-NodeExpress_Solution/ /opt/marketplace/

RUN apt update \
  && apt install -y sqlite3 curl \
  && cd /opt/marketplace \
  && npm install i\
  && node models/init-sequelize.mjs \
  && sqlite3 -cmd ".read models/data-pbkdf3.db" marketplace.sqlite3

EXPOSE 3000
EXPOSE 3443


WORKDIR /opt/marketplace/

COPY run.sh .

ENTRYPOINT ["bash","run.sh"]
