from django.urls import path
from .views import status, UserAPIView, PostAPIView, FeedAPIView, LikeAPIView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("v1/status", status, name="status"),
    path("v1/refresh", TokenRefreshView.as_view(), name="refresh"),
    path("v1/user", UserAPIView.as_view(), name="user_api"),
    path("v1/post", PostAPIView.as_view(), name="post_api"),
    path("v1/feed", FeedAPIView.as_view(), name="feed_api"),
    path("v1/like", LikeAPIView.as_view(), name="like_api"),
]