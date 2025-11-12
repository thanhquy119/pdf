# app.py
import os
import io
import logging
import tempfile
from typing import List

import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image, ImageOps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="PDF HEHE", page_icon="📄", layout="wide")

# Read Adobe credentials from environment (prevent NameError)
ADOBE_CLIENT_ID = os.getenv("ADOBE_CLIENT_ID")
ADOBE_CLIENT_SECRET = os.getenv("ADOBE_CLIENT_SECRET")

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

def images_to_pdf_local(images_bytes_list: List[bytes],
                        max_width: int = 1600,
                        max_height: int = 1600,
                        quality: int = 75,
                        dpi: int = 150) -> bytes:
    """
    Tạo PDF từ list ảnh theo phương pháp local:
    - resize nếu ảnh quá lớn (giữ tỉ lệ)
    - chuyển sang JPEG với quality để giảm dung lượng
    - ghép các ảnh JPEG vào PDF (với DPI)
    """
    pil_images = []
    for b in images_bytes_list:
        img = Image.open(io.BytesIO(b))
        # Handle orientation / exif
        img = ImageOps.exif_transpose(img)

        # convert to RGB (removes alpha)
        if img.mode not in ("RGB",):
            img = img.convert("RGB")

        w, h = img.size
        scale = min(1.0, max_width / w, max_height / h)
        if scale < 1.0:
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.LANCZOS)

        # Save to bytes as JPEG to reduce size
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        buf.seek(0)
        pil_images.append(Image.open(buf).convert("RGB"))

    if not pil_images:
        raise ValueError("No images provided")

    out = io.BytesIO()
    pil_images[0].save(out, format="PDF", save_all=True, append_images=pil_images[1:], resolution=dpi)
    out.seek(0)
    return out.read()

def images_to_pdf_with_adobe(images_bytes_list: List[bytes]) -> bytes:
    """
    Best-effort example: dùng Adobe PDF Services SDK để tạo PDF từ ảnh.
    Yêu cầu: ADOBE_CLIENT_ID và ADOBE_CLIENT_SECRET đã set trong env.
    Lưu ý: SDK có thể có API khác nhau theo phiên bản — hàm này cố gắng xử lý
    trường hợp phổ biến nhưng có thể cần chỉnh khi bạn cài SDK thực tế.
    """
    if not ADOBE_CLIENT_ID or not ADOBE_CLIENT_SECRET:
        raise RuntimeError("Adobe credentials missing in environment variables")

    try:
        # Lazy import Adobe SDK (nếu không cài sẽ ném ImportError)
        from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
        from adobe.pdfservices.operation.pdfservices import PDFServices
        # The exact CreatePDFOperation class / methods may vary by SDK version:
        try:
            from adobe.pdfservices.operation.pdfops.create_pdf_operation import CreatePDFOperation
            from adobe.pdfservices.operation.io.file_ref import FileRef
        except Exception:
            # fallback names/locations for other SDK versions
            from adobe.pdfservices.operation.pdfops.create_pdf import CreatePDFOperation
            from adobe.pdfservices.operation.io.file_ref import FileRef

        # Prepare credentials and service client
        credentials = ServicePrincipalCredentials(client_id=ADOBE_CLIENT_ID, client_secret=ADOBE_CLIENT_SECRET)
        pdf_services = PDFServices(credentials=credentials)

        # Save images to temp files then create FileRef
        temp_paths = []
        for idx, b in enumerate(images_bytes_list):
            # use system temp directory
            fd, tmp_path = tempfile.mkstemp(suffix=f"_{idx}.jpg")
            os.close(fd)
            # write JPEG-optimized copy to reduce upload size
            with open(tmp_path, "wb") as f:
                im = Image.open(io.BytesIO(b)).convert("RGB")
                im = ImageOps.exif_transpose(im)
                im.save(f, format="JPEG", quality=80, optimize=True)
            temp_paths.append(tmp_path)

        # Create operation and set input file refs
        create_pdf_op = CreatePDFOperation.create_new()
        file_refs = [FileRef.create_from_local_file(p) for p in temp_paths]

        # Depending on SDK, set_input may accept a list or single; try both
        try:
            create_pdf_op.set_input(file_refs)
        except Exception:
            # try to chain or add input in another way (best effort)
            for fr in file_refs:
                try:
                    create_pdf_op.add_input(fr)
                except Exception:
                    pass

        result = pdf_services.execute(create_pdf_op)
        # The result may offer get_as_stream or get_result etc
        if hasattr(result, "get_as_stream"):
            result_stream = result.get_as_stream()
            if hasattr(result_stream, "read"):
                pdf_bytes = result_stream.read()
            else:
                pdf_bytes = result_stream
        elif hasattr(result, "get_result"):
            rr = result.get_result()
            if hasattr(rr, "get_content"):
                stream = rr.get_content()
                if hasattr(stream, "read"):
                    pdf_bytes = stream.read()
                else:
                    pdf_bytes = stream
            else:
                # fallback: try to convert to bytes
                pdf_bytes = bytes(rr)
        else:
            # Unknown result shape: try to convert
            pdf_bytes = bytes(result)

        # cleanup temp files
        for p in temp_paths:
            try:
                os.remove(p)
            except Exception:
                pass

        return pdf_bytes

    except ImportError as ie:
        logger.exception("Adobe SDK not installed")
        raise RuntimeError("Adobe SDK not installed. Install adobe-pdfservices-sdk to use Adobe path.") from ie
    except Exception as e:
        logger.exception("Adobe images->PDF error")
        # ensure temp cleanup on error
        try:
            for p in temp_paths:
                if os.path.exists(p):
                    os.remove(p)
        except Exception:
            pass
        raise

def images_to_pdf(images_bytes_list: List[bytes],
                  use_adobe: bool = False,
                  **local_kwargs) -> bytes:
    """
    Wrapper: nếu use_adobe True => gọi Adobe (yêu cầu credentials).
    Ngược lại dùng phương pháp local nén/resample.
    """
    if use_adobe:
        return images_to_pdf_with_adobe(images_bytes_list)
    else:
        return images_to_pdf_local(images_bytes_list, **local_kwargs)

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
    if not ADOBE_CLIENT_ID or not ADOBE_CLIENT_SECRET:
        logger.warning("Adobe credentials missing (ADOBE_CLIENT_ID / ADOBE_CLIENT_SECRET). Skipping conversion.")
        st.error("Adobe credentials missing — không thể chuyển PDF→DOCX. \
Thiết lập ADOBE_CLIENT_ID và ADOBE_CLIENT_SECRET trong biến môi trường.")
        return None

    try:
        # Lazy import Adobe SDK to avoid errors at startup
        from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
        from adobe.pdfservices.operation.pdfservices import PDFServices
        from adobe.pdfservices.operation.pdfjobs.jobs.export_pdf_job import ExportPDFJob
        from adobe.pdfservices.operation.pdfjobs.params.export_pdf.export_pdf_params import ExportPDFParams
        from adobe.pdfservices.operation.pdfjobs.params.export_pdf.export_pdf_target_format import ExportPDFTargetFormat
        from adobe.pdfservices.operation.io.stream_asset import StreamAsset
        from adobe.pdfservices.operation.io.file_ref import FileRef

        credentials = ServicePrincipalCredentials(client_id=ADOBE_CLIENT_ID, client_secret=ADOBE_CLIENT_SECRET)
        pdf_services = PDFServices(credentials=credentials)

        # Save PDF bytes to temp file and create FileRef (common SDK pattern)
        fd, tmp_pdf = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        with open(tmp_pdf, "wb") as f:
            f.write(pdf_bytes)

        input_ref = FileRef.create_from_local_file(tmp_pdf)

        export_pdf_params = ExportPDFParams(target_format=ExportPDFTargetFormat.DOCX)
        export_job = ExportPDFJob(input_ref, export_pdf_params)

        location = pdf_services.submit(export_job)
        pdf_services_response = pdf_services.get_job_result(location, ExportPDFResult := None)  # placeholder - handle generically

        # The SDK shapes vary; try common retrieval patterns
        try:
            # If response supports get_result / get_asset etc
            result_asset = pdf_services_response.get_result().get_asset()
            stream_asset = pdf_services.get_content(result_asset)
            asset_stream = stream_asset.get_input_stream()
            if hasattr(asset_stream, "read"):
                docx_bytes = asset_stream.read()
            else:
                docx_bytes = asset_stream
        except Exception:
            # fallback: try to fetch bytes directly
            # Some SDKs return a FileRef or direct bytes
            try:
                docx_bytes = pdf_services_response.get_content()
            except Exception as e:
                logger.exception("Không thể đọc kết quả Adobe PDF→DOCX")
                raise

        # cleanup temp
        try:
            os.remove(tmp_pdf)
        except Exception:
            pass

        return docx_bytes

    except ImportError as ie:
        logger.exception("Adobe SDK not installed")
        st.error("Adobe SDK không được cài. Cài package adobe-pdfservices-sdk nếu muốn dùng tính năng này.")
        return None
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

        # Compression / resize options
        st.markdown("**Tùy chọn nén / resize**")
        max_width = st.slider("Max chiều ngang (px)", min_value=400, max_value=5000, value=1600, step=100)
        max_height = st.slider("Max chiều cao (px)", min_value=400, max_value=5000, value=1600, step=100)
        quality = st.slider("JPEG quality (cao → size lớn)", min_value=20, max_value=95, value=75, step=5)
        dpi = st.slider("DPI (độ phân giải PDF)", min_value=72, max_value=300, value=150, step=1)

        use_adobe = st.checkbox("Dùng Adobe PDF Services để tạo PDF (yêu cầu ADOBE_CLIENT_ID/ADOBE_CLIENT_SECRET)", value=False)

        if st.button("Chuyển và tải xuống"):
            try:
                bytes_list = [f.read() for f in imgs]
                if use_adobe:
                    try:
                        pdf_bytes = images_to_pdf(bytes_list, use_adobe=True)
                        st.success("Đã tạo PDF bằng Adobe PDF Services")
                        st.download_button("Tải file PDF", data=pdf_bytes, file_name=output_name, mime="application/pdf")
                    except Exception as e:
                        logger.exception("Adobe images->PDF error")
                        st.error(f"Lỗi khi gọi Adobe: {e}\nSẽ thử phương pháp local thay thế.")
                        # fallback to local
                        pdf_bytes = images_to_pdf(bytes_list, use_adobe=False,
                                                  max_width=max_width, max_height=max_height,
                                                  quality=quality, dpi=dpi)
                        st.success("Chuyển ảnh → PDF (local) thành công!")
                        st.download_button("Tải file PDF", data=pdf_bytes, file_name=output_name, mime="application/pdf")
                else:
                    pdf_bytes = images_to_pdf(bytes_list, use_adobe=False,
                                              max_width=max_width, max_height=max_height,
                                              quality=quality, dpi=dpi)
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
