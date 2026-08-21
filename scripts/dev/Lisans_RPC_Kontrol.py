from license_app import check_license_status

print("=== GUVENLI LISANS RPC TESTI ===")
result = check_license_status()
print("active    :", result.active)
print("online    :", result.online)
print("message   :", result.message)
print("expires_at:", result.expires_at)
