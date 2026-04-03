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

    path('calendar/auth/', views.GoogleCalendarInitView.as_view(), name='calendar_auth'),
    path('google/callback/', views.GoogleCalendarCallbackView.as_view(), name='google_callback'),

    # Admin Paneli Linkleri
    path('admin/users/', views.AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/update-quota/', views.AdminUpdateQuotaView.as_view(), name='admin-update-quota'),
    path('admin/manage-users/', views.AdminUserManagementView.as_view(), name='admin-manage-users'),
]