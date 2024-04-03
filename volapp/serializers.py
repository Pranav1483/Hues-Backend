from rest_framework.serializers import ModelSerializer, SerializerMethodField
from .models import Streak, Posts
from django.contrib.auth.models import User

class UserSerializer(ModelSerializer):
    username = SerializerMethodField()

    class Meta:
        model = Streak
        fields = (
            'username',
            'current_streak',
            'max_streak',
            'last_post_datetime'
        )
    
    def get_username(self, obj):
        return obj.user.username
    

class PostsSerializer(ModelSerializer):
    username = SerializerMethodField()

    class Meta:
        model = Posts
        fields = (
            'id',
            'multimedia',
            'description',
            'username',
            'timestamp',
            'flagged',
            'emotions',
            'answers',
            'total_likes',
            'display'
        )
    
    def get_username(self, obj):
        return obj.posted_user.username
    

class UserSerializerForAdminView(ModelSerializer):

    class Meta:
        model = User
        fields = (
            'username',
            'is_staff',
            'date_joined'
        )