FROM public.ecr.aws/docker/library/node:18-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --production

COPY server.js ./
COPY src/ ./src/

ENV CODE_VERSION=good
ENV PGSSLMODE=require

EXPOSE 3000

CMD ["node", "server.js"]
