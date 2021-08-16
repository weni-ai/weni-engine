ENVIRONMENT_VARS_FILE := .env
IS_PRODUCTION ?= false
CHECK_ENVIRONMENT := true


# Commands

createproto:
	@rm -rf ./weni/protos/
	@git clone --depth 1 --branch v1.0.1 https://github.com/Ilhasoft/weni-protobuffers ./weni/protos/
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/inteligence/authentication.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/inteligence/organization.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/inteligence/repository.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/billing.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/classifier.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/flow.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/org.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/statistic.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/user.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/connect/project.proto
