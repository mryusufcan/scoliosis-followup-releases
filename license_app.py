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
REQUEST_TIMEOUT_SECONDS = 2.5
HWID_TIMEOUT_SECONDS = 2


def get_hwid():
    """Bilgisayarın donanım bileşenlerinden benzersiz bir HWID üretir."""
    try:
        result = subprocess.run(
            ["wmic", "baseboard", "get", "serialnumber"],
            capture_output=True,
            check=False,
            text=True,
            timeout=HWID_TIMEOUT_SECONDS,
        )
        values = [line.strip() for line in result.stdout.splitlines() if line.strip() and "serialnumber" not in line.lower()]
        serial = values[0] if values else ""
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
    """HWID lisansını güvenli Supabase RPC üzerinden doğrular."""
    hwid = get_hwid()
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/check_device_license"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json={"p_hwid": hwid},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return LicenseStatus(
                False,
                False,
                f"Lisans sunucusu yanıt vermedi (HTTP {response.status_code}).",
            )

        data = response.json()
        row = data[0] if isinstance(data, list) and data else (
            data if isinstance(data, dict) else {}
        )

        active = bool(row.get("active", False))
        message = str(
            row.get(
                "message",
                "Lisans sunucusundan geçerli yanıt alınamadı.",
            )
        )
        expires_at = row.get("expires_at") or None

        return LicenseStatus(
            active,
            True,
            message,
            str(expires_at).strip() if expires_at else None,
        )

    except Exception as exc:
        return LicenseStatus(
            False,
            False,
            f"Lisans sunucusuna ulaşılamadı: {exc}",
        )


def verify_license_silent():
    """Geriye dönük uyumluluk için yalnızca etkinlik sonucunu döndürür."""
    return check_license_status().active


def activate_license(
    name: str,
    email: str,
    license_key: str,
) -> tuple[bool, str]:
    """Lisansı güvenli Supabase RPC üzerinden mevcut HWID'ye bağlar."""
    name = str(name).strip()
    email = str(email).strip()
    license_key = str(license_key).strip()

    if not name or not email or not license_key:
        return False, "Ad, e-posta ve lisans anahtarı zorunludur."

    hwid = get_hwid()
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/activate_device_license"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json={
                "p_license_key": license_key,
                "p_hwid": hwid,
                "p_name": name,
                "p_email": email,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return (
                False,
                f"Lisans sunucusu yanıt vermedi (HTTP {response.status_code}).",
            )

        data = response.json()
        row = data[0] if isinstance(data, list) and data else (
            data if isinstance(data, dict) else {}
        )

        success = bool(row.get("success", False))
        message = str(
            row.get(
                "message",
                "Lisans sunucusundan geçerli yanıt alınamadı.",
            )
        )
        return success, message

    except Exception as exc:
        return False, f"Bağlantı hatası: {exc}"


# ---------------------------------------------------------------------------
# DEVICE TRIAL SERVER API
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrialServerStatus:
    online: bool
    ok: bool
    message: str
    trial_started_at: str | None = None
    server_now: str | None = None


def check_or_create_device_trial() -> TrialServerStatus:
    """Cihazın tek seferlik trial başlangıcını Supabase RPC üzerinden getirir.

    Trial başlangıç tarihi istemci tarafından gönderilmez. Sunucu aynı HWID için
    ilk oluşturduğu tarihi daima korur; reinstall/AppData silme yeni trial üretmez.
    """
    hwid = get_hwid()
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/get_or_create_device_trial"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            url,
            headers=headers,
            json={"p_hwid": hwid},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return TrialServerStatus(
                False,
                False,
                f"Deneme lisansı sunucusu yanıt vermedi (HTTP {response.status_code}).",
            )

        data = response.json()
        if isinstance(data, list):
            row = data[0] if data else {}
        elif isinstance(data, dict):
            row = data
        else:
            row = {}

        started = row.get("trial_started_at")
        server_now = row.get("server_now")
        if not started or not server_now:
            return TrialServerStatus(
                True,
                False,
                "Deneme lisansı sunucusundan geçerli tarih alınamadı.",
            )

        return TrialServerStatus(
            True,
            True,
            "Cihaz deneme kaydı doğrulandı.",
            str(started),
            str(server_now),
        )
    except Exception as exc:
        return TrialServerStatus(
            False,
            False,
            f"Deneme lisansı sunucusuna ulaşılamadı: {exc}",
        )

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
