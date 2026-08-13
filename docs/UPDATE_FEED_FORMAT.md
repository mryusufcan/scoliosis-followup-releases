# Güncelleme denetimi

Uygulama güncelleme indirme veya kurma işlemini otomatik yapmaz. Kullanıcı, `Help → Güncellemeleri Denetle` ekranında yalnızca HTTPS ile erişilen bir sürüm dosyası tanımlayabilir.

Dosya JSON biçiminde olmalıdır:

```json
{
  "version": "1.2.0",
  "url": "https://ornek-alanadi.tr/indir/ScoliosisFollowUp-1.2.0.exe"
}
```

Uygulama farklı bir sürüm bulursa yalnızca kullanıcıya bağlantıyı gösterir. İndirme ve kurulum, kullanıcı onayı olmadan başlatılmaz.
