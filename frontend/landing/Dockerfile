FROM node:20-alpine AS build
WORKDIR /app
COPY tsconfig.base.json ./
COPY assets ./assets
COPY landing/package.json landing/package-lock.json* ./landing/
WORKDIR /app/landing
RUN npm install
COPY landing/ .
ARG VITE_DASHBOARD_URL=http://localhost:3000
ENV VITE_DASHBOARD_URL=$VITE_DASHBOARD_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/landing/dist /usr/share/nginx/html
COPY --from=build /app/assets /usr/share/nginx/html/brand
COPY landing/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
