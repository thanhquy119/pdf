# app.py
import os
import io
import logging
from typing import List

import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="PDF HEHE", page_icon="📄", layout="wide")

# Read Adobe credentials from environment (prevent NameError)
CLIENT_ID = os.getenv("ADOBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("ADOBE_CLIENT_SECRET")

# ================= Utility functions =================
def merge_pdfs(file_bytes_list: List[bytes]) -> bytes:
    writer = PdfWriter()
    for b in file_bytes_list:
        reader = PdfReader(io.BytesIO(b))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()

def images_to_pdf(images_bytes_list: List[bytes]) -> bytes:
    pil_images = []
    for b in images_bytes_list:
        img = Image.open(io.BytesIO(b)).convert("RGB")
        pil_images.append(img)
    out = io.BytesIO()
    if not pil_images:
        raise ValueError("No images provided")
    pil_images[0].save(out, format="PDF", save_all=True, append_images=pil_images[1:])
    out.seek(0)
    return out.read()

def delete_pages_pdf(pdf_bytes: bytes, pages_to_remove: List[int]) -> bytes:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    n = len(reader.pages)
    to_remove_set = set(pages_to_remove)
    for i in range(n):
        # page indices are 1-based externally; internally 0-based
        if (i + 1) in to_remove_set:
            continue
        writer.add_page(reader.pages[i])
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()

# PDF -> DOCX using Adobe SDK (best-effort; user must configure env vars)
def convert_pdf_to_docx_with_adobe(pdf_bytes: bytes):
    """
    Returns bytes of .docx or None if failure.
    Requires ADOBE_CLIENT_ID and ADOBE_CLIENT_SECRET set in env variables.
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        # No credentials configured
        logger.warning("Adobe credentials missing (ADOBE_CLIENT_ID / ADOBE_CLIENT_SECRET). Skipping conversion.")
        st.error("Adobe credentials missing — không thể chuyển PDF→DOCX. \
Thiết lập ADOBE_CLIENT_ID và ADOBE_CLIENT_SECRET trong biến môi trường.")
        return None

    try:
        # Import Adobe SDK lazily to avoid import errors at app startup when sdk not installed
        from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
        from adobe.pdfservices.operation.pdf_services import PDFServices
        from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType
        from adobe.pdfservices.operation.pdfjobs.jobs.export_pdf_job import ExportPDFJob
        from adobe.pdfservices.operation.pdfjobs.params.export_pdf.export_pdf_params import ExportPDFParams
        from adobe.pdfservices.operation.pdfjobs.params.export_pdf.export_pdf_target_format import ExportPDFTargetFormat
        from adobe.pdfservices.operation.pdfjobs.result.export_pdf_result import ExportPDFResult
        from adobe.pdfservices.operation.io.stream_asset import StreamAsset

        # Use credentials from environment
        credentials = ServicePrincipalCredentials(client_id="702badd4a1634f1a914cba03aa36114d", client_secret="p8e-47C4dyLDI_FbPiR3GlNmwcy_qytGZaUW")
        pdf_services = PDFServices(credentials=credentials)

        # Upload input - interface may differ between SDK versions; using best-effort calls
        input_asset = pdf_services.upload(input_stream=pdf_bytes, mime_type=PDFServicesMediaType.PDF)

        export_pdf_params = ExportPDFParams(target_format=ExportPDFTargetFormat.DOCX)
        export_pdf_job = ExportPDFJob(input_asset=input_asset, export_pdf_params=export_pdf_params)

        location = pdf_services.submit(export_pdf_job)
        pdf_services_response = pdf_services.get_job_result(location, ExportPDFResult)

        result_asset = pdf_services_response.get_result().get_asset()
        stream_asset = pdf_services.get_content(result_asset)

        # stream_asset may offer get_input_stream() or similar; handle both bytes and stream
        asset_stream = stream_asset.get_input_stream()
        # asset_stream might be BytesIO-like or already bytes
        if hasattr(asset_stream, "read"):
            return asset_stream.read()
        else:
            return asset_stream
    except Exception as e:
        logger.exception("Lỗi khi gọi Adobe SDK")
        st.error(f"Chuyển PDF→DOCX lỗi: {e}")
        return None

# ================= Streamlit UI =================
st.sidebar.header("Chọn chức năng")

# Move "Images → PDF" to top in the selectbox
mode = st.sidebar.selectbox(
    "Chức năng",
    ["Images → PDF", "Merge PDFs", "Delete pages from PDF", "PDF → DOCX"]
)

if mode == "Merge PDFs":
    uploaded = st.file_uploader("Chọn nhiều file PDF để gộp", type=["pdf"], accept_multiple_files=True)
    if uploaded:
        st.write(f"Đã chọn {len(uploaded)} file.")
        if st.button("Gộp và tải xuống"):
            try:
                bytes_list = [f.read() for f in uploaded]
                merged = merge_pdfs(bytes_list)
                st.success("Gộp thành công!")
                st.download_button("Tải file PDF gộp", data=merged, file_name="merged.pdf", mime="application/pdf")
            except Exception as e:
                logger.exception("Merge error")
                st.error(f"Lỗi: {e}")

elif mode == "Images → PDF":
    imgs = st.file_uploader("Chọn ảnh (jpg, png, ...)", type=["png","jpg","jpeg","bmp","tiff","webp"], accept_multiple_files=True)
    if imgs:
        st.write(f"Đã chọn {len(imgs)} ảnh.")
        output_name = st.text_input("Tên file PDF đầu ra", value="images.pdf")
        if st.button("Chuyển và tải xuống"):
            try:
                bytes_list = [f.read() for f in imgs]
                pdf_bytes = images_to_pdf(bytes_list)
                st.success("Chuyển ảnh → PDF thành công!")
                st.download_button("Tải file PDF", data=pdf_bytes, file_name=output_name, mime="application/pdf")
            except Exception as e:
                logger.exception("Images→PDF error")
                st.error(f"Lỗi: {e}")

elif mode == "Delete pages from PDF":
    pdf_file = st.file_uploader("Chọn file PDF", type=["pdf"])
    if pdf_file:
        st.write("File:", pdf_file.name)
        page_input = st.text_input("Nhập số trang cần xóa (ví dụ: 2,5-7,9) — các trang tính từ 1", "")
        if st.button("Xóa trang và tải xuống"):
            try:
                raw = pdf_file.read()
                # parse page_input into list of ints
                def parse_pages(s):
                    s = s.strip()
                    if not s:
                        return []
                    parts = [p.strip() for p in s.split(",") if p.strip()]
                    out = []
                    for part in parts:
                        if "-" in part:
                            a,b = part.split("-",1)
                            a=int(a); b=int(b)
                            out.extend(list(range(a, b+1)))
                        else:
                            out.append(int(part))
                    return sorted(set(out))
                pages_to_remove = parse_pages(page_input)
                if not pages_to_remove:
                    st.warning("Bạn chưa nhập trang cần xóa.")
                else:
                    new_pdf = delete_pages_pdf(raw, pages_to_remove)
                    st.success("Xóa trang thành công.")
                    out_name = pdf_file.name.replace(".pdf", "_edited.pdf")
                    st.download_button("Tải file PDF sau khi xóa trang", data=new_pdf, file_name=out_name, mime="application/pdf")
            except Exception as e:
                logger.exception("Delete pages error")
                st.error(f"Lỗi: {e}")

elif mode == "PDF → DOCX":
    pdf_file = st.file_uploader("Chọn file PDF", type=["pdf"])
    if pdf_file:
        st.write("File:", pdf_file.name)
        out_name = pdf_file.name.replace(".pdf", ".docx")
        if st.button("Chuyển và tải xuống DOCX"):
            pdf_bytes = pdf_file.read()
            with st.spinner("Gọi Adobe PDF Services..."):
                docx_bytes = convert_pdf_to_docx_with_adobe(pdf_bytes)
                if docx_bytes:
                    st.success("Chuyển thành công!")
                    st.download_button("Tải file DOCX", data=docx_bytes, file_name=out_name, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                else:
                    st.error("Không thể chuyển đổi. Kiểm tra logs / thông tin Adobe credentials.")

st.markdown("---")
