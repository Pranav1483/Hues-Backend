from django.db import models
from django.contrib.auth.models import User

def default_emotions():
    return {'emotions': []}

def default_answers():
    return {'answers': []}

class Streak(models.Model):
    user = models.OneToOneField(to=User, on_delete=models.CASCADE)
    current_streak = models.PositiveIntegerField(default=0)
    max_streak = models.PositiveIntegerField(default=0)
    last_post_datetime = models.DateTimeField(null=True)

class Posts(models.Model):
    multimedia = models.URLField(max_length=1000)
    description = models.TextField(blank=True)
    posted_user = models.ForeignKey(to=User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    flagged = models.BooleanField(default=False)
    emotions = models.JSONField(default=default_emotions)
    answers = models.JSONField(default=default_answers)
    total_likes = models.PositiveBigIntegerField(default=0)

class Likes(models.Model):
    user = models.ForeignKey(to=User, on_delete=models.CASCADE)
    post = models.ForeignKey(to=Posts, on_delete=models.CASCADE)

class ResetLink(models.Model):
    user = models.ForeignKey(to=User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    token = models.CharField(max_length=150)