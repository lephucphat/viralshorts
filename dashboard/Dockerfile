# Multi-stage: `dev` for local docker-compose (HMR), `prod` for Coolify/production.
# The prod stage is last, so `docker build` (and Coolify) produce the static build
# by default. Local docker-compose targets the `dev` stage explicitly.

# ---- deps + dev server (local) ----
FROM node:20-alpine AS dev
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

# ---- production build ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Vite bakes env at BUILD time. Set VITE_API_URL to the backend's public URL
# (Coolify: add it as a build variable on the frontend service). Empty = same-origin.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
# Public origin of the site, e.g. https://viralshorts.example (no trailing slash). Used at BUILD
# time for canonical links, sitemap.xml and llms.txt; left empty, those are simply not emitted.
ARG SITE_URL=""
ENV SITE_URL=$SITE_URL
# Optional product analytics (OpenPanel). Left empty, index.html initialises
# nothing and the build phones home to nobody; see the comment there.
ARG VITE_OPENPANEL_API_URL=""
ENV VITE_OPENPANEL_API_URL=$VITE_OPENPANEL_API_URL
ARG VITE_OPENPANEL_CLIENT_ID=""
ENV VITE_OPENPANEL_CLIENT_ID=$VITE_OPENPANEL_CLIENT_ID
RUN npm run build

# ---- static serving (nginx) ----
FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
# nginx.conf is a template: the nginx image's entrypoint runs envsubst on it at
# start (only the two variables below) and writes /etc/nginx/conf.d/default.conf.
# Set DOMAIN to the public host name; defaults keep a bare `docker run` working.
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV DOMAIN=localhost \
    BACKEND_UPSTREAM=backend:8000 \
    NGINX_ENVSUBST_FILTER="DOMAIN|BACKEND_UPSTREAM"
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
