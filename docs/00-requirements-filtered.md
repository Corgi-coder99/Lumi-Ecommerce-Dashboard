# Dự án Data E-commerce & Dashboard: yêu cầu đã lọc từ 4 tin tuyển dụng

Ngày: 2026-11-16. Nguồn: 4 ảnh JD (Data Analyst Power BI & E-commerce, Hà Nội) và bài tìm đối tác collab (ảnh 5).
Mục tiêu: xây hệ thống dashboard nhiều nguồn dữ liệu, gần real-time, làm case study portfolio cho vị trí Data Analyst thương mại điện tử.

## 1. Phần lọc ra (chỉ giữ data, e-commerce, digital marketing)

### 1.1 Nguồn dữ liệu cần mô phỏng
| Nhóm | Nguồn | Ghi chú |
|---|---|---|
| Bán hàng | Website/Shopify, Shopee, TikTok Shop, Lazada (ảnh 5 thêm Amazon) | Mỗi sàn một lược đồ đơn hàng khác nhau, cần chuẩn hóa |
| Quảng cáo | Facebook Ads, TikTok Ads, Google Ads (ảnh 5 thêm GA4) | Chi phí, hiển thị, click, chuyển đổi theo ngày và chiến dịch |
| Sản phẩm | Danh mục, giá vốn, mã sản phẩm (SKU) | Cần để tính lợi nhuận theo SKU |

### 1.2 Chỉ số phải tính
| Chỉ số | Công thức dùng trong dự án |
|---|---|
| Doanh thu, chi phí, lợi nhuận | theo ngày, sàn, SKU. Lợi nhuận = doanh thu - giá vốn - phí sàn - chi phí quảng cáo |
| ROAS | doanh thu từ quảng cáo / chi phí quảng cáo |
| ROI | (lợi nhuận - chi phí) / chi phí |
| CPO (chi phí trên mỗi đơn) | chi phí quảng cáo / số đơn |
| CAC | chi phí marketing / số khách hàng mới |
| CIR | chi phí quảng cáo / doanh thu (%) |
| AOV | doanh thu / số đơn |
| Conversion rate | đơn / phiên truy cập (hoặc click) |
| Retention | % khách quay lại theo cohort tháng |
| LTV | doanh thu (hoặc lãi gộp) tích lũy trên mỗi khách theo cohort |

### 1.3 Công việc kỹ thuật (từ phần trách nhiệm)
1. Thu thập, làm sạch, chuẩn hóa dữ liệu đa kênh vào một mô hình chung.
2. Xây pipeline: Power Query (hoặc Python) -> MySQL / BigQuery, có kiểm tra toàn vẹn và độ chính xác.
3. Data modeling: star schema (fact đơn hàng, fact quảng cáo; dim ngày, sản phẩm, kênh, khách).
4. Phân tích hiệu quả chiến dịch và lợi nhuận theo SKU.
5. Phân tích hành vi khách: retention, AOV, LTV, tỷ lệ chuyển đổi.
6. Dashboard Power BI cho Ban giám đốc và trưởng bộ phận, hướng real-time.
7. Đề xuất giải pháp tối ưu chi phí quảng cáo từ insight.

### 1.4 Công cụ và kỹ năng (từ phần yêu cầu)
Power BI (chính), Power Query, DAX, SQL (MySQL, BigQuery, SQL Server), Python (ưu tiên), Power Platform (ưu tiên). Chứng chỉ PL-300 là điểm cộng.

## 2. Phần đã loại (không liên quan đến hệ thống)
Địa điểm, giờ làm, lương thưởng, phúc lợi, văn hóa công ty, yêu cầu bằng cấp và số năm kinh nghiệm, kỹ năng mềm chung, phối hợp với Kế toán và Sales (chỉ giữ ý "dashboard phục vụ các bộ phận").

## 3. Kiến trúc đề xuất

```
[Bộ sinh dữ liệu giả lập]  Shopee / TikTok Shop / Lazada / Web  +  FB / TikTok / Google Ads
        | (CSV/JSON mỗi sàn, lược đồ khác nhau, chạy theo lịch hoặc stream giả)
        v
[Staging + làm sạch]  Python (pandas)  -> kiểm tra chất lượng (data-quality-audit)
        v
[Kho dữ liệu]  MySQL (local) hoặc BigQuery sandbox  -> star schema
        v
[Lớp chỉ số]  view SQL + measure DAX  -> đối chiếu (metric-reconciliation)
        v
[Power BI]  4 trang: Tổng quan | Quảng cáo | Sản phẩm/SKU | Khách hàng
```

Real-time: giai đoạn 1 làm refresh theo lịch (15 phút) bằng bộ sinh dữ liệu chạy liên tục; giai đoạn 2 mới thử streaming dataset hoặc DirectQuery.

## 4. Dashboard (4 trang)
1. Tổng quan cho Ban giám đốc: doanh thu, lợi nhuận, ROAS, CIR, đơn hàng, so với kỳ trước, cảnh báo.
2. Quảng cáo: chi phí, ROAS, CAC, CPO theo kênh và chiến dịch; chiến dịch lãi và lỗ.
3. Sản phẩm: doanh thu và lợi nhuận theo SKU, top và bottom, tồn tại sàn nào bán tốt.
4. Khách hàng: cohort retention, AOV, LTV, tỷ lệ chuyển đổi.

## 5. Quy tắc dữ liệu (theo CLAUDE.md mục 6)
- Mặc định dùng dữ liệu tổng hợp do chính mình sinh ra (synthetic). Không có khách hàng thật, không có thông tin định danh.
- Công bố rõ trong portfolio: "dữ liệu mô phỏng, không phải số liệu của doanh nghiệp thật". Không bịa như số thật.
- Nếu sau này có doanh nghiệp thật cho dữ liệu (kiểu collab ở ảnh 5): phải ẩn danh, có thỏa thuận bằng văn bản, không đăng dữ liệu thô. Cần VU duyệt trước khi nhận.
- Không dùng tên, logo thương hiệu thật như thể dữ liệu của họ. Có thể dùng tên cửa hàng hư cấu.

## 6. Kế hoạch 5 bước
| Bước | Việc | Skill | Kết quả |
|---|---|---|---|
| 1 | Kế hoạch và từ điển chỉ số | analysis-planning, semantic-model-builder | file định nghĩa chỉ số, câu hỏi kinh doanh |
| 2 | Bộ sinh dữ liệu 6 tháng, 4 sàn, 3 kênh ads, có chủ đích nhúng bất thường (đợt sale, chiến dịch lỗ, SKU lỗ) | schema-mapper | CSV thô mỗi nguồn |
| 3 | Làm sạch, nạp kho, star schema, kiểm tra chất lượng | data-quality-audit, query-validation | bảng sạch, báo cáo chất lượng |
| 4 | Phân tích: ROAS, lợi nhuận SKU, cohort, funnel; tìm insight | cohort-analysis, funnel-analysis, root-cause-investigation | danh sách insight kèm số |
| 5 | Dashboard Power BI + case study | dashboard-specification, data-narrative-builder, analysis-qa-checklist | file .pbix, ảnh chụp, bài viết case study |

## 7. Việc cần VU quyết (trước bước 2)
1. Có Power BI Desktop trên máy chưa (bản miễn phí chạy trên Windows)? Nếu chưa, phương án dự phòng là dashboard HTML tĩnh.
2. Kho dữ liệu: MySQL local (đơn giản) hay BigQuery sandbox (cần tài khoản Google Cloud, JD có nhắc)?
3. Ngành hàng: ĐÃ CHỐT 2026-11-16 là phụ kiện thời trang (cửa hàng hư cấu).
   - Nhóm sản phẩm dự kiến: túi xách, ví, thắt lưng, mũ, kính, trang sức, khăn. Khoảng 80 đến 120 SKU, có biến thể màu và kích cỡ.
   - Đặc thù để nhúng vào dữ liệu: mùa vụ (Tết, 11.11, 12.12, 8/3, 20/10), giá trị đơn thấp đến trung bình, tỷ lệ hoàn trả cao hơn ở nhóm cần chọn size, khách mua lặp lại thấp, hay mua quà tặng.
   - Mốc cần có trong dữ liệu: đợt sale, chiến dịch ads lỗ, SKU lãi gộp âm sau phí sàn, kênh có tỷ lệ hoàn cao.
4. Còn chờ VU: có Power BI Desktop chưa; chọn MySQL local (đề xuất) hay BigQuery.
