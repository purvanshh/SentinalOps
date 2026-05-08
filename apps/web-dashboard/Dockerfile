FROM node:20-alpine

WORKDIR /app

COPY apps/web-dashboard/package.json /app/package.json
RUN npm install

COPY apps/web-dashboard /app

CMD ["npm", "run", "dev"]
