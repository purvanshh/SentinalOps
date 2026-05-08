FROM node:20-alpine

WORKDIR /app

COPY apps/web-dashboard/package.json /app/package.json
COPY apps/web-dashboard/tsconfig.json /app/tsconfig.json
COPY apps/web-dashboard/next.config.js /app/next.config.js
COPY apps/web-dashboard/next-env.d.ts /app/next-env.d.ts
RUN npm install

COPY apps/web-dashboard /app

CMD ["npm", "run", "dev"]
