# Video Watermark Remover

Hapus watermark dari video otomatis via GitHub Actions.

## Fitur
- ✅ Auto-detect SEMUA watermark (text + gambar)
- ✅ Multi-region detection (bukan cuma 4 sudut)
- ✅ 4 metode hapus: inpaint, inpaint_ns, blur, median
- ✅ Preview deteksi
- ✅ GitHub Actions (tanpa Colab)

## Cara Pakai

### Metode 1: Manual Trigger

1. Buka **Actions** tab
2. Pilih **Remove Watermark**
3. Klik **Run workflow**
4. Isi `video_url` dengan link video
5. Pilih metode
6. Klik **Run workflow**
7. Download hasil dari **Artifacts**

### Metode 2: Push Video

1. Upload video ke folder `input/` atau `videos/`
2. Commit & push
3. Workflow jalan otomatis
4. Download hasil dari Artifacts

## Metode Hapus

| Metode | Kelebihan | Kekurangan |
|--------|-----------|------------|
| inpaint | Natural | Lambat |
| inpaint_ns | Natural | Lambat |
| blur | Cepat | Terlihat blur |
| median | Cepat | Terlihat kasar |

## Deteksi Watermark

- **Temporal Variance**: Area static di banyak frame
- **Edge Stability**: Edge yang konsisten = text/logo
- **Brightness**: Pixel terang = text putih
- **Multi-region**: Semua area, bukan hanya 4 sudut

## Contoh

URL video yang didukung:
- GitHub raw: `https://raw.githubusercontent.com/.../video.mp4`
- Direct link: `https://example.com/video.mp4`

---

Created By Yad
