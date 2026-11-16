# Đặc tả dashboard Power BI: Lumi Accessories France (dữ liệu mô phỏng)

Cửa hàng hư cấu Lumi Accessories bán phụ kiện thời trang ở Pháp, tiền tệ EUR. Nguồn: MySQL `lumi_dw`, kết nối 127.0.0.1, chế độ Import. Dữ liệu 2026-05-01 đến 2026-11-15 (giờ Paris), 6 kênh bán (Amazon.fr, Temu, Shein, TikTok Shop, Cdiscount, Boutique web) và 3 nền tảng ads (Meta, TikTok, Google).
Người xem: Ban giám đốc (trang 1), trưởng marketing (trang 2), trưởng sản phẩm/mua hàng (trang 3), CRM (trang 4).
Nguồn sự thật cho tên bảng, cột, view: `SPEC-T-047.md`. Phí sàn và lịch sale: `market-fr/sources.md`.

## 1. Mô hình dữ liệu (Model view)

Quan hệ (nhiều-một, lọc một chiều từ dim sang fact):
| Từ (fact) | Đến (dim) |
|---|---|
| fact_order_line[date_key] | dim_date[date_key] |
| fact_order_line[sku] | dim_product[sku] |
| fact_order_line[platform] | dim_platform[platform] |
| fact_order_line[customer_key] | dim_customer[customer_key] |
| fact_ads_daily[date_key] | dim_date[date_key] |
| fact_ads_daily[campaign] | dim_campaign[campaign] |
| dim_customer[first_date_key] | dim_date[date_key] (KHÔNG hoạt động, dùng USERELATIONSHIP) |

Cột chính:
- `dim_date`: date_key, full_date, year, month, month_name, day, weekday, is_weekend, event_name (từ bảng calendar_events; một sự kiện kéo dài nhiều ngày liên tiếp, nhiều sự kiện trùng ngày thì lấy priority nhỏ nhất, không có thì trống).
- `dim_platform`: platform (khóa), display_name, channel_type (`marketplace` cho 5 sàn, `own_store` cho `web`).
- `dim_product`: sku, product_name, category, color, list_price_ttc, unit_cost_ht.
- `dim_customer`: customer_key, region (vùng của Pháp, có thể trống), first_order_date (giờ Paris), first_platform.
- `dim_campaign`: campaign, channel (meta / tiktok / google).
- `dim_platform_fee`: platform, category, commission_rate (chỉ để tham chiếu, không cần nối trong model).
- `fact_order_line`: line_id, order_id, platform, order_ts_utc, order_ts_local, date_key, sku, customer_key, qty, gross_ttc, discount_ttc, net_ttc, vat_amount, net_ht, platform_fee, cogs, status.
- `fact_ads_daily`: date_key, campaign, channel, impressions, clicks, spend (HT), platform_conversions, platform_conv_value (TTC, nền tảng tự báo).

Việc cần làm trong Power Query/Model:
1. Chọn `dim_date` làm Date table (cột `full_date`).
2. Ẩn các cột khóa trong fact. Format: tiền tệ `€ #,##0` (hoặc `#,##0.00 €` cho giá trị đơn lẻ như AOV, CPC), tỷ lệ `0.0%`.
3. Thêm cột tính toán (DAX):
```dax
-- dim_customer
first_date_key = YEAR(dim_customer[first_order_date]) * 10000 + MONTH(dim_customer[first_order_date]) * 100 + DAY(dim_customer[first_order_date])
first_month = DATE(YEAR(dim_customer[first_order_date]), MONTH(dim_customer[first_order_date]), 1)

-- fact_order_line
order_date = RELATED(dim_date[full_date])
months_since_first = DATEDIFF(RELATED(dim_customer[first_month]), DATE(YEAR(fact_order_line[order_date]), MONTH(fact_order_line[order_date]), 1), MONTH)
```
Lưu ý: không có khóa nối đơn hàng với chiến dịch quảng cáo. Mọi so sánh quảng cáo và doanh thu làm ở mức ngày và kênh, không ở mức đơn.

## 2. Measure (tạo bảng rỗng `_Measures`)

```dax
-- Doanh thu (EUR)
Revenue = CALCULATE(SUM(fact_order_line[net_ht]), fact_order_line[status] = "completed")
Revenue TTC = CALCULATE(SUM(fact_order_line[net_ttc]), fact_order_line[status] = "completed")
VAT Collected = CALCULATE(SUM(fact_order_line[vat_amount]), fact_order_line[status] = "completed")
Gross Merchandise Value = CALCULATE(SUM(fact_order_line[gross_ttc]), fact_order_line[status] = "completed")
Orders = CALCULATE(DISTINCTCOUNT(fact_order_line[order_id]), fact_order_line[status] = "completed")
Units = CALCULATE(SUM(fact_order_line[qty]), fact_order_line[status] = "completed")
AOV = DIVIDE([Revenue], [Orders])
Platform Fee = CALCULATE(SUM(fact_order_line[platform_fee]), fact_order_line[status] = "completed")
COGS = CALCULATE(SUM(fact_order_line[cogs]), fact_order_line[status] = "completed")
Gross Profit = [Revenue] - [Platform Fee] - [COGS]
Gross Margin % = DIVIDE([Gross Profit], [Revenue])

-- Quảng cáo
Ad Spend = SUM(fact_ads_daily[spend])  -- HT
Net Profit = [Gross Profit] - [Ad Spend]
Net Margin % = DIVIDE([Net Profit], [Revenue])
Blended ROAS = DIVIDE([Revenue], [Ad Spend])
Platform ROAS = DIVIDE(SUM(fact_ads_daily[platform_conv_value]), [Ad Spend])
CIR = DIVIDE([Ad Spend], [Revenue])
CPO = DIVIDE([Ad Spend], [Orders])
CPC = DIVIDE([Ad Spend], SUM(fact_ads_daily[clicks]))
CTR = DIVIDE(SUM(fact_ads_daily[clicks]), SUM(fact_ads_daily[impressions]))
Ads CVR = DIVIDE(SUM(fact_ads_daily[platform_conversions]), SUM(fact_ads_daily[clicks]))
ROI = DIVIDE([Net Profit], [Ad Spend])

-- Khách hàng
New Customers = CALCULATE(COUNTROWS(dim_customer), USERELATIONSHIP(dim_customer[first_date_key], dim_date[date_key]))
CAC = DIVIDE([Ad Spend], [New Customers])
Customers = CALCULATE(DISTINCTCOUNT(fact_order_line[customer_key]), fact_order_line[status] = "completed")
Repeat Rate =
VAR c = SUMX(VALUES(fact_order_line[customer_key]), IF(CALCULATE(DISTINCTCOUNT(fact_order_line[order_id]), fact_order_line[status] = "completed") >= 2, 1, 0))
RETURN DIVIDE(c, [Customers])
Return Rate =
DIVIDE(
  CALCULATE(COUNTROWS(fact_order_line), fact_order_line[status] = "returned"),
  CALCULATE(COUNTROWS(fact_order_line), fact_order_line[status] IN {"completed", "returned"}))
Cancel Rate = DIVIDE(CALCULATE(COUNTROWS(fact_order_line), fact_order_line[status] = "cancelled"), COUNTROWS(fact_order_line))
Retention % =
VAR base = CALCULATE(DISTINCTCOUNT(fact_order_line[customer_key]), fact_order_line[months_since_first] = 0, fact_order_line[status] = "completed")
RETURN DIVIDE(CALCULATE(DISTINCTCOUNT(fact_order_line[customer_key]), fact_order_line[status] = "completed"), base)

-- Thời gian và sự kiện
Revenue PM = CALCULATE([Revenue], DATEADD(dim_date[full_date], -1, MONTH))
Revenue MoM % = DIVIDE([Revenue] - [Revenue PM], [Revenue PM])
Event Day Uplift =
VAR ev = CALCULATE(AVERAGEX(VALUES(dim_date[full_date]), [Revenue]), NOT(ISBLANK(dim_date[event_name])))
VAR normal = CALCULATE(AVERAGEX(VALUES(dim_date[full_date]), [Revenue]), ISBLANK(dim_date[event_name]))
RETURN DIVIDE(ev, normal) - 1
```
Ghi chú định nghĩa:
- Tiền tệ EUR. Giá bán là TTC; Revenue là doanh thu HT (`net_ht` = `net_ttc` / 1,2, VAT 20% đồng nhất). Giá vốn, phí sàn và Ad Spend đều coi là HT.
- Doanh thu chỉ tính đơn `completed` (thực thu sau giảm giá). Đơn hoàn trả và hủy không tính vào Revenue nhưng vẫn tính vào Return Rate và Cancel Rate.
- Return Rate by Platform: không cần measure riêng. Dùng `Return Rate` với cắt theo `dim_platform[display_name]` (và theo `dim_product[category]` cho heatmap).
- Event Day Uplift: `dim_date[event_name]` lấy từ `calendar_events`, mỗi sự kiện là một khoảng nhiều ngày liên tiếp (French Days, Prime Day, Soldes...), so sánh doanh thu trung bình ngày trong sự kiện với ngày thường.
- Blended ROAS (Revenue HT chia Ad Spend HT) là con số đáng tin hơn Platform ROAS. Lưu ý khi so sánh: Platform ROAS dùng giá trị chuyển đổi TTC do nền tảng tự báo (Meta thổi phồng khoảng 30% trong dữ liệu này) còn Ad Spend là HT, nên Platform ROAS cao hơn Blended ROAS một phần chỉ vì TTC so với HT (chênh 20%). Hiển thị cả hai cạnh nhau và ghi chú rõ trên dashboard.
- CAC dùng chi phí ads toàn bộ chia khách mới toàn bộ, nên là CAC tổng hợp (blended CAC).
- Return Rate tính theo dòng sản phẩm, không theo đơn.

## 3. Bốn trang

Bộ lọc ngày dùng chung mọi trang: `dim_date[full_date]` <= 2026-11-15 (dim_date còn chứa 2026-11-16 nhưng ngoài kỳ báo cáo).

### Trang 1: Tổng quan (Ban giám đốc)
- Thẻ KPI (6): Revenue, Gross Profit, Net Profit, Blended ROAS, CIR, Orders. Mỗi thẻ có so với tháng trước (Revenue MoM %).
- Biểu đồ đường: Revenue và Net Profit theo ngày, đánh dấu các khoảng sự kiện (event_name).
- Cột xếp chồng: Revenue theo tháng và kênh bán (`dim_platform[display_name]`).
- So sánh marketplace và boutique web: cột nhóm hoặc donut theo `dim_platform[channel_type]` cho Revenue, Gross Margin %, Return Rate.
- Bảng nhỏ: top 3 cảnh báo (chiến dịch Platform ROAS < 1, SKU lãi âm, danh mục Return Rate > 10%).
- Bộ lọc: Tháng, Kênh bán (display_name).

### Trang 2: Quảng cáo (Marketing)
- Thẻ KPI: Ad Spend, Platform ROAS, Blended ROAS, CPO, CAC, CTR.
- Bảng chiến dịch: channel, spend, clicks, CPC, CVR, Platform ROAS, tô đỏ khi ROAS < 1.
- Cột nhóm: Platform ROAS và Blended ROAS theo kênh ads (Meta, TikTok, Google), có chú thích TTC so với HT.
- Đường hoặc cột xếp chồng: Ad Spend theo ngày, tách màu theo kênh ads Meta / TikTok / Google, đối chiếu Revenue theo ngày để thấy hiệu ứng ngày sale.
- Scatter: spend (X) và ROAS (Y) theo chiến dịch, kích thước = clicks, màu = kênh ads.

### Trang 3: Sản phẩm và SKU
- Cột: Gross Profit theo danh mục. Bảng SKU: units, Revenue, Gross Profit, Gross Margin %, Return Rate.
- Danh sách "SKU lãi âm" (lọc Gross Profit < 0): phải thấy đúng 5 SKU theo `truth_summary.json`.
- Heatmap: Return Rate theo danh mục (hàng) và kênh bán (cột). Temu, Shein, TikTok Shop dự kiến cao hơn Amazon.fr, Cdiscount, Boutique web.
- Waterfall: Revenue -> phí sàn -> giá vốn -> Gross Profit -> Ad Spend -> Net Profit.

### Trang 4: Khách hàng
- Thẻ KPI: Customers, New Customers, AOV, Repeat Rate, Return Rate.
- Ma trận cohort: hàng = first_month, cột = months_since_first, giá trị = Retention % (tô màu).
- Cột: New Customers theo tháng, phân theo kênh đầu tiên (`first_platform`).
- Bar: Revenue theo vùng (region); vùng trống hiển thị là "Không rõ".
- Đường: AOV theo tháng và theo kênh bán.

## 4. Giữ "real-time" ở mức nào
Dữ liệu là mô phỏng. Hai mức làm:
1. Mặc định: Import + nút Refresh. Chạy lại `generate_data.py` rồi `build_dw.py` để tạo dữ liệu mới.
2. Demo trực tiếp (tùy chọn): đổi bảng fact sang DirectQuery trên Power BI Desktop (MySQL hỗ trợ). Chậm hơn, chỉ dùng khi quay video demo.
Power BI Service và lịch refresh tự động cần gateway và tài khoản Microsoft; không làm trong giai đoạn này.

## 5. Kết quả mong đợi để kiểm tra dashboard đúng (định tính)
(Đối chiếu với truth_summary.json, chỉ dùng để tự kiểm tra, không đưa lên dashboard.)
- Chiến dịch `TT_Live_Ceintures` có Platform ROAS dưới 1 (lỗ).
- `GG_Search_Marque` có Platform ROAS cao nhất.
- Đúng 5 SKU lãi âm, khớp danh sách `loss_making_skus_after_discount_and_fees` trong truth_summary.json.
- Prime Day (23-26/6) và French Days rentrée (7-14/9) nằm trong các ngày doanh thu cao nhất; Event Day Uplift dương rõ.
- Temu, Shein, TikTok Shop có Return Rate cao hơn Amazon.fr, Cdiscount, Boutique web.

Số tổng để đối chiếu (đơn completed, ngày ≤ 2026-11-15; đã khớp chính xác giữa MySQL và dashboard HTML ngày 2026-11-17):
- Revenue (HT) 1.186.856,31 EUR; 32.110 đơn; 50.374 sản phẩm; Gross Profit 371.116,18 EUR (31,3% doanh thu).
- Ad Spend (HT) 160.467,68 EUR; CIR 13,5%; Blended ROAS khoảng 7,4; Net Profit khoảng 210.648 EUR (17,7%).
- Khách hàng có đơn completed: 26.994; khách có từ 2 đơn trở lên: 4.312 (16,0%).
- Ngày doanh thu cao nhất: 26/6 (Prime Day, khoảng 9,9 nghìn EUR), 12/9 và 13/9 (French Days rentrée), 25/6, 10/11 (Singles Day).
- Return Rate theo kênh (dòng sản phẩm): Temu 12,3%, TikTok Shop 12,3%, Shein 12,0%, Amazon.fr 9,0%, Cdiscount 8,9%, boutique web 7,1%.
- ROAS do nền tảng báo: `TT_Live_Ceintures` 0,91 (lỗ), `GG_Search_Marque` 11,48 (cao nhất).
- 5 SKU lãi âm: LM064 (-8,5 nghìn EUR), LM002, LM013, LM060, LM081.

## 6. Kiểm tra trước khi giao (analysis-qa-checklist)
- Tổng Revenue trên Power BI bằng tổng `v_sales_daily.revenue` trong MySQL (chênh lệch = 0).
- Số đơn trên Power BI bằng số `order_id` completed khác nhau trong `fact_order_line`.
- Mỗi KPI có định nghĩa (tooltip hoặc trang "Definitions").
- Ghi chú trên dashboard: "Dữ liệu mô phỏng, không phải số liệu doanh nghiệp thật."
