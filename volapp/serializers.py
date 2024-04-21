from rest_framework.serializers import ModelSerializer, SerializerMethodField
from rest_framework.request import Request
from .models import Streak, Posts, Likes
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

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
    
    def get_username(self, obj: Streak):
        return obj.user.username
    

class PostsSerializer(ModelSerializer):
    username = SerializerMethodField()
    emoji = SerializerMethodField()

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
            'display',
            'reactions',
            'emoji'
        )
    
    def get_username(self, obj: Posts):
        return obj.posted_user.username
    
    def get_emoji(self, obj: Posts):
        request: Request = self.context.get('request')
        user: User = request.user
        like_filter = Likes.objects.filter(user=user, post=obj)
        if like_filter.exists():
            return like_filter.get().emoji   
        else:
            return "" 

class UserSerializerForAdminView(ModelSerializer):

    class Meta:
        model = User
        fields = (
            'username',
            'is_staff',
            'date_joined'
        )