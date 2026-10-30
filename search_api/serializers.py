from rest_framework import serializers


class CricketSearchSerializer(serializers.Serializer):
    query = serializers.CharField(
        required=True,
        min_length=3,
        max_length=500
    )
    limit = serializers.IntegerField(
        required=False,
        default=5,
        min_value=1,
        max_value=20
    )