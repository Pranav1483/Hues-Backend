from django.urls import path
from .views import status, signin, signup, UserAPIView, PostAPIView, FeedAPIView, LikeAPIView, ResetAPIView, AnalyticsAPIView, FeedbackAPIView, SearchAPIView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("v1/status", status, name="status"),
    path("v1/refresh", TokenRefreshView.as_view(), name="refresh"),
    path("v1/user", UserAPIView.as_view(), name="user_api"),
    path("v1/post", PostAPIView.as_view(), name="post_api"),
    path("v1/feed", FeedAPIView.as_view(), name="feed_api"),
    path("v1/like", LikeAPIView.as_view(), name="like_api"),
    path("v1/reset", ResetAPIView.as_view(), name="reset_api"),
    path("v2/analytics", AnalyticsAPIView.as_view(), name="analytics_api"),
    path("v2/signin", signin, name="signin"),
    path("v2/signup", signup, name="signup"),
    path("v2/feedback", FeedbackAPIView.as_view(), name="feedback_api"),
    path("v2/search", SearchAPIView.as_view(), name="search_api")
]