import platform
import subprocess
import hashlib
import requests
import sys
import tkinter as tk
from tkinter import messagebox
from dataclasses import dataclass

# --- SUPABASE BİLGİLERİNİZ ---
SUPABASE_URL = "https://mvszpbrjedpvxtkcebzr.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im12c3pwYnJqZWRwdnh0a2NlYnpyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYyOTU1ODAsImV4cCI6MjEwMTg3MTU4MH0.4CFfuWw5TdYmmMxNe-RKZ_r4rY-O0kJCWzULz6OxQUU"

EXPIRY_DATE_FIELDS = (
    "expires_at", "expiry_date", "expiration_date", "end_date",
    "valid_until", "license_end_date", "expiry", "expires_on", "end_at",
)


def get_hwid():
    """Bilgisayarın donanım bileşenlerinden benzersiz bir HWID üretir."""
    try:
        cmd = "wmic baseboard get serialnumber"
        serial = subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
        if not serial or serial == "None":
            serial = platform.node()
    except Exception:
        serial = platform.node()
    return hashlib.sha256(serial.encode()).hexdigest()

@dataclass(frozen=True)
class LicenseStatus:
    """Lisans sunucusu denetiminin sonuç tipi.

    ``online`` alanı, uygulamanın geçici çevrimdışı izin ile gerçekten
    lisanssız kullanım durumunu ayırt etmesini sağlar.
    """
    active: bool
    online: bool
    message: str
    expires_at: str | None = None


def check_license_status() -> LicenseStatus:
    """HWID lisansını denetler ve sunucuya erişilebildiğini ayrıca bildirir."""
    hwid = get_hwid()
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/licenses?hwid=eq.{hwid}&status=eq.active"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
    }
    try:
        response = requests.get(f"{url}&select=id", headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                expires_at = None
                # Tablo şeması sürümleri arasında tarih adı değişebildiği için
                # olası alanlar ayrı denenir; lisans anahtarı gibi alanlar alınmaz.
                for field in EXPIRY_DATE_FIELDS:
                    expiry_response = requests.get(f"{url}&select={field}", headers=headers, timeout=5)
                    if expiry_response.status_code != 200:
                        continue
                    expiry_data = expiry_response.json()
                    if expiry_data and expiry_data[0].get(field) not in (None, ""):
                        expires_at = str(expiry_data[0][field]).strip()
                        break
                return LicenseStatus(True, True, "Etkin lisans doğrulandı.", expires_at)
            return LicenseStatus(False, True, "Bu bilgisayar için etkin lisans bulunamadı.")
        return LicenseStatus(False, False, f"Lisans sunucusu yanıt vermedi (HTTP {response.status_code}).")
    except Exception as exc:
        return LicenseStatus(False, False, f"Lisans sunucusuna ulaşılamadı: {exc}")


def verify_license_silent():
    """Geriye dönük uyumluluk için yalnızca etkinlik sonucunu döndürür."""
    return check_license_status().active


def activate_license(name: str, email: str, license_key: str) -> tuple[bool, str]:
    """Activate the current computer through the existing license endpoint.

    This UI-independent function is used by the PySide application. It does
    not start a second Tk window or open the clinical application itself.
    """
    name, email, license_key = str(name).strip(), str(email).strip(), str(license_key).strip()
    if not name or not email or not license_key:
        return False, "Ad, e-posta ve lisans anahtarı zorunludur."
    hwid = get_hwid()
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/licenses?license_key=eq.{license_key}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return False, "Lisans sunucusuna bağlanılamadı."
        data = response.json()
        if not data:
            return False, "Geçersiz lisans anahtarı."
        record = data[0]
        if record.get("status") != "active":
            return False, "Bu lisans etkin değil veya devre dışı bırakılmış."
        registered_hwid = record.get("hwid")
        if registered_hwid and registered_hwid != "EMPTY" and registered_hwid != hwid:
            return False, "Bu lisans anahtarı başka bir cihaza kayıtlı."
        patch_response = requests.patch(
            url,
            json={"name": name, "email": email, "hwid": hwid, "status": "active"},
            headers=headers,
            timeout=5,
        )
        if patch_response.status_code in (200, 204):
            return True, "Lisanslama başarılı."
        return False, "Lisans kaydı güncellenemedi."
    except Exception as exc:
        return False, f"Bağlantı hatası: {exc}"

def register_and_activate(name_entry, email_entry, key_entry, window):
    name = name_entry.get().strip()
    email = email_entry.get().strip()
    license_key = key_entry.get().strip()
    
    if not name or not email or not license_key:
        messagebox.showerror("Hata", "Lütfen tüm alanları doldurun!")
        return
        
    active, message = activate_license(name, email, license_key)
    if active:
        messagebox.showinfo("Başarılı", message)
        window.destroy()
        start_main_app()
    else:
        messagebox.showerror("Hata", message)

def show_license_window():
    win = tk.Tk()
    win.title("Yazılım Lisans Aktivasyonu")
    win.geometry("350x300")
    win.resizable(False, False)
    
    tk.Label(win, text="Ad Soyad:", font=("Arial", 10)).pack(pady=(20, 5))
    name_entry = tk.Entry(win, width=30, font=("Arial", 10))
    name_entry.pack()
    
    tk.Label(win, text="E-posta Adresi:", font=("Arial", 10)).pack(pady=(10, 5))
    email_entry = tk.Entry(win, width=30, font=("Arial", 10))
    email_entry.pack()
    
    tk.Label(win, text="Lisans Numarası:", font=("Arial", 10)).pack(pady=(10, 5))
    key_entry = tk.Entry(win, width=30, font=("Arial", 10))
    key_entry.pack()
    
    btn = tk.Button(win, text="Aktive Et ve Başlat", bg="green", fg="white", font=("Arial", 10, "bold"),
                    command=lambda: register_and_activate(name_entry, email_entry, key_entry, win))
    btn.pack(pady=20)
    
    win.mainloop()

def start_main_app():
    root = tk.Tk()
    root.title("Asıl Program")
    root.geometry("400x300")
    tk.Label(root, text="Program başarıyla açıldı!", font=("Arial", 14)).pack(expand=True)
    root.mainloop()

if __name__ == "__main__":
    if verify_license_silent():
        start_main_app()
    else:
        show_license_window()
