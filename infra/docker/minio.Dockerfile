# Rebuild the existing MinIO release after its upstream registry images were removed.
FROM golang:1.26.7-alpine3.24@sha256:28d89ee9cc0ff9fec75c82ca201e6bf7fdf9a679d4b7b24dfa04f2bb766bb468 AS build
WORKDIR /src
ADD --checksum=sha256:8872a8266ac623e35956e3cd7758b85c5ba79de419b1c05d4b46288e95f576dd https://codeload.github.com/minio/minio/tar.gz/f92beb79b555ca0762e01d5aca11e531353e9eae /src/minio.tar.gz
RUN tar -xzf minio.tar.gz --strip-components=1 && rm minio.tar.gz
RUN CGO_ENABLED=0 go build -trimpath -o /minio .

FROM alpine:3.24@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6
RUN apk add --no-cache ca-certificates curl && mkdir /minio_data
COPY --from=build /minio /usr/local/bin/minio
COPY --from=build /src/LICENSE /usr/share/licenses/minio/LICENSE
LABEL org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.revision="f92beb79b555ca0762e01d5aca11e531353e9eae" \
      org.opencontainers.image.version="RELEASE.2024-05-28T17-19-04Z" \
      org.opencontainers.image.licenses="AGPL-3.0-only"
EXPOSE 9000 9001
CMD ["minio", "server", "/minio_data", "--console-address", ":9001"]
