from rest_framework.decorators import APIView, api_view
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT, HTTP_410_GONE, HTTP_500_INTERNAL_SERVER_ERROR
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTStatelessUserAuthentication, JWTAuthentication
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from .models import Streak, Posts, Likes, ResetLink, Feedback
from .serializers import UserSerializer, PostsSerializer
import logging
import requests
from hashlib import sha256
from datetime import datetime, timedelta
from django.conf import settings
from pytz import timezone
import json

logger = logging.getLogger(__name__)


@api_view(['GET'])
def status(request: Request):
    return Response(status=HTTP_200_OK)

@api_view(['POST'])
def signin(request: Request):
    username, password = request.data.get('username'), request.data.get('password')
    if not username or not password:
        return Response(status=HTTP_400_BAD_REQUEST)
    else:
        username = sha256(username.encode()).hexdigest()
        user = authenticate(request=request, username=username, password=password)
        if user is not None:
            token = RefreshToken.for_user(user)
            logger.info(f"{user.username} logged in")
            token_data = {
                'access': str(token.access_token),
                'refresh': str(token)
            }
            return Response(data=token_data, status=HTTP_200_OK)
        else:
            return Response(status=HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
def signup(request: Request):
    try:
        username, password = request.data.get('username'), request.data.get('password')
        if not username or not password:
            return Response(status=HTTP_400_BAD_REQUEST)
        else:
            username = sha256(username.encode()).hexdigest()
            if User.objects.filter(username=username).exists():
                return Response(status=HTTP_409_CONFLICT)
            else:
                user = User(username=username)
                user.set_password(password)
                user.save()
                streak = Streak(user=user)
                streak.save()
                logger.info(f"{user.username} created")
                return Response(status=HTTP_200_OK)
    except Exception as e:
        logger.warn(e)
        return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)

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
            
    
class ResetAPIView(APIView):

    authentication_classes = [JWTAuthentication]

    def get(self, request: Request):
        email = request.query_params.get('email')
        if not email:
            return Response(HTTP_400_BAD_REQUEST)
        else:
            current_time = datetime.now(timezone(settings.TIME_ZONE))
            current_time_str = datetime.strftime(current_time, "%Y-%m-%d %H:%M:%S.%f%z")
            try:
                user = User.objects.get(username=sha256(email.encode()).hexdigest())
                token = sha256(json.dumps({"user": user.username, "timestamp": current_time_str}).encode()).hexdigest()
                resetLink = ResetLink(user=user, timestamp=current_time, token=token)
                send_mail(
                    "Reset Password",
                    f"Follow this link to reset your password\n{settings.CLIENT_HOST}/reset?token={token}\n\nLink expires in 10 minutes",
                    "volship.app@gmail.com",
                    [email]
                )
                resetLink.save()
                logger.info(f"Password reset email sent to {user.username}")
                return Response(status=HTTP_200_OK)
            except User.DoesNotExist:
                return Response(status=HTTP_404_NOT_FOUND)
            except Exception as e:
                logger.warn(e)
                return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request: Request):
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        if not token or not new_password:
            return Response(status=HTTP_400_BAD_REQUEST)
        else:
            try:
                resetLink = ResetLink.objects.get(token=token)
                if resetLink.timestamp + timedelta(minutes=10) < datetime.now(timezone(settings.TIME_ZONE)):
                    resetLink.delete()
                    return Response(status=HTTP_410_GONE)
                else:
                    user = resetLink.user
                    user.set_password(new_password)
                    user.save()
                    resetLink.delete()
                    logger.info(f"{user.username} changed Password")
                    return Response(status=HTTP_200_OK)
            except ResetLink.DoesNotExist:
                return Response(status=HTTP_404_NOT_FOUND)
            except Exception as e:
                logger.warn(e)
                return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)


class AnalyticsAPIView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        start, end = request.query_params.get('start'), request.query_params.get('end')
        if not (start and end):
            return Response(status=HTTP_400_BAD_REQUEST)
        else:
            start = datetime.strptime(start, "%y-%m-%d %H:%M:%S.%f%z")
            end = datetime.strptime(end, "%y-%m-%d %H:%M:%S.%f%z")
            postFilter = Posts.objects.filter(timestamp__lte=end, timestamp__gte=start, posted_user=request.user)
            posts = PostsSerializer(postFilter, many=True).data
            logger.info(f"{request.user.username} fetched Analytics")
            return Response({'posts': posts}, status=HTTP_200_OK)
            

class FeedbackAPIView(APIView):

    authentication_classes = [JWTStatelessUserAuthentication]

    def post(self, request: Request):
        text = request.data.get('text')
        if not text:
            return Response(status=HTTP_400_BAD_REQUEST)
        else:
            feedback = Feedback(text=text)
            feedback.save()
            return Response(status=HTTP_200_OK)
        

class SearchAPIView(APIView):

    authentication_classes = [JWTStatelessUserAuthentication]

    def get(self, request: Request):
        query = request.query_params.get('query')
        if not query:
            return Response(status=HTTP_400_BAD_REQUEST)
        else:
            query = query.title()
            postQuery = Posts.objects.filter(emotions__emotions__contains=query).order_by('timestamp')[:20][::-1]
            posts = PostsSerializer(postQuery, many=True).data
            return Response(data={'posts': posts}, status=HTTP_200_OK)
    
    def post(self, request: Request):
        if request.data.get('postId') and request.data.get('timestamp') and request.data.get('query'):
            postId, timestamp, query = request.data.get('postId'), datetime.strptime(request.data.get('timestamp'), '%Y-%m-%dT%H:%M:%S.%f%z'), request.data.get('query').title()
            postsQuery = Posts.objects.filter(emotions__emotions__contains=query, timestamp__lte=timestamp, id__lt=postId)
            postsQuery = postsQuery.order_by('-timestamp', 'id')[:20]
            posts = PostsSerializer(postsQuery, many=True).data
            return Response(data={'posts': posts}, status=HTTP_200_OK)
        else:
            return Response(status=HTTP_400_BAD_REQUEST)


