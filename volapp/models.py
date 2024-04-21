from django.db import models
from django.contrib.auth.models import User

def default_emotions():
    return {'emotions': []}

def default_answers():
    return {'answers': []}

def default_emojis():
    return {"1F604": 0,"1F60D": 0,"1F929": 0,"1F970": 0,"1F44F": 0,"1F9E1": 0}

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
    reactions = models.JSONField(default=default_emojis)
    display = models.BooleanField(default=False)

class Likes(models.Model):
    user = models.ForeignKey(to=User, on_delete=models.CASCADE)
    post = models.ForeignKey(to=Posts, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=10, null=True, default=None)

class Feedback(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    text = models.TextField()