# FROM registry.gitlab.com/signald/signald:latest # out of date
FROM debian:bookworm-slim

# To deal with the issue described in https://gitlab.com/signald/signald/-/issues/375
# We have to install signal-cli
# https://github.com/AsamK/signal-cli
# ARG SIGNAL_CLI_VERSION
# Check if SIGNAL_CLI_VERSION is set and not empty
# RUN if [ -z "$SIGNAL_CLI_VERSION" ]; then echo "SIGNAL_CLI_VERSION argument is required" && exit 1; fi

RUN apt-get update \
    && apt-get install -y --no-install-recommends --reinstall curl \
    && apt-get install -y --reinstall ca-certificates \
    && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    systemd \
    git \
    build-essential \
    default-jdk


# update URL https://gitlab.com/signald/signald/-/tree/libsignal-service-java-unofficial-90
RUN git clone https://gitlab.com/signald/signald.git && \
    cd signald && \
    git checkout libsignal-service-java-unofficial-90
WORKDIR signald
RUN make installDist
RUN apt-get install sudo
RUN mkdir -p /var/run/signald
RUN make setup


RUN curl -o /usr/bin/signaldctl https://gitlab.com/api/v4/projects/21018340/jobs/artifacts/main/raw/signaldctl?job=build%3Ax86 && \
    chmod +x /usr/bin/signaldctl
# RUN systemctl start signald
# RUN signaldctl version

# RUN curl -L -o signal-cli-${SIGNAL_CLI_VERSION}.tar.gz https://github.com/AsamK/signal-cli/releases/download/v"${SIGNAL_CLI_VERSION}"/signal-cli-"${SIGNAL_CLI_VERSION}".tar.gz
# RUN tar xf signal-cli-${SIGNAL_CLI_VERSION}.tar.gz -C /opt && \
#     ln -sf /opt/signal-cli-${SIGNAL_CLI_VERSION}/bin/signal-cli /usr/local/bin/

# Allow other services to access the signald directory
# RUN chmod -R 755 ${PWD}/signald

HEALTHCHECK --interval=10s --timeout=20s --start-period=5s --retries=5 \
    CMD sh -c 'timeout 5s nc -zU /signald-sock/signald.sock || exit 1'

# WORKDIR /signald/build/install/signald/bin/
# RUN chmod +x signald

COPY signald_setup.sh /signald_setup.sh
RUN chmod +x /signald_setup.sh

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
# CMD ["/signald/build/install/signald/bin/signald", "--socket=/signald-sock/signald.sock"]
