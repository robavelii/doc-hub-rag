FROM node:20-alpine AS build
WORKDIR /app
COPY tsconfig.base.json ./
COPY shared ./shared
COPY admin/package.json admin/package-lock.json* ./admin/
WORKDIR /app/admin
RUN npm install
COPY admin/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/admin/dist /usr/share/nginx/html
COPY admin/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
