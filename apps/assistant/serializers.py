from rest_framework import serializers


class AskRequestSerializer(serializers.Serializer):
    question = serializers.CharField(min_length=1, max_length=1000, required=True)
    document_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
    top_k = serializers.IntegerField(min_value=1, max_value=10, required=False, default=5)


class SourceSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    document_title = serializers.CharField()
    page = serializers.IntegerField(allow_null=True)
    chunk_id = serializers.UUIDField()
    excerpt = serializers.CharField()


class AskResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    grounded = serializers.BooleanField()
    insufficient_context = serializers.BooleanField()
    sources = SourceSerializer(many=True)
    request_id = serializers.CharField()
