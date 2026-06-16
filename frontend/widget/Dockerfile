FROM node:20-alpine AS build
WORKDIR /app
COPY tsconfig.base.json ./
COPY shared ./shared
COPY widget/package.json widget/package-lock.json* ./widget/
WORKDIR /app/widget
RUN npm install
COPY widget/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/widget/dist/widget.js /usr/share/nginx/html/widget.js
COPY widget/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
