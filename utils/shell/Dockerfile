FROM gradle:jdk8-python

# Fiaas-deploy-daemon Running in Dev mod
EXPOSE 5000

# Workspace sharing
VOLUME /project
WORKDIR /project

# Setup wrapper
COPY ./utils/shell/docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]
