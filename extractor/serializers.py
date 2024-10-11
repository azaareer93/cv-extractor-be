from rest_framework import serializers

class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
