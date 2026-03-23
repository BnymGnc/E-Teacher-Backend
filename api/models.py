from django.db import models
from django.contrib.auth.models import User

class UserActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=50) # Örn: 'chat', 'exam_analysis', 'daily_report'
    title = models.CharField(max_length=200)
    data = models.JSONField(default=dict) # React'ten gelen verileri esnekçe tutmak için
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.activity_type}"