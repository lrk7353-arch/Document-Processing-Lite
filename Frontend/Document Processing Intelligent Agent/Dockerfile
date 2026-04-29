# 采用多阶段构建：Node 构建 + Nginx 部署
FROM node:18-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* /app/
RUN npm ci || (yarn install --frozen-lockfile || pnpm install --frozen-lockfile)
COPY . /app
RUN npm run build

FROM nginx:alpine
WORKDIR /usr/share/nginx/html
COPY --from=build /app/dist/ .
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
