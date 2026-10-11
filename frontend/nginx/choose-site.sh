#!/bin/sh
# Serve HTTPS once a certificate exists, plain HTTP until then - so the site
# can start before the first certificate is issued. The nginx image runs
# every script in /docker-entrypoint.d/ before it starts Nginx.
set -eu

if [ -f /etc/letsencrypt/live/abhiyudhya/fullchain.pem ]; then
    cp /etc/nginx/abhiyudhya/https.conf /etc/nginx/conf.d/default.conf
    echo "choose-site: certificate found - serving HTTPS"
else
    cp /etc/nginx/abhiyudhya/http.conf /etc/nginx/conf.d/default.conf
    echo "choose-site: no certificate yet - serving plain HTTP"
fi
