# ⚙️ Backend Geliştirme Planı

Bu repo, E-Teacher platformunun tüm veritabanı, AI ve API süreçlerini yöneten merkezi servisidir.

## 🏗️ 1. Aşama: Temel Kurulum ve Auth (Hafta 1)
- [x] Django projesinin başlatılması ve PostgreSQL (Neon DB) bağlantısı.
- [ ] Custom User modelinin oluşturulması (Öğrenci/Eğitmen ayrımı).
- [ ] JWT (SimpleJWT) entegrasyonu ile `/api/token/` endpointlerinin hazırlanması.
- [ ] **Önemli:** CORS ayarlarının hem Web (Vercel) hem de Mobil adreslerine izin verecek şekilde yapılandırılması.

## 🧠 2. Aşama: AI ve Veri Servisleri
- [ ] Gemini/OpenAI API entegrasyonu için servis katmanı oluşturulması.
- [ ] Psikolojik destek chatbot'u için `/api/ai/chat/` endpoint'inin yazılması.
- [ ] YÖK Atlas verilerinin (Hedef Net) işlenmesi için veri modellerinin kurulması.

## 🚀 3. Aşama: Deployment
- [ ] Render üzerinde PostgreSQL ile canlıya alma.