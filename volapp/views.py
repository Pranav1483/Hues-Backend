from rest_framework.decorators import APIView, api_view
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTStatelessUserAuthentication, JWTAuthentication
from django.contrib.auth.models import User
from .models import Streak, Posts, Likes
from .serializers import UserSerializer, PostsSerializer
import logging
import requests
from hashlib import sha256
from datetime import datetime, timedelta
from django.conf import settings
from pytz import timezone
from rest_framework_simplejwt.views import TokenRefreshView

logger = logging.getLogger(__name__)


@api_view(['GET'])
def status(request: Request):
    return Response(status=HTTP_200_OK)


class UserAPIView(APIView):

    authentication_classes = [JWTAuthentication]

    def get(self, request: Request):
        streak = UserSerializer(Streak.objects.get(user=request.user)).data
        logger.info(f"{request.user.username} at Homepage")
        return Response(streak, status=HTTP_200_OK)

    def post(self, request: Request):
        email = ''
        if request.data.get('oauth'):
            google_access_token = request.data.get('oauth')
            response = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", params={"access_token": google_access_token})
            if not response.ok:
                logger.warn("Unauthorised Google Token")
                return Response(status=HTTP_401_UNAUTHORIZED)
            else:
                data = response.json()
                email = data['email']
        elif request.data.get('email'):
            email = request.data.get('email')
        else:
            logger.warn(f"Invalid Data during Signup\n\tGiven Data: {request.data.get('email')}")
            return Response(status=HTTP_409_CONFLICT)
        hash_email = sha256(email.encode()).hexdigest()
        user, created = User.objects.get_or_create(username=hash_email)
        if created:
            user.set_password(email[::-1])
            user.save()
            streak = Streak(user=user)
            streak.save()
            logger.info(f"{user.username} created")
        token = RefreshToken.for_user(user)
        logger.info(f"{user.username} logged in")
        token_data = {
            'access': str(token.access_token),
            'refresh': str(token)
        }
        if created:
            return Response(data=token_data, status=HTTP_201_CREATED)
        else:
            return Response(data=token_data, status=HTTP_200_OK)
    
    def delete(self, request: Request):
        username = request.user.username
        request.user.delete()
        logger.info(f"{username} deleted")
        return Response(status=HTTP_204_NO_CONTENT)
    

class PostAPIView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        postId = request.query_params.get('postId')
        if postId:
            postFilter = Posts.objects.filter(posted_user=request.user, id=postId)
            if postFilter.exists():
                logger.info(f"{request.user.username} fetched Post {postId}")
                return Response(data=PostsSerializer(postFilter.first()).data, status=HTTP_200_OK)
            else:
                logger.warn(f"Post {postId} not found by {request.user.username}")
                return Response(status=HTTP_404_NOT_FOUND)
        else:
            postQuery = Posts.objects.filter(posted_user=request.user).order_by('timestamp')
            posts = PostsSerializer(postQuery, many=True).data[::-1]
            logger.info(f"{request.user.username} fetched all Posts")
            return Response(data={'posts': posts}, status=HTTP_200_OK)
    
    def post(self, request: Request):
        streak = Streak.objects.get(user=request.user)
        current_date = datetime.now(timezone(settings.TIME_ZONE)).date()
        if streak.last_post_datetime and streak.last_post_datetime.date() + timedelta(days=1) < current_date:
            streak.current_streak = 0
        multimedia = request.data.get('url', '')
        description = request.data.get('description', '')
        emotions = {'emotions': request.data.get('emotions', [])}
        answers = {'answers': request.data.get('answers', [])}
        if not multimedia:
            return Response(status=HTTP_409_CONFLICT)
        post = Posts(multimedia=multimedia, description=description, posted_user=request.user, emotions=emotions, answers=answers)
        try:
            post.save()
        except Exception as e:
            return Response(data=str(e), status=HTTP_400_BAD_REQUEST)
        if not streak.last_post_datetime or streak.last_post_datetime.date() != current_date:
            streak.current_streak += 1
            streak.max_streak = max(streak.current_streak, streak.max_streak)
        streak.last_post_datetime = datetime.now(timezone(settings.TIME_ZONE))
        streak.save()
        logger.info(f"{request.user.username} posted Post {post.id}")
        return Response(status=HTTP_201_CREATED)
    
    def put(self, request: Request):
        postId = request.query_params.get('postId')
        if not postId:
            return Response(status=HTTP_400_BAD_REQUEST)
        postFilter = Posts.objects.filter(posted_user=request.user, id=postId)
        if postFilter.exists():
            post = postFilter.first()
            if request.data.get('description'):
                post.description = request.data.get('description')
            if request.data.get('emotions'):
                post.emotions = {"emotions": request.data.get('emotions')}
            if request.data.get('answers'):
                post.answers = {"answers": request.data.get('answers')}
            post.save()
            logger.info(f"{request.user.username} updated Post {postId}")
            return Response(status=HTTP_204_NO_CONTENT)
        else:
            logger.warn(f"Post {postId} not found by {request.user.username}")
            return Response(status=HTTP_404_NOT_FOUND)
    
    def delete(self, request: Request):
        postId = request.query_params.get('postId')
        if not postId:
            return Response(status=HTTP_400_BAD_REQUEST)
        postFilter = Posts.objects.filter(posted_user=request.user, id=postId)
        if postFilter.exists():
            post = postFilter.first()
            post.delete()
            logger.info(f"{request.user.username} deleted Post {postId}")
            return Response(status=HTTP_204_NO_CONTENT)
        else:
            logger.warn(f"Post {postId} not found by {request.user.username}")
            return Response(status=HTTP_404_NOT_FOUND)
    

class FeedAPIView(APIView):

    authentication_classes = [JWTStatelessUserAuthentication]

    def get(self, request: Request):
        postQuery = Posts.objects.all().order_by('timestamp')[:20][::-1]
        posts = PostsSerializer(postQuery, many=True).data
        return Response(data={'posts': posts}, status=HTTP_200_OK)
        

    def post(self, request: Request):
        if request.data.get('postId') and request.data.get('timestamp'):
            postId, timestamp = request.data.get('postId'), datetime.strptime(request.data.get('timestamp'), '%Y-%m-%dT%H:%M:%S.%f%z')
            postsQuery = Posts.objects.filter(timestamp__lte=timestamp, id__lt=postId)
            postsQuery = postsQuery.order_by('-timestamp', 'id')[:20]
            posts = PostsSerializer(postsQuery, many=True).data
            return Response(data={'posts': posts}, status=HTTP_200_OK)
        else:
            return Response(status=HTTP_400_BAD_REQUEST)
        

class LikeAPIView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        if request.query_params.get('postId'):
            try:
                post = Posts.objects.get(id=request.query_params.get('postId'))
                like_data = Likes.objects.get_or_create(user=request.user, post=post)
                if like_data[1]:
                    post.total_likes += 1
                    post.save()
                    logger.info(f"{request.user.username} liked Post {post.id}")
                return Response(status=HTTP_200_OK)
            except Posts.DoesNotExist:
                logger.warn(f"Post {request.query_params.get('postId')} not found by {request.user.username}")
                return Response(status=HTTP_404_NOT_FOUND)
        else:
            return Response(status=HTTP_404_NOT_FOUND)
            
    
