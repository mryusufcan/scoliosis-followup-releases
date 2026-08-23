# `.quarantine` ve `.restore_points` Alan Analizi

**Tarih:** 20 Ağustos 2026  
**Kapsam:** Yalnızca ölçüm ve SHA-256 karşılaştırması; bu analiz sırasında dosya silinmedi.

## Toplam alan

| Klasör | Boyut | Dosya sayısı | Değerlendirme |
|---|---:|---:|---|
| `.quarantine` | **1,811 GiB** | 32.255 | Deneysel landmark laboratuvarı, sanal ortam ve model adayları. |
| `.restore_points` | **1,569 GiB** | 24.152 | Geri alma kopyaları; bunun 1,567 GiB’ı tek büyük restore point içinde. |
| **Brüt toplam** | **3,380 GiB** | 56.407 | Kopya tekrarları dahil toplam. |

## `.quarantine` dağılımı

`.quarantine` alanının 1,808 GiB’lık bölümü `.quarantine\landmark_lab` altındadır.

| Alt alan | Boyut | Sınıf |
|---|---:|---|
| `.quarantine\landmark_lab\.venv` | **1,488 GiB** | Deneysel Python sanal ortamı; yeniden kurulabilir, ancak deney tekrar kullanılacaksa korunmalı. |
| `weights_quarantine` | 178,13 MiB | Deneysel ağırlık/checkpoint arşivi; model doğrulaması tamamlanmadan silinmemeli. |
| `onnx_candidate` | 92,34 MiB | ONNX aday model dosyaları; aktif deneysel model olabilir. |
| `v2_landmark_candidate` | 92,34 MiB | İkinci ONNX/model adayı; adaylar karşılaştırılmadan silinmemeli. |
| `fixtures` ve küçük Python dosyaları | yaklaşık 0,2 MiB | Test/deney yardımcıları. |
| `Vertebra-Landmark-Detection_b9fc05c` | 3,45 MiB | Küçük deneysel kaynak/fixture alanı. |

## Birebir tekrar analizi

En büyük restore point şu klasördür:

```text
.restore_points\landmark_lab_adapter_20260820_114227
```

Bu restore point’in **1,567 GiB’lık bölümü**, aşağıdaki aktif quarantine alanıyla karşılaştırıldı:

```text
.quarantine\landmark_lab
```

SHA-256 karşılaştırmasında aynı göreli yola ve aynı içeriğe sahip **23.976 dosya** bulundu. Bu dosyaların toplamı **1.604,82 MiB**, yani yaklaşık **1,567 GiB**’dır. Dolayısıyla iki klasörün brüt toplamındaki en büyük tekrar budur.

> Bu ölçüm, aynı içeriğin iki yerde tutulduğunu gösterir; ancak restore point’in geri alma amacı taşıması nedeniyle otomatik olarak gereksiz olduğu anlamına gelmez.

## Güvenli temizlik adayları

| Aday | Yaklaşık kazanım | Risk | Öneri |
|---|---:|---|---|
| Büyük restore point içindeki birebir `.quarantine\landmark_lab` kopyası | **1,567 GiB** | Deneysel landmark çalışmasına geri dönüş kaybolur. | Harici arşiv veya yeni doğrulanmış restore point olmadan silme. |
| `.quarantine\landmark_lab\.venv` | **1,488 GiB** | Deneysel ortam yeniden çalıştırılamaz; paketler tekrar kurulmalıdır. | `requirements`/kurulum adımları doğrulanırsa en güvenli büyük aday. |
| `weights_quarantine` | 178,13 MiB | Model checkpoint geri dönüşü kaybolur. | Model adayları kesinleştirilmeden koru. |
| `onnx_candidate` + `v2_landmark_candidate` | yaklaşık 184,68 MiB | Aday model karşılaştırması ve rollback kaybolur. | Aktif model sürümü kesinleştikten sonra tek aday bırakılabilir. |
| Diğer küçük restore point’ler | yaklaşık 2,1 MiB | Düşük | Boyut kazancı çok az; korumak daha mantıklı. |

## Sonuç

Matematiksel olarak en büyük “tekrar” alanı **yaklaşık 1,567 GiB**’dır. `.quarantine` içindeki en büyük yeniden üretilebilir alan ise **1,488 GiB’lık deneysel sanal ortamdır**. İkisi aynı şey değildir: birincisi geri alma kopyası, ikincisi deneysel çalışma ortamıdır.

Bu nedenle güvenli sıra şöyledir: önce deneysel landmark ortamının yeniden kurulabilirliğini doğrula, sonra büyük restore point’i harici bir arşive taşı veya retention politikasına al, en son aktif model adaylarını tekilleştir. Bu rapor hazırlanırken hiçbir `.quarantine` veya `.restore_points` içeriği silinmemiştir.
