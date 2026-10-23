# Sauvegarde vers le NAS : client PostgreSQL 16 (même version majeure que la base), rsync.
# flock et timeout viennent de busybox.
FROM alpine:3.22
RUN apk upgrade --no-cache && apk add --no-cache postgresql16-client rsync tzdata tini
COPY --chmod=755 sauvegarder.sh planifier.sh essai.sh /app/
# Même numéro que le backend et le frontend (voir docker-build.yml), noté dans sauvegarde.txt.
ARG NEXT_PUBLIC_APP_VERSION=dev
ENV APP_VERSION=$NEXT_PUBLIC_APP_VERSION TZ=Europe/Paris
LABEL org.opencontainers.image.source=https://github.com/djkix/magazine-search
# root : la pile (compose, .env) peut n'être lisible que par root sur l'hôte. Tout est monté en lecture seule,
# sauf le NAS ; le service n'a aucune route vers Internet.
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/app/planifier.sh"]
