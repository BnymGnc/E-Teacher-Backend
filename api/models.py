from django.db import models
from django.contrib.auth.models import User

# --- 1. KULLANICI PROFİLİ VE KOTA SİSTEMİ ---
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    ai_credits = models.IntegerField(default=20) # Her yeni kullanıcıya 20 soru hakkı
    is_premium = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - Kredi: {self.ai_credits}"


# --- 2. KULLANICI AKTİVİTELERİ (Ders Programı, Raporlar vb.) ---
class UserActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=50) # Örn: 'schedule', 'daily_report'
    title = models.CharField(max_length=200)
    data = models.JSONField(default=dict) # React'ten gelen verileri esnekçe tutmak için
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.activity_type}"