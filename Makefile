
repo=localhost
user=pypiadmin
password=pypiadmin

install:
	pip install -i http://$(repo):8036 --trusted-host $(repo) -U --pre --use-feature=2020-resolver -r test_requirements.txt

.PHONY: build
build:
	shellfoundry install

download:
	pip download -i http://$(repo):8036 --trusted-host $(repo) --pre -r src/requirements.txt -d dist/downloads
