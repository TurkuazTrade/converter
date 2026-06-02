FROM node:22-alpine

WORKDIR /workspace

COPY turkuaz-ui/package.json ./turkuaz-ui/package.json
COPY turkuaz-ui/src ./turkuaz-ui/src
COPY converter/web-crm/apps/web/.npmrc ./converter/web-crm/apps/web/.npmrc
COPY converter/web-crm/apps/web/package.json converter/web-crm/apps/web/package-lock.json* ./converter/web-crm/apps/web/

WORKDIR /workspace/converter/web-crm/apps/web
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY converter/web-crm/apps/web ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
