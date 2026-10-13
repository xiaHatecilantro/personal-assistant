# 构建阶段安装锁定依赖并产出不可变静态资源。
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# 运行阶段不携带 Node 工具链，仅由 Nginx 提供静态文件和 API 代理。
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
