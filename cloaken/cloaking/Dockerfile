FROM node:20-alpine3.16 as builder
COPY . .
RUN npm ci --only=production
EXPOSE 3000
CMD ["node", "index.js"]