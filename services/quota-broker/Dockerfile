# syntax=docker/dockerfile:1
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o broker ./cmd/broker

FROM gcr.io/distroless/static-debian12
COPY --from=builder /app/broker /broker
EXPOSE 8080
ENTRYPOINT ["/broker"]
