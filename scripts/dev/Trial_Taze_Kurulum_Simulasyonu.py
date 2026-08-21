from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import modular_app.services.license_policy as policy
from license_app import check_or_create_device_trial, check_license_status


class MemoryRepository:
    def __init__(self):
        self.values = {}

    def get_setting(self, key, default=""):
        return self.values.get(key, default)

    def set_setting(self, key, value):
        self.values[str(key)] = str(value)


print("=== TAZE KURULUM / YEREL KAYIT SILINMIS SIMULASYONU ===")
print("Gercek SQLite ve AppData dosyalarina dokunulmaz.\n")

server_before = check_or_create_device_trial()
print("Sunucudaki trial:")
print("  online          :", server_before.online)
print("  ok              :", server_before.ok)
print("  trial_started_at:", server_before.trial_started_at)
print("  server_now      :", server_before.server_now)
print()

with TemporaryDirectory() as temp_dir:
    old_dir = policy.MACHINE_STATE_DIR
    old_file = policy.MACHINE_STATE_FILE

    try:
        policy.MACHINE_STATE_DIR = Path(temp_dir)
        policy.MACHINE_STATE_FILE = Path(temp_dir) / ".license_state.json"

        repo = MemoryRepository()

        result = policy.evaluate_license_gate(
            repo,
            checker=check_license_status,
            trial_checker=check_or_create_device_trial,
        )

        print("Simule edilen taze kurulum sonucu:")
        print("  allowed :", result.allowed)
        print("  mode    :", result.mode)
        print("  message :", result.message)
        print("  remaining:", result.remaining)
        print()
        print("Sunucudan geri yazilan trial tarihi:")
        print(" ", repo.get_setting("license/unlicensed_started_at", "<yok>"))
        print()
        print("Gecici yerel state olustu mu?:", policy.MACHINE_STATE_FILE.exists())

    finally:
        policy.MACHINE_STATE_DIR = old_dir
        policy.MACHINE_STATE_FILE = old_file

print("\nTEST TAMAMLANDI - gercek kullanici verileri degistirilmedi.")
