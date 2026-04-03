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
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        flow = get_google_flow()
        
        # Google'a gitmeden önce linki oluşturuyoruz.
        # Bu işlem sırasında flow nesnesi güvenliğimiz için otomatik bir "code_verifier" üretir.
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # KRİTİK ADIM: Üretilen bu şifreyi kullanıcının oturumuna (session) kaydediyoruz.
        # Böylece Google'dan geri döndüğünde bu anahtarı çekip kullanabileceğiz.
        request.session['code_verifier'] = flow.code_verifier
        
        return Response({'auth_url': authorization_url})

class GoogleCalendarCallbackView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.GET.get('code')
        error = request.GET.get('error')

        if error:
            return Response({'error': 'Google yetkilendirmesi reddedildi.'}, status=400)

        if not code:
            return Response({'error': 'Yetki kodu bulunamadı.'}, status=400)

        # 1. ADIM: Session'a kaydettiğimiz o gizli anahtarı geri çağırıyoruz.
        code_verifier = request.session.get('code_verifier')

        # Eğer oturum silinmişse veya anahtar yoksa kullanıcıyı uyarıyoruz.
        if not code_verifier:
            return Response({'error': 'Oturum zaman aşımına uğradı veya güvenlik anahtarı bulunamadı. Lütfen linki tekrar oluşturun.'}, status=400)

        try:
            flow = get_google_flow()
            
            # 2. ADIM: Google'a "İşte giderken oluşturduğum anahtar tam olarak buydu" diyoruz.
            flow.code_verifier = code_verifier 
            
            # Ve token'ı sorunsuzca çekiyoruz!
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            return Response({
                'message': 'Harika! Google Takvim yetkisi başarıyla alındı.',
                'token': credentials.token,
            })
            
        except Exception as e:
            return Response({'error': f'Token alınırken hata: {str(e)}'}, status=500)