# Khối DMCA (tuỳ chọn, mẫu): chưa áp dụng

> **Đây không phải tư vấn pháp lý.** Bản này là bản nháp kỹ thuật và cần được
> người có chuyên môn pháp lý rà soát (cả luật Việt Nam và luật Mỹ) trước khi sử
> dụng.

Tên tệp `upload-post-dmca-section.md` được giữ nguyên. Bản gốc của tệp này là
bản ghi một khối DMCA đã được dán vào điều khoản của một dịch vụ khác, mang pháp
nhân, địa chỉ và email đại diện của tác giả gốc. **Toàn bộ thông tin đó đã bị gỡ**:
nó không thuộc về chủ sở hữu ViralShorts, và việc đăng một "đại diện được chỉ
định" mà không đăng ký thật với Cơ quan bản quyền Hoa Kỳ là sai sự thật.

## ViralShorts có cần khối này không?

Mặc định **không**. Điều khoản dịch vụ (Mục 9) và trang `/report-content` đã có
quy trình tiếp nhận thông báo vi phạm, gỡ nội dung và phản đối, theo pháp luật
Việt Nam. Khối dưới đây chỉ có ích nếu bạn muốn được hưởng cơ chế "safe harbor"
của 17 U.S.C. § 512(c) khi chủ sở hữu quyền ở Mỹ khiếu nại, và để có hiệu lực thì
**phải làm cả hai việc**:

1. đăng khối này (với thông tin thật) trên trang web; **và**
2. đăng ký người đại diện chỉ định tại dmca.copyright.gov (cần tài khoản, phí lệ
   phí, và gia hạn định kỳ).

Chỉ đăng một trong hai thì không đạt hiệu lực mong muốn. ❓ Hỏi luật sư có đáng
làm không, đặc biệt nếu khách hàng chủ yếu ở Việt Nam.

## Mẫu nội dung nếu quyết định dùng (tiếng Anh, vì dành cho chủ sở hữu quyền ở Mỹ)

Thay các giữ chỗ bằng thông tin **đã đăng ký thật** với Cơ quan bản quyền Hoa Kỳ,
và chỉ đăng khi việc đăng ký đã hoàn tất.

```html
<h3>Notices under the US DMCA</h3>
<p>For rightsholders in the United States, [TÊN PHÁP NHÂN] has designated the
following agent to receive notifications of claimed infringement under 17 U.S.C.
&sect; 512(c)(2):</p>
<p>Copyright Agent, [TÊN PHÁP NHÂN], [ĐỊA CHỈ]. Email: [EMAIL HỖ TRỢ].</p>
<p>A notification must be in writing and include: a physical or electronic
signature of the owner of the exclusive right allegedly infringed, or of a person
authorised to act on their behalf; identification of the copyrighted work
claimed to have been infringed; identification of the material claimed to be
infringing and information reasonably sufficient to let us locate it; your
address, telephone number and email address; a statement that you have a
good-faith belief that the use is not authorised by the copyright owner, its
agent, or the law; and a statement, made under penalty of perjury, that the
information in the notification is accurate and that you are the owner or are
authorised to act on the owner's behalf.</p>
<p>If we remove or disable access to your material and you believe this was the
result of a mistake or a misidentification, you may send a counter-notification
to the designated agent under 17 U.S.C. &sect; 512(g), including your signature,
identification of the material and where it appeared before removal, a statement
under penalty of perjury that you have a good-faith belief it was removed by
mistake or misidentification, and your consent to the jurisdiction of the United
States federal district court for the district in which you reside or, if your
address is outside the United States, of any district in which we may be found.
We forward the counter-notification to the complaining party and may restore the
material after 10 business days unless that party notifies us that it has filed
an action seeking a court order to restrain the allegedly infringing activity.</p>
<p>In accordance with 17 U.S.C. &sect; 512(i), we terminate, in appropriate
circumstances, the accounts of users who are repeat infringers. Under 17 U.S.C.
&sect; 512(f), anyone who knowingly materially misrepresents that material is
infringing, or that it was removed by mistake or misidentification, may be liable
for the damages that misrepresentation causes.</p>
```

Nếu đăng, thêm khối này vào Mục 9 của `TERMS_VI` trong `dashboard/seo/legal.js`.

## Thông tin phải trùng với bản đăng ký

Khi nộp đăng ký tại dmca.copyright.gov, bốn thứ sau phải **giống hệt** thông tin
đã đăng trên trang, nếu không việc đăng bài không đạt mục đích:

- Tên đại diện: Copyright Agent
- Tổ chức: [TÊN PHÁP NHÂN]
- Địa chỉ: [ĐỊA CHỈ]
- Email: [EMAIL HỖ TRỢ]

Biểu mẫu đăng ký cũng bắt buộc có số điện thoại [SỐ ĐIỆN THOẠI] và các tên khác
của dịch vụ (ViralShorts, [TÊN MIỀN]).
