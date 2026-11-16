# Thông tin thị trường Pháp dùng cho mô hình (tra cứu công khai ngày 2026-11-16)

Nguyên tắc: chỉ đọc thông tin công khai, không cào hàng loạt, không lấy dữ liệu cá nhân. Mức tin cậy: A = trang chính thức hoặc nhiều nguồn khớp; B = nguồn thứ cấp, có mâu thuẫn; C = ước lượng của tôi.
Mọi tỷ lệ phí dưới đây là giả định đơn giản hóa để mô phỏng, cần kiểm lại bằng biểu phí chính thức (sell.amazon.fr, Seller Center, Octopia CGV) trước khi dùng cho số liệu thật.

## 1. Hoa hồng bán hàng (dùng trong platform_fees.csv)
| Sàn | Tỷ lệ mô phỏng | Cơ sở | Tin cậy |
|---|---|---|---|
| Amazon.fr | 15% | Mục "Vêtements et accessoires": 5% đến 15 €, 10% từ 15 đến 20 €, 15% trên 20 €, tối thiểu 0,30 € HT/món (bảng sell.amazon.fr được báo cáo ngày 19/10/2026). Mô hình dùng 15% phẳng vì phần lớn món trên 20 € | B |
| TikTok Shop France | 9% | Tăng từ 5% lên 9% từ 8/1/2026 (ecommerce-nation, speed-ecom). Người bán mới có ưu đãi 4% trong 60 ngày (không mô phỏng) | A |
| Cdiscount (Octopia) | 15% mặc định, 20% trang sức | Đăng ký 39,99 € HT/tháng + hoa hồng 5% đến 20% theo danh mục, tính trên giá TTC kèm phí ship. Trang sức tối đa 20% theo một nguồn | B |
| Temu (người bán nội địa EU) | 10% | Nguồn nêu khoảng 5% đến 15% theo danh mục, chốt khi ký hợp đồng | B |
| Shein (marketplace EU) | 10% | Shein công bố 10% cho site EU (0% trong 30 ngày đầu, không mô phỏng) | B |
| Cửa hàng riêng (web) | 2,5% | Phí cổng thanh toán, ước lượng | C |

Nguồn: ecommerce-nation.fr (TikTok Shop 9%), repricer.com (phí Amazon 2026), lafabriquedunet.fr và leptidigital.fr (Cdiscount), magnalister.com và retaildetail.eu (Temu), tin Reuters về việc Amazon giảm phí châu Âu tháng 12/2025.
Không có số liệu phí AliExpress cho người bán châu Âu nên AliExpress không có trong mô hình.

## 2. Lịch khuyến mãi (dùng trong calendar_events.csv)
| Sự kiện | Ngày 2026 | Tin cậy |
|---|---|---|
| French Days mùa xuân | 29/4 đến 5/5 | A (một nguồn lệch 1 ngày) |
| Fête des mères (tặng quà) | 25/5 đến 31/5 (ước lượng cho hiệu ứng mua quà) | C |
| Prime Day (Amazon) | 23/6 00:01 đến 26/6 23:59 | A |
| Soldes d'été (luật định) | 24/6 đến 28/7 (kéo dài thêm 1 tuần so với dự kiến 21/7; đa số tỉnh đại lục) | B |
| French Days mùa tựu trường | 7/9 đến 14/9 (nguồn lệch: 22 đến 28/9, 24 đến 30/9) | B |
| Jours Flash Prime (Amazon) | 6/10 đến 7/10 | A |
| Singles Day 11.11 | 10/11 đến 11/11 | C |
| Black Friday | 27/11/2026 (ngoài khoảng dữ liệu mô phỏng) | A |
| Soldes d'hiver 2027 | 6/1 đến 2/2/2027 (chưa xác nhận) | B |

Nguồn: moneyvox.fr và economie.gouv.fr (soldes), aboutamazon.eu và journaldeleconomie.fr (Prime Day), sortiraparis.com và clubic.com (French Days), icalendrier.fr (Black Friday).

## 3. Thuế và pháp lý dùng trong mô hình
- Giá bán lẻ ở Pháp là giá TTC (đã gồm VAT). VAT phổ thông 20%. Doanh thu phân tích tính theo HT = TTC / 1,2.
- Hoa hồng sàn tính trên giá TTC (theo Amazon và Cdiscount); trong mô hình coi khoản phí là HT.
- Quyền hủy trong 14 ngày của người tiêu dùng EU khiến tỷ lệ hoàn trả cao hơn ở Temu, Shein, TikTok Shop (nhân hệ số trong bộ sinh).

## 4. Không dùng (và lý do)
- leboncoin, Vinted, Facebook Marketplace: giao dịch giữa cá nhân, tin đăng gắn với người bán là cá nhân, cào hàng loạt là xử lý dữ liệu cá nhân (GDPR/CNIL).
- AliExpress, Alibaba: không có biểu phí công khai đáng tin cậy cho người bán châu Âu; Alibaba là B2B nên khác mô hình.
