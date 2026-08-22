FROM node:20-alpine

WORKDIR /app

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

RUN chown -R node:node /app
USER node

EXPOSE 3000

CMD ["npm", "run", "start"]