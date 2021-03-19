ENVIRONMENT_VARS_FILE := .env
IS_PRODUCTION ?= false
CHECK_ENVIRONMENT := true


# Commands

createproto:
	@rm -rf ./weni/protos/inteligence/*.py
	@rm -rf ./weni/protos/flow
	@git clone https://github.com/Ilhasoft/weni-protobuffers weni/protos/flow/
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/inteligence/authentication.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/inteligence/organization.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/rapidpro_billing/billing.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/rapidpro_flow/flow.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/rapidpro_org/org.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/rapidpro_statistic/statistic.proto
	@python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/rapidpro_user/user.proto
