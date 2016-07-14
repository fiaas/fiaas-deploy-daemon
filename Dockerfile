FROM gliderlabs/alpine:3.3

RUN apk-install python py-pip ca-certificates

COPY dist/*.whl /

RUN pip install *.whl

EXPOSE 5000
CMD ["fiaas-deploy-daemon"]
