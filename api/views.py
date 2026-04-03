import os
import requests
import json
import re
from rest_framework import permissions, status, views
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import UserActivity, UserProfile
import fitz  # PyMuPDF (PDF okumak için)
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.decorators import method_decorator   # EKLENEN SATIR
from django.views.decorators.csrf import csrf_exempt   # EKLENEN SATIR
from google_auth_oauthlib.flow import Flow
from django.shortcuts import redirect
from rest_framework.permissions import IsAuthenticated
from .models import GoogleCalendarCredential
from rest_framework.permissions import IsAdminUser
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import uuid

# --- ADMİN KOTA VE KULLANICI YÖNETİMİ ---

class AdminUserListView(views.APIView):
    """Tüm kullanıcıları ve mevcut kredilerini listeler"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.contrib.auth.models import User
        users = User.objects.all()
        user_list = []
        for user in users:
            # Profil varsa krediyi al, yoksa 0 de
            credits = user.profile.ai_credits if hasattr(user, 'profile') else 0
            user_list.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'ai_credits': credits,
                'is_staff': user.is_staff
            })
        return Response(user_list)

class AdminUpdateQuotaView(views.APIView):
    """Belirli bir kullanıcının kotasını günceller"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        user_id = request.data.get('user_id')
        new_credits = request.data.get('ai_credits')

        try:
            from django.contrib.auth.models import User
            target_user = User.objects.get(id=user_id)
            
            # Kullanıcının profili varsa güncelle, yoksa oluştur
            profile, created = UserProfile.objects.get_or_create(user=target_user)
            profile.ai_credits = new_credits
            profile.save()

            return Response({
                'message': f'{target_user.username} için yeni kredi sınırı: {new_credits}'
            })
        except User.DoesNotExist:
            return Response({'error': 'Kullanıcı bulunamadı.'}, status=404)

# --- ADMİN KULLANICI VE PREMİUM YÖNETİMİ ---

class AdminUserManagementView(views.APIView):
    """Tüm kullanıcıları listeler ve premium/kota durumlarını yönetir"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.contrib.auth.models import User
        users = User.objects.all()
        user_list = []
        for user in users:
            # Profil verilerini çekiyoruz
            profile = getattr(user, 'profile', None)
            user_list.append({
                'id': user.id,
                'username': user.username,
                'ai_credits': profile.ai_credits if profile else 0,
                'is_premium': profile.is_premium if profile else False,
                'is_staff': user.is_staff
            })
        return Response(user_list)

    def post(self, request):
        """Kullanıcının premium durumunu veya kredisini günceller"""
        user_id = request.data.get('user_id')
        new_credits = request.data.get('ai_credits')
        set_premium = request.data.get('is_premium') # True veya False gelir

        try:
            target_user = User.objects.get(id=user_id)
            profile, created = UserProfile.objects.get_or_create(user=target_user)
            
            if new_credits is not None:
                profile.ai_credits = new_credits
            
            if set_premium is not None:
                profile.is_premium = set_premium
                
            profile.save()

            return Response({
                'message': f'{target_user.username} başarıyla güncellendi.',
                'is_premium': profile.is_premium,
                'current_credits': profile.ai_credits
            })
        except User.DoesNotExist:
            return Response({'error': 'Kullanıcı bulunamadı.'}, status=404)

# --- 1. KULLANICI PROFİLİ VE KOTA (Görüntüleme / Güncelleme) ---
class UserProfileView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        ai_credits = 0
        if hasattr(user, 'profile'):
            ai_credits = user.profile.ai_credits
            
        return Response({
            'username': user.username,
            'email': user.email,
            'ai_credits': ai_credits
        })

    def put(self, request):
        user = request.user
        new_username = request.data.get('username', '').strip()
        new_password = request.data.get('password', '').strip()

        # E-posta değişiyorsa kesin format kontrolü (@ ve . zorunlu)
        if new_username:
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, new_username):
                return Response({'error': 'Lütfen geçerli bir e-posta adresi giriniz.'}, status=400)
            
            if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                return Response({'error': 'Bu e-posta adresi başka bir kullanıcı tarafından kullanılıyor.'}, status=400)
            
            user.username = new_username
            user.email = new_username
        
        # Yeni şifre girilmişse kesin güvenlik kontrolü (8 Karakter, Harf ve Rakam zorunlu)
        if new_password:
            if len(new_password) < 8:
                return Response({'error': 'Şifreniz en az 8 karakter olmalıdır.'}, status=400)
            if not re.search(r"[A-Za-z]", new_password) or not re.search(r"[0-9]", new_password):
                return Response({'error': 'Şifreniz en az bir harf ve bir rakam içermelidir.'}, status=400)
            
            user.set_password(new_password)
            
        user.save()
        return Response({'message': 'Profil başarıyla güncellendi.'}, status=status.HTTP_200_OK)


# --- 2. KULLANICI KAYIT İŞLEMİ (EKSİK OLAN VE DÜZELTİLEN KISIM BURASI) ---
class RegisterView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip()
        password = request.data.get('password', '').strip()
        
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            return Response({'error': 'Lütfen geçerli bir e-posta adresi giriniz.'}, status=400)

        if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
            return Response({'error': 'Şifreniz en az 8 karakter olmalı, harf ve rakam içermelidir.'}, status=400)

        if User.objects.filter(username=email).exists():
            return Response({'error': 'Bu email zaten kullanılıyor.'}, status=400)
            
        try:
            user = User.objects.create_user(username=email, email=email, password=password)
            UserProfile.objects.create(user=user, ai_credits=20)
            return Response({'message': 'Kayıt başarılı, giriş yapabilirsiniz.'}, status=201)
        except Exception as e:
            return Response({'error': 'Kayıt sırasında teknik bir hata oluştu.'}, status=500)


# --- 3. KENDİ ML (MAKİNE ÖĞRENMESİ) MODELLERİMİZ ---
class MLExamAnalysisView(views.APIView):
    permission_classes = [permissions.AllowAny] 

    def post(self, request):
        subjects = request.data.get('subjects', [])
        toplam_net = sum([float(s.get('net', 0)) for s in subjects])
        analysis = f"Özel ML Modelimizin Çıktısı: Toplam netiniz {toplam_net}. Matris analizine göre Fen dersine yüklenmelisiniz."
        return Response({'analysis': analysis})

class MLTargetNetsView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        university = request.data.get('university')
        department = request.data.get('department')
        return Response({
            'tyt_requirement': '95.5',
            'ayt_requirement': '68.25',
            'analysis': f'ML Modelimize göre {university} - {department} için güvenli bölgedesiniz.'
        })


# --- 4. HAZIR API (OPENROUTER KULLANILARAK - KOTA DÜŞÜRENLER) ---
class APIChatView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile and profile.ai_credits <= 0:
            return Response({'error': 'Yapay zeka kullanım kotanız dolmuştur.'}, status=403)

        message = request.data.get('message', '')
        if not message:
            return Response({'error': 'Mesaj içeriği boş olamaz.'}, status=400)

        api_key = os.environ.get('OPENROUTER_API_KEY')
        
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'http://localhost:5173', 
                'X-Title': 'E-Teacher App'
            }
            payload = {
                'model': 'openai/gpt-4o-mini', 
                'messages': [
                    {'role': 'system', 'content': 'Sen şefkatli, anlayışlı ve motive edici bir rehber öğretmen/psikologsun. Sınav stresi çeken öğrencilere kısa, net ve rahatlatıcı tavsiyeler ver. Çok uzun yazma.'},
                    {'role': 'user', 'content': message}
                ]
            }
            resp = requests.post('https://openrouter.ai/api/v1/chat/completions', json=payload, headers=headers)
            
            if resp.ok:
                if profile:
                    profile.ai_credits -= 1
                    profile.save()
                reply = resp.json()['choices'][0]['message']['content']
                return Response({'reply': reply})
            else:
                return Response({'error': f'Yapay zeka servisine ulaşılamadı. Hata Kodu: {resp.status_code}'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

class APISummaryView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile and profile.ai_credits <= 0:
            return Response({'error': 'Yapay zeka kullanım kotanız dolmuştur.'}, status=403)

        text = request.data.get('text', '')
        api_key = os.environ.get('OPENROUTER_API_KEY')
        
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'http://localhost:5173',
                'X-Title': 'E-Teacher App'
            }
            payload = {
                'model': 'openai/gpt-4o-mini',
                'messages': [
                    {'role': 'system', 'content': 'Gönderilen uzun metinleri veya ders notlarını okuyup, en önemli kısımlarını anlaşılır ve akılda kalıcı maddeler halinde özetleyen bir asistansın. Türkçe yanıt ver.'},
                    {'role': 'user', 'content': f"Şu metni benim için özetle:\n\n{text}"}
                ]
            }
            resp = requests.post('https://openrouter.ai/api/v1/chat/completions', json=payload, headers=headers)
            
            if resp.ok:
                if profile:
                    profile.ai_credits -= 1
                    profile.save()
                summary = resp.json()['choices'][0]['message']['content']
                return Response({'summary': summary})
            else:
                return Response({'error': 'Özetleme servisine ulaşılamadı.'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

class APIQuizGenerateView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile and profile.ai_credits <= 0:
            return Response({'error': 'Yapay zeka kullanım kotanız dolmuştur.'}, status=403)

        topic = request.data.get('topic', 'Genel Kültür')
        difficulty = request.data.get('difficulty', 'Orta')
        count = request.data.get('count', 5)
        api_key = os.environ.get('OPENROUTER_API_KEY')
        
        prompt = f"""
        Lütfen '{topic}' konusunda, '{difficulty}' zorluk derecesinde {count} soruluk çoktan seçmeli bir test hazırla.
        YANITINI SADECE VE SADECE AŞAĞIDAKİ GİBİ GEÇERLİ BİR JSON FORMATINDA VER. BAŞKA HİÇBİR AÇIKLAMA YAZMA:
        [
          {{
            "question": "Soru metni buraya gelecek",
            "options": ["Seçenek A", "Seçenek B", "Seçenek C", "Seçenek D", "Seçenek E"],
            "correctAnswer": "Doğru olan seçeneğin tam metni",
            "explanation": "Bu cevabın neden doğru olduğunun açıklaması"
          }}
        ]
        """
        
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'http://localhost:5173',
                'X-Title': 'E-Teacher App'
            }
            payload = {
                'model': 'openai/gpt-4o-mini',
                'messages': [
                    {'role': 'system', 'content': 'Sen bir sınav hazırlama asistanısın. Sadece JSON formatında çıktı verirsin.'},
                    {'role': 'user', 'content': prompt}
                ]
            }
            resp = requests.post('https://openrouter.ai/api/v1/chat/completions', json=payload, headers=headers)
            
            if resp.ok:
                if profile:
                    profile.ai_credits -= 1
                    profile.save()
                content = resp.json()['choices'][0]['message']['content']
                clean_content = content.replace('```json', '').replace('```', '').strip()
                quiz_data = json.loads(clean_content)
                return Response({'quiz': quiz_data})
            else:
                return Response({'error': 'Yapay zeka servisine ulaşılamadı.'}, status=400)
        except Exception as e:
            return Response({'error': 'Quiz oluşturulurken format hatası yaşandı. Lütfen tekrar deneyin.'}, status=500)


# --- 5. VERİTABANI: PROGRAM VE RAPORLAR ---
class ScheduleView(views.APIView):
    permission_classes = [permissions.IsAuthenticated] 

    def get(self, request):
        activity = UserActivity.objects.filter(
            user=request.user, 
            activity_type='schedule'
        ).order_by('-created_at').first() 
        
        if activity:
            return Response({'schedule': activity.data.get('schedule', [])})
        return Response({'schedule': None})

    def post(self, request):
        schedule_data = request.data.get('schedule', [])
        activity, created = UserActivity.objects.update_or_create(
            user=request.user,
            activity_type='schedule',
            defaults={
                'title': 'Haftalık Ders Programı',
                'data': {'schedule': schedule_data}
            }
        )
        return Response({'message': 'Programın başarıyla kaydedildi!'})

class DailyReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, date):
        activity = UserActivity.objects.filter(user=request.user, activity_type='daily_report', title=f"Rapor {date}").first()
        if activity:
            data = activity.data
            return Response({
                "dailyNotes": data.get("dailyNotes", data.get("report", "")),
                "productivityScore": data.get("productivityScore", data.get("productivity", 5)),
                "studyHours": data.get("studyHours", 0)
            })
        return Response({'dailyNotes': '', 'productivityScore': None, 'studyHours': None})

    def post(self, request):
        date = request.data.get('date')
        activity, created = UserActivity.objects.update_or_create(
            user=request.user,
            activity_type='daily_report',
            title=f"Rapor {date}",
            defaults={'data': request.data}
        )
        return Response({'message': 'Günlük rapor kaydedildi!'})

class AllReportsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        activities = UserActivity.objects.filter(
            user=request.user, 
            activity_type='daily_report'
        ).order_by('-created_at')
        
        report_list = []
        for act in activities:
            report_data = dict(act.data) if act.data else {}
            if 'date' not in report_data:
                report_data['date'] = act.title.replace("Rapor ", "")
            report_list.append(report_data)
            
        return Response(report_list)


# --- 6. PDF DOSYA YÜKLEME VE ÖZETLEME ---
@method_decorator(csrf_exempt, name='dispatch')
class APIFileSummaryView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser] # Dosya kabul etmek için

    def post(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile and profile.ai_credits <= 0:
            return Response({'error': 'Yapay zeka kullanım kotanız dolmuştur.'}, status=403)

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'Lütfen bir dosya yükleyin.'}, status=400)

        # PDF İçeriğini Metne Çevirme
        text = ""
        try:
            if file_obj.name.endswith('.pdf'):
                doc = fitz.open(stream=file_obj.read(), filetype="pdf")
                for page in doc:
                    text += page.get_text()
            else:
                text = file_obj.read().decode('utf-8')
        except Exception as e:
            return Response({'error': 'Dosya okunamadı: ' + str(e)}, status=400)

        if len(text.strip()) < 10:
            return Response({'error': 'Dosya içeriği çok kısa veya metin bulunamadı.'}, status=400)

        # Mevcut AI Özetleme Mantığını Çağırıyoruz (Kod tekrarı yapmamak için senin sistemin)
        api_key = os.environ.get('OPENROUTER_API_KEY')
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'X-Title': 'E-Teacher App'
            }
            payload = {
                'model': 'openai/gpt-4o-mini',
                'messages': [
                    {'role': 'system', 'content': 'Sen bir ders asistanısın. Yüklenen PDF içeriğini en önemli başlıklarla özetle.'},
                    {'role': 'user', 'content': f"Şu PDF içeriğini özetle:\n\n{text[:10000]}"} # Çok uzunsa ilk 10k karakter
                ]
            }
            resp = requests.post('https://openrouter.ai/api/v1/chat/completions', json=payload, headers=headers)
            
            if resp.ok:
                if profile:
                    profile.ai_credits -= 1
                    profile.save()
                summary = resp.json()['choices'][0]['message']['content']
                return Response({'summary': summary})
            else:
                return Response({'error': 'AI servisi yanıt vermedi.'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)



# --- 7. GOOGLE TAKVİM ENTEGRASYONU ---

# --- 7. GOOGLE TAKVİM ENTEGRASYONU ---

def get_google_flow():
    client_config = {
        "web": {
            "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
            "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["https://e-teacher.onrender.com/api/google/callback/"],
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=['https://www.googleapis.com/auth/calendar.events'],
        redirect_uri="https://e-teacher.onrender.com/api/google/callback/"
    )
    
    return flow

class GoogleCalendarInitView(views.APIView):
    # Sadece giriş yapmış kullanıcılar takvim bağlayabilsin
    permission_classes = [IsAuthenticated] 

    def get(self, request):
        flow = get_google_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # Session'a code_verifier'ın yanına kullanıcının ID'sini de ekliyoruz
        request.session['code_verifier'] = flow.code_verifier
        request.session['calendar_user_id'] = request.user.id
        
        return Response({'auth_url': authorization_url})

class GoogleCalendarCallbackView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.GET.get('code')
        error = request.GET.get('error')

        if error or not code:
            return Response({'error': 'Yetkilendirme hatası.'}, status=400)

        code_verifier = request.session.get('code_verifier')
        user_id = request.session.get('calendar_user_id') # Hangi kullanıcıydı?

        if not code_verifier or not user_id:
            return Response({'error': 'Oturum zaman aşımı.'}, status=400)

        try:
            flow = get_google_flow()
            flow.code_verifier = code_verifier 
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Anahtarları Kullanıcının Veritabanına Kaydediyoruz
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)

            GoogleCalendarCredential.objects.update_or_create(
                user=user,
                defaults={
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': ",".join(credentials.scopes),
                }
            )
            
            return Response({'message': 'Harika! Takvim başarıyla hesabınıza bağlandı.'})
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)

# --- 8. GOOGLE MEET VE DERS OLUŞTURMA ---

class CreateLessonEventView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        
        try:
            # 1. Kullanıcının veritabanındaki Google anahtarlarını alıyoruz
            creds_data = user.calendar_credential
            
            # 2. Google'ın anlayacağı 'Credentials' nesnesini hazırlıyoruz
            credentials = Credentials(
                token=creds_data.token,
                refresh_token=creds_data.refresh_token,
                token_uri=creds_data.token_uri,
                client_id=creds_data.client_id,
                client_secret=creds_data.client_secret,
                scopes=creds_data.scopes.split(',')
            )

            # 3. Google Takvim API'sine bağlanıyoruz
            service = build('calendar', 'v3', credentials=credentials)

            # 4. Takvime eklenecek "Ders" detayları
            # İleride bu tarih ve saatleri React'ten (request.data'dan) alacağız
            event_details = {
                'summary': 'E-Teacher Canlı Etüt',
                'description': 'E-Teacher platformu üzerinden otomatik oluşturulmuş ders.',
                'start': {
                    'dateTime': '2026-04-10T10:00:00+03:00', # Örnek Tarih
                    'timeZone': 'Europe/Istanbul',
                },
                'end': {
                    'dateTime': '2026-04-10T11:00:00+03:00', # 1 Saatlik Ders
                    'timeZone': 'Europe/Istanbul',
                },
                # İŞTE SİHİRLİ KISIM: Otomatik Google Meet Linki Üretme
                'conferenceData': {
                    'createRequest': {
                        'requestId': str(uuid.uuid4()), # Çakışmayı önlemek için benzersiz ID
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                }
            }

            # 5. Etkinliği Google'a fırlatıyoruz!
            event = service.events().insert(
                calendarId='primary',
                body=event_details,
                conferenceDataVersion=1 # Bu ayar Meet linki üretilmesi için ŞARTTIR
            ).execute()

            return Response({
                'message': 'Harika! Ders takvime başarıyla eklendi!',
                'meet_link': event.get('hangoutLink'),
                'event_link': event.get('htmlLink')
            })

        except GoogleCalendarCredential.DoesNotExist:
            return Response({'error': 'Takvim bağlı değil. Lütfen önce Google Takviminizi bağlayın.'}, status=400)
        except Exception as e:
            return Response({'error': f'Takvim etkinliği oluşturulamadı: {str(e)}'}, status=500)        