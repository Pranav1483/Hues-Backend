from rest_framework.decorators import APIView, api_view
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_302_FOUND, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT, HTTP_410_GONE, HTTP_500_INTERNAL_SERVER_ERROR
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTStatelessUserAuthentication, JWTAuthentication
from .permissions import IsAdmin
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Streak, Posts, Likes, Feedback
from .serializers import UserSerializer, PostsSerializer, UserSerializerForAdminView
import logging
import requests
from hashlib import sha256
from datetime import datetime, timedelta
from django.conf import settings
from pytz import timezone

logger = logging.getLogger(__name__)

emojis = {
    "1F604",
    "1F60D",
    "1F929",
    "1F970",
    "1F44F",
    "1F9E1"
}


@api_view(['GET'])
def status(request: Request):
    return Response(status=HTTP_200_OK)

@api_view(['POST'])
def signup(request: Request):
    try:
        username, email = request.data.get('username'), request.data.get('email')
        if not username or not email:
            return Response(status=HTTP_400_BAD_REQUEST)
        else:
            email = sha256(email.encode()).hexdigest()
            if User.objects.filter(username=username).exists():
                return Response(data={"message": "Username already exists"}, status=HTTP_409_CONFLICT)
            elif User.objects.filter(email=email):
                return Response(data={"message": "Email already exists"}, status=HTTP_409_CONFLICT)
            else:
                user = User(username=username, email=email)
                user.set_password(sha256((username + email).encode()).hexdigest())
                user.save()
                user.set_password
                streak = Streak(user=user)
                streak.save()
                logger.info(f"{user.username} created")
                return Response(status=HTTP_201_CREATED)
    except Exception as e:
        logger.warn(e)
        return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['POST'])
def admin_login(request: Request):
    if not request.data.get("username") or not request.data.get("password"):
        return Response(status=HTTP_400_BAD_REQUEST)
    else:
        username, password = request.data.get("username"), request.data.get("password")
        user = authenticate(request=request, username=username, password=password)
        if not user:
            return Response(status=HTTP_401_UNAUTHORIZED)
        elif not user.is_staff:
            return Response(status=HTTP_403_FORBIDDEN)
        else:
            token = RefreshToken.for_user(user)
            logger.info(f"{user.username} logged in")
            token_data = {
                'access': str(token.access_token),
                'refresh': str(token)
            }
            return Response(data=token_data, status=HTTP_200_OK)

class UserAPIView(APIView):

    authentication_classes = [JWTAuthentication]

    def get(self, request: Request):
        streak = Streak.objects.get(user=request.user)
        if streak.last_post_datetime and streak.last_post_datetime.date() + timedelta(days=1) < datetime.now(timezone(settings.TIME_ZONE)).date():
            streak.current_streak = 0
            streak.save()
        streak = UserSerializer(streak).data
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
        email = sha256(email.encode()).hexdigest()
        userFilter = User.objects.filter(email=email)
        if userFilter.exists():
            user = userFilter.get()
            token = RefreshToken.for_user(user)
            logger.info(f"{user.username} logged in")
            token_data = {
                'access': str(token.access_token),
                'refresh': str(token)
            }
            return Response(data=token_data, status=HTTP_200_OK)
        else:
            return Response(status=HTTP_302_FOUND)
    
    def delete(self, request: Request):
        username = request.user.username
        request.user.delete()
        logger.info(f"{username} deleted")
        return Response(status=HTTP_204_NO_CONTENT)
    

class PostAPIView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        try:
            postId = request.query_params.get('postId')
            if postId:
                postFilter = Posts.objects.filter(posted_user=request.user, id=postId)
                if postFilter.exists():
                    logger.info(f"{request.user.username} fetched Post {postId}")
                    return Response(data=PostsSerializer(postFilter.first(), context={"request": request}).data, status=HTTP_200_OK)
                else:
                    logger.warn(f"Post {postId} not found by {request.user.username}")
                    return Response(status=HTTP_404_NOT_FOUND)
            else:
                postQuery = Posts.objects.filter(posted_user=request.user).order_by('-timestamp')
                posts = PostsSerializer(postQuery, context={"request": request}, many=True).data
                logger.info(f"{request.user.username} fetched all Posts")
                return Response(data={'posts': posts}, status=HTTP_200_OK)
        except Exception as e:
            logger.critical(e)
            return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request: Request):
        streak = Streak.objects.get(user=request.user)
        current_date = datetime.now(timezone(settings.TIME_ZONE)).date()
        if streak.last_post_datetime and streak.last_post_datetime.date() + timedelta(days=1) < current_date:
            streak.current_streak = 0
        multimedia = request.data.get('url', '')
        description = request.data.get('description', '')
        emotions = {'emotions': request.data.get('emotions', [])}
        answers = {'answers': request.data.get('answers', [])}
        display = request.data.get('display', False)
        if not multimedia:
            return Response(status=HTTP_400_BAD_REQUEST)
        post = Posts(multimedia=multimedia, description=description, posted_user=request.user, emotions=emotions, answers=answers, display=display)
        try:
            post.save()
        except Exception as e:
            return Response(data=str(e), status=HTTP_500_INTERNAL_SERVER_ERROR)
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
            if request.data.get('display'):
                post.display = request.data.get('display')
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
        postQuery = Posts.objects.filter(display=True, flagged=False).order_by('-timestamp', '-id')[:20]
        posts = PostsSerializer(postQuery, context={"request": request}, many=True).data
        logger.info("Posts Fetched")
        return Response(data={'posts': posts}, status=HTTP_200_OK)
        

    def post(self, request: Request):
        if request.data.get('postId') and request.data.get('timestamp'):
            postId, timestamp = request.data.get('postId'), datetime.strptime(request.data.get('timestamp'), '%Y-%m-%dT%H:%M:%S.%f%z')
            postsQuery = Posts.objects.filter(
                                                Q(timestamp__lt=timestamp) | (Q(timestamp=timestamp) & Q(id__lt=postId)),
                                                display=True,
                                                flagged=False
                                            )
            postsQuery = postsQuery.order_by('-timestamp', '-id')[:20]
            posts = PostsSerializer(postsQuery, context={"request": request}, many=True).data
            logger.info("Posts Fetched")
            return Response(data={'posts': posts}, status=HTTP_200_OK)
        else:
            logger.warn("Error Fetching more Posts")
            return Response(status=HTTP_400_BAD_REQUEST)
        

class LikeAPIView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request):
        postId, emoji = request.data.get("post"), request.data.get("emoji")
        if emoji not in emojis:
            return Response(status=HTTP_400_BAD_REQUEST)
        user: User = request.user
        if postId and emoji:
            post_filter = Posts.objects.filter(id=postId)
            if post_filter.exists():
                post = post_filter.get()
                likes_filter = Likes.objects.filter(user=user, post=post)
                if likes_filter.exists():
                    like = likes_filter.get()
                    post.reactions[like.emoji] -= 1
                    like.emoji = emoji
                    post.reactions[emoji] = post.reactions.get(emoji, 0) + 1
                    like.save()
                    post.save()
                    return Response(status=HTTP_204_NO_CONTENT)
                else:
                    like = Likes(user=user, post=post, emoji=emoji)
                    post.reactions[emoji] = post.reactions.get(emoji, 0) + 1
                    post.save()
                    like.save()
                    return Response(status=HTTP_204_NO_CONTENT)
            else:
                return Response(status=HTTP_404_NOT_FOUND)
        else:
            return Response(status=HTTP_400_BAD_REQUEST)

            

class AnalyticsAPIView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        start, end = request.query_params.get('start'), request.query_params.get('end')
        if not (start and end):
            return Response(status=HTTP_400_BAD_REQUEST)
        else:
            start = datetime.strptime(start, "%y-%m-%dT%H:%M:%S.%f%z")
            end = datetime.strptime(end, "%y-%m-%dT%H:%M:%S.%f%z")
            postFilter = Posts.objects.filter(timestamp__lte=end, timestamp__gte=start, posted_user=request.user)
            posts = PostsSerializer(postFilter, context={"request": request}, many=True).data
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
            postQuery = Posts.objects.filter(emotions__emotions__contains=query, display=True, flagged=False).order_by('-timestamp', '-id')[:20]
            posts = PostsSerializer(postQuery, context={"request": request}, many=True).data
            return Response(data={'posts': posts}, status=HTTP_200_OK)
    
    def post(self, request: Request):
        if request.data.get('postId') and request.data.get('timestamp') and request.data.get('query'):
            postId, timestamp, query = request.data.get('postId'), datetime.strptime(request.data.get('timestamp'), '%Y-%m-%dT%H:%M:%S.%f%z'), request.data.get('query').title()
            postsQuery = Posts.objects.filter(Q(timestamp__lt=timestamp) | (Q(timestamp=timestamp) & Q(id__lt=postId)),
                                              emotions__emotions__contains=query, 
                                              display=True,
                                              flagged=False
                                            )
            postsQuery = postsQuery.order_by('-timestamp', '-id')[:20]
            posts = PostsSerializer(postsQuery, context={"request": request}, many=True).data
            return Response(data={'posts': posts}, status=HTTP_200_OK)
        else:
            return Response(status=HTTP_400_BAD_REQUEST)


class UserListAPIView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request: Request):
        userQuery = User.objects.all().order_by('-date_joined', '-username')[:20]
        users = UserSerializerForAdminView(userQuery, many=True).data
        logger.info("Admin Fetched Users")
        return Response({'users': users}, status=HTTP_200_OK)
    
    def post(self, request: Request):
        if not request.data.get('date_joined') or not request.data.get('username'):
            return Response(status=HTTP_400_BAD_REQUEST)
        else:
            date_joined, username = datetime.strptime(request.data.get('date_joined'), '%Y-%m-%dT%H:%M:%S.%f%z'), request.data.get('username')
            userQuery = User.objects.filter(
                Q(date_joined__lt=date_joined) | (Q(date_joined=date_joined) & Q(username__lt=username))
            )
            userQuery = userQuery.order_by('-date_joined', '-username')[:20]
            users = UserSerializerForAdminView(userQuery, many=True).data
            logger.info("Admin Fetched More Users")
            return Response({'users': users}, status=HTTP_200_OK)
        

class PostListAPIView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request: Request):
        postQuery = Posts.objects.all().order_by('-timestamp', '-id')[:20]
        posts = PostsSerializer(postQuery, context={"request": request}, many=True).data
        logger.info("Admin Fetched Posts")
        return Response({"posts": posts}, status=HTTP_200_OK)
    
    def post(self, request: Request):
        timestamp, id = request.data.get('timestamp'), request.data.get('id')
        if not timestamp or not id:
            return Response(status=HTTP_400_BAD_REQUEST)
        timestamp = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%f%z')
        postQuery = Posts.objects.filter(
            Q(timestamp__lt=timestamp) | (Q(timestamp=timestamp) & Q(id__lt=id))
        )
        postQuery = postQuery.order_by('-timestamp', '-id')[:20]
        posts = PostsSerializer(postQuery, context={"request": request}, many=True).data
        logger.info("Admin fetched more Posts")
        return Response({"posts": posts}, status=HTTP_200_OK)

    def patch(self, request: Request):
        id = request.query_params.get('id')
        if not id:
            return Response(status=HTTP_400_BAD_REQUEST)
        else:
            postFilter = Posts.objects.filter(id=id)
            if postFilter.exists():
                post = postFilter.get()
                post.flagged = not post.flagged
                post.save()
                logger.info(f"Post {id} {'flagged' if post.flagged else 'un-flagged'}")
                return Response(status=HTTP_204_NO_CONTENT)
            else:
                return Response(status=HTTP_404_NOT_FOUND)    


class ShareImageAPIView(APIView):

    def get(self, request: Request):
        post_id = request.query_params.get('id')
        if not post_id:
            return Response(status=HTTP_400_BAD_REQUEST)
        postFilter = Posts.objects.filter(id=post_id, display=True)
        if postFilter.exists():
            return Response(PostsSerializer(postFilter.get(), context={"request": request}).data, status=HTTP_200_OK)
        else:
            return Response(status=HTTP_404_NOT_FOUND)
        