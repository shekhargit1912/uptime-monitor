# --- Build stage: compile the React app with Vite ---
FROM node:20-alpine AS build
WORKDIR /app
# Copy the lockfile too so `npm ci` gives a reproducible, pinned install.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- Serve stage: static files behind nginx (also reverse-proxies /api) ---
# nginx-unprivileged runs as a non-root user (uid 101) and listens on 8080.
FROM nginxinc/nginx-unprivileged:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
