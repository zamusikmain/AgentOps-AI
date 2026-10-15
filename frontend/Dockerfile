FROM node:24-alpine
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package.json
RUN npm ci --no-audit
COPY frontend ./frontend
RUN npm run build
WORKDIR /app/frontend
CMD ["npx", "next", "start", "--hostname", "0.0.0.0"]
