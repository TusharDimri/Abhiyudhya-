# Build the React static bundle, then serve it with Nginx (also reverse-proxies /api).
FROM node:24-alpine AS build
WORKDIR /app
COPY package*.json ./
# exactly the versions in package-lock.json, so the server builds what was tested
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/site.conf nginx/http.conf nginx/https.conf /etc/nginx/abhiyudhya/
# picks http.conf or https.conf as conf.d/default.conf each time the container starts
COPY nginx/choose-site.sh /docker-entrypoint.d/40-choose-site.sh
RUN chmod +x /docker-entrypoint.d/40-choose-site.sh
EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
