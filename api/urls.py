from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    # Auth
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('auth/profile/', views.UserProfileView.as_view(), name='profile'), # BURASI DÜZELDİ
    
    # ML & AI
    path('ml/exam-analysis/', views.MLExamAnalysisView.as_view(), name='ml_exam_analysis'),
    path('ml/target-nets/', views.MLTargetNetsView.as_view(), name='ml_target_nets'),
    path('chat/', views.APIChatView.as_view(), name='api_chat'),
    path('summarize/', views.APISummaryView.as_view(), name='api_summary'),
    path('quiz-generate/', views.APIQuizGenerateView.as_view(), name='api_quiz_generate'),

    # Veritabanı
    path('schedule/', views.ScheduleView.as_view(), name='schedule'),
    path('report/all/', views.AllReportsView.as_view(), name='report_all'),
    path('report/', views.DailyReportView.as_view(), name='report_base'),
    path('report/<str:date>/', views.DailyReportView.as_view(), name='report_date'),

    path('summarize-file/', views.APIFileSummaryView.as_view(), name='summarize-file'),
]