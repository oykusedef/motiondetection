# Real-Time Motion Detection & Security Surveillance System

A modern, web-based security surveillance system with real-time motion detection, user authentication, admin panel, and video recording features. Built with Python, OpenCV, Flask, and Bootstrap.

## 🚀 Features
- Real-time motion detection with OpenCV
- Live video feed in browser
- Automatic video recording on motion
- Activity logs
- User authentication (login/register)
- Admin panel for user management
- Role-based access control
- Modern, responsive UI (Bootstrap 5)
- Alarm sound on motion detection

## 🛠️ Setup
1. **Gereksinimleri yükleyin:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Uygulamayı başlatın:**
   ```bash
   python app.py
   ```
3. **Web tarayıcınızda açın:**
   - [http://localhost:5000](http://localhost:5000)

## 👤 Varsayılan Admin Girişi
- Kullanıcı adı: `admin`
- Şifre: `admin123`

## 📁 Klasör Yapısı
```
Real-Time Motion Detection/
├── app.py
├── requirements.txt
├── .gitignore
├── README.md
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── admin.html
│   └── play_recording.html
├── recordings/         # Kayıtlı videolar (git'e dahil edilmez)
├── logs/               # Hareket logları (git'e dahil edilmez)
```

## 📸 Özellikler
- Hareket algılandığında otomatik kayıt başlar.
- Kayıtlar zaman damgası ile etiketlenir.
- Kayıtlar ve loglar panelden izlenebilir.
- Hareket algılandığında kısa alarm sesi çalar.

## 📝 Lisans
MIT 