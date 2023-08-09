.PHONY: speex-ns

DOCKER_PLATFORM ?= linux/amd64,linux/arm64

speex-ns:
	docker buildx build . -f Dockerfile.speex-ns --platform "$(DOCKER_PLATFORM)" --output 'type=local,dest=dist'
