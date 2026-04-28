# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS base
ENV PNPM_HOME=/usr/local/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

WORKDIR /app
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY libs/contracts ./libs/contracts
COPY apps/web/package.json ./apps/web/package.json

RUN pnpm install --frozen-lockfile --filter @golf/web... --filter @golf/contracts

COPY apps/web ./apps/web
RUN pnpm --filter @golf/web build

EXPOSE 3000
CMD ["pnpm", "--filter", "@golf/web", "start", "-p", "3000"]
