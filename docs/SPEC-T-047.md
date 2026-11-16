# SPEC T-047: build_dw.py chuyển sang thị trường Pháp (EUR, VAT, 6 kênh bán)

Owner: Codex. File được sửa: `data-analytics/ecommerce-dashboard/build_dw.py` (chỉ file này). Claude viết `generate_data.py` (T-048) song song; đừng sửa file đó.
Làm việc trong worktree `D:\Dev\ai-company-codex`, nhánh `codex/T-047`. Đọc `AGENTS.md`, `docs/collaboration.md`, `data-analytics/ecommerce-dashboard/build_dw.py` hiện tại (đang chạy đúng cho bản Việt Nam) và `market-fr/sources.md`.

## Giới hạn và luật dừng
- KHÔNG chạy build_dw.py và KHÔNG kết nối MySQL (bạn không có mật khẩu và không cần). Chỉ kiểm tra bằng `python -I -m py_compile build_dw.py` và đọc lại SQL cho đúng cú pháp MySQL 8.4.
- Tổng thời gian tối đa 25 phút, sửa lỗi cùng một chỗ tối đa 2 lần. Nếu spec mâu thuẫn hoặc không làm được: dừng và báo, không tự hạ mục tiêu.
- Giữ nguyên cấu trúc hàm hiện có (`load_staging`, `run_script`, `checks`, `main`), tên bảng staging `stg_*` (do `colname()` sinh), cách đọc mật khẩu từ `MYSQL_PWD`. Chữ trong in ra không dấu như bản hiện tại (tránh lỗi mã hóa console Windows).
- Không đưa mật khẩu hay dữ liệu cá nhân vào file.

## 1. Đầu vào: các CSV trong `data/raw/` (do T-048 sinh)
Tên cột gốc, `colname()` chuyển thành snake_case chữ thường (`amazon-order-id` thành `amazon_order_id`, `createDate` thành `createdate`...). Mọi cột nạp là VARCHAR.

| File (bảng staging) | Cột gốc theo thứ tự | Ghi chú |
|---|---|---|
| orders_amazon_fr (stg_orders_amazon_fr) | amazon-order-id, purchase-date, sku, quantity-purchased, item-price, promotion-discount, order-status, buyer-key, ship-state | purchase-date dạng `2026-05-01T17:07:11+00:00` (UTC); item-price và promotion-discount là TỔNG DÒNG, TTC, dấu phẩy thập phân (`34,90`); status Shipped / Returned / Cancelled |
| orders_temu (stg_orders_temu) | order_sn, order_time_epoch, sku_id, qty, unit_price_eur, discount_eur, status, user_hash, region_code | epoch GIÂY (UTC); unit_price_eur là giá ĐƠN VỊ TTC; discount_eur là TỔNG DÒNG; status delivered / refunded / cancelled |
| orders_shein (stg_orders_shein) | orderNo, createDate, sellerSku, number, sellingPrice, couponAmount, orderState, memberHash, province | createDate `dd/mm/YYYY HH:MM:SS` (UTC); sellingPrice giá ĐƠN VỊ TTC; couponAmount TỔNG DÒNG; orderState Completed / Return / Cancel |
| orders_tiktokshop (stg_orders_tiktokshop) | order_id, create_time_ms, seller_sku, quantity, sku_subtotal_before_discount, seller_discount, order_state, buyer_id, region | epoch MILI GIÂY; subtotal là TỔNG DÒNG TTC; có dòng trùng hoàn toàn; state COMPLETED / RETURNED / CANCELLED |
| orders_cdiscount (stg_orders_cdiscount) | OrderNumber, CreationDate, SellerProductId, Quantity, SalePrice, Discount, State, CustomerKey, DeliveryRegion | CreationDate `YYYY-MM-DD HH:MM` (UTC); SalePrice giá ĐƠN VỊ TTC; Discount TỔNG DÒNG; State Delivered / Returned / Cancelled; DeliveryRegion có ô rỗng |
| orders_web (stg_orders_web) | id, created_at_utc, sku, quantity, price, coupon_discount, fulfillment_status, customer_key, region | created_at_utc `YYYY-MM-DDTHH:MM:SSZ`; price giá ĐƠN VỊ TTC; coupon_discount TỔNG DÒNG; status completed / returned / cancelled |
| ads_meta, ads_tiktok, ads_google | như bản hiện tại (ads_facebook đổi tên thành ads_meta, cột `Amount spent (EUR)` thành `amount_spent_eur`) | tiền EUR, HT; Google vẫn `cost_micros` (chia 1.000.000) |
| products | sku, product_name, category, color, list_price_ttc, unit_cost_ht | |
| platform_fees | platform, category, commission_rate | category `*` là mức mặc định của sàn; có dòng riêng cho (cdiscount, Jewelry) |
| calendar_events | event_name, start_date, end_date, priority, demand_multiplier | ngày `YYYY-MM-DD`; priority nhỏ hơn = ưu tiên hơn |

Tên platform chuẩn trong kho: `amazon_fr`, `temu`, `shein`, `tiktokshop`, `cdiscount`, `web`. Kênh quảng cáo: `meta`, `tiktok`, `google`.
Khóa nối: `sku` (bảng sản phẩm), khách hàng là mã băm `customer_key`; vùng (region) là tên vùng của Pháp, có thể NULL.

## 2. Đầu ra: schema trong `lumi_dw`
Tiền dùng `DECIMAL(14,2)` (EUR), không dùng BIGINT.

- `dim_date` (date_key INT, full_date, year, month, month_name, day, weekday, is_weekend, event_name VARCHAR(30)): ngày 2026-04-30 đến 2026-11-16. `event_name` lấy từ `stg_calendar_events` (ngày nằm trong [start_date, end_date]; nhiều sự kiện trùng ngày thì lấy `priority` nhỏ nhất; không có thì NULL). Không còn CASE cứng theo ngày.
- `dim_product` (sku, product_name, category, color, list_price_ttc DECIMAL, unit_cost_ht DECIMAL).
- `dim_platform` (platform PK, display_name, channel_type): channel_type là `marketplace` cho 5 sàn, `own_store` cho `web`. display_name: Amazon.fr, Temu, Shein, TikTok Shop, Cdiscount, Boutique web.
- `dim_platform_fee` (platform, category, commission_rate DECIMAL(5,4), PK hai cột đầu).
- `dim_campaign` (campaign PK, channel).
- `dim_customer` (customer_key PK, region, first_order_date, first_platform): giữ cách tính hiện tại, đổi `province` thành `region`; `first_order_date` theo giờ Paris.
- `fact_order_line`: line_id, order_id, platform, order_ts_utc, order_ts_local, date_key, sku, customer_key, qty, gross_ttc, discount_ttc, net_ttc, vat_amount, net_ht, platform_fee, cogs, status (completed / returned / cancelled), kèm các KEY như bản hiện tại.
- `fact_ads_daily`: như hiện tại, spend và platform_conv_value là DECIMAL(14,2), channel meta/tiktok/google.

## 3. Quy tắc biến đổi (trong `UNION` và `FACTS`)
1. Chuẩn hóa mỗi sàn về các cột: platform, order_id, ts (UTC), sku, qty, gross_ttc (TỔNG DÒNG TTC TRƯỚC giảm giá), discount_ttc (tổng dòng), status chuẩn, customer, region (NULLIF chuỗi rỗng thành NULL).
   - gross_ttc = đơn giá × qty cho Temu, Shein, Cdiscount, Web; bằng cột tổng dòng cho Amazon.fr (REPLACE dấu phẩy thành chấm, rồi `+0`) và TikTok Shop.
   - Mapping status: Amazon Shipped / Returned / Cancelled; Temu delivered / refunded / cancelled; Shein Completed / Return / Cancel; TikTok viết hoa; Cdiscount Delivered / Returned / Cancelled; Web viết thường. Tất cả về `completed`, `returned`, `cancelled`.
   - ts: Amazon `STR_TO_DATE(LEFT(purchase_date,19),'%Y-%m-%dT%H:%i:%s')`; Temu `FROM_UNIXTIME(epoch)` và TikTok `FROM_UNIXTIME(ms/1000)` (session đã `SET time_zone='+00:00'`); Shein `%d/%m/%Y %H:%i:%s`; Cdiscount `%Y-%m-%d %H:%i`; Web như hiện tại. Mọi mốc coi là UTC.
   - TikTok: loại dòng trùng hoàn toàn bằng `SELECT DISTINCT *` như hiện tại.
2. Giờ địa phương Paris: `order_ts_local = ts + INTERVAL (CASE WHEN ts >= '2026-03-29 01:00:00' AND ts < '2026-10-25 01:00:00' THEN 2 ELSE 1 END) HOUR` (giờ mùa hè CEST so với CET; viết chú thích). `date_key` tính từ `order_ts_local`.
3. VAT 20%: `net_ttc = gross_ttc - discount_ttc`; `net_ht = ROUND(net_ttc / 1.2, 2)`; `vat_amount = net_ttc - net_ht`.
4. Hoa hồng: `rate = COALESCE(mức của (platform, category), mức của (platform, '*'))` (LEFT JOIN hai lần từ `dim_platform_fee` qua `dim_product.category`); `platform_fee = ROUND(net_ttc * rate, 2)`. Hoa hồng tính trên giá TTC, coi khoản phí là HT.
5. `cogs = qty * unit_cost_ht`.
6. Quảng cáo: ngày Meta `Day` (YYYY-MM-DD), TikTok `stat_time_day` (YYYY/MM/DD), Google `date`; Google spend = `cost_micros / 1000000` (làm tròn 2 số lẻ).
7. Views (chỉ tính status `completed`; doanh thu theo `net_ht`):
   - `v_sales_daily`: full_date, event_name, platform, orders, revenue (SUM net_ht), platform_fee, cogs, profit_before_ads (net_ht - platform_fee - cogs).
   - `v_sku_profit`: sku, category, units, revenue, profit_before_ads.
   - `v_campaign_perf`: channel, campaign, spend, clicks, platform_conversions, platform_value, platform_roas (platform_value / spend; platform_value là TTC do nền tảng báo).

## 4. Hàm `checks` (in không dấu)
Giữ tinh thần hiện tại, cập nhật cho 6 sàn: số dòng staging so với fact từng sàn; TikTok loại bao nhiêu dòng trùng; mất dòng ở sàn khác (phải bằng 0); khách thiếu; vùng thiếu ở dim_customer; khoảng ngày; đối chiếu `gross_ttc - discount_ttc - net_ttc` (phải 0) và `net_ttc - net_ht - vat_amount` (phải 0); đơn net <= 0; doanh thu và lợi nhuận trước ads theo sàn (đơn vị nghìn EUR); 5 SKU lỗ nhất so với `truth["loss_making_skus_after_discount_and_fees"]`; ROAS theo chiến dịch. Bỏ phép so sánh "FB vs đơn web".

## 5. Tiêu chí hoàn thành
- `python -I -m py_compile build_dw.py` qua.
- Mọi bảng, cột, view đúng tên ở trên; không còn tham chiếu đến shopee, lazada, VND; `province` chỉ được phép xuất hiện như tên cột GỐC của file Shein (stg_orders_shein.province).
- Ghi handoff vào cuối `TASKS.md` dưới T-047 (không sửa dòng khác): đã làm gì, chưa kiểm chứng gì (chưa chạy với MySQL).
