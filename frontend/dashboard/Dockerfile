FROM node:20-alpine AS build
WORKDIR /app
COPY tsconfig.base.json ./
COPY shared ./shared
COPY dashboard/package.json dashboard/package-lock.json* ./dashboard/
WORKDIR /app/dashboard
ARG VITE_BASE_PATH=/
ENV VITE_BASE_PATH=$VITE_BASE_PATH
RUN npm install
COPY dashboard/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dashboard/dist /usr/share/nginx/html
COPY dashboard/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
