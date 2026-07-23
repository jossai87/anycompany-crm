FROM public.ecr.aws/docker/library/node:18-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --production
COPY notificationWorker.js ./
ENV PGSSLMODE=require
CMD ["node", "notificationWorker.js"]
