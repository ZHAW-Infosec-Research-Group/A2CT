FROM mitmproxy/mitmproxy:8.1.1
USER root:root
RUN mkdir /home/mitmproxy/scripts
COPY add_header.py /home/mitmproxy/scripts
COPY save_responses.py /home/mitmproxy/scripts
