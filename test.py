import streamlit as st
from PIL import Image, UnidentifiedImageError
import io
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import requests
import tempfile
import os

st.set_page_config(page_title="PDF HEHE", layout="wide")
# --- Load secrets ---
# Put these into Streamlit Cloud App Settings -> Secrets as shown in your screenshot.
ADOBE_CLIENT_ID = st.secrets.get("ADOBE_CLIENT_ID", None)
ADOBE_CLIENT_SECRET = st.secrets.get("ADOBE_CLIENT_SECRET", None)

# ---------- Helper functions ----------

def images_to_pdf_bytes(file_objs):
    """Convert list of uploaded file-like objects to a single PDF bytes.
       Robust: converts images to RGB, checks for invalid files, returns (pdf_bytes, errors)."""
    images_rgb = []
    errors = []
    for idx, uploaded in enumerate(file_objs, start=1):
        try:
            img = Image.open(uploaded)
            img.load()  # force load to detect corruption
            if img.mode != "RGB":
                img = img.convert("RGB")
            images_rgb.append(img)
        except UnidentifiedImageError:
            errors.append(f"File #{idx} ('{uploaded.name}') is not a valid image.")
        except Exception as e:
            errors.append(f"File #{idx} ('{uploaded.name}') error: {repr(e)}")
    if errors or not images_rgb:
        return None, errors

    pdf_bytes = io.BytesIO()
    try:
        if len(images_rgb) == 1:
            images_rgb[0].save(pdf_bytes, format="PDF")
        else:
            images_rgb[0].save(pdf_bytes, format="PDF", save_all=True, append_images=images_rgb[1:])
        pdf_bytes.seek(0)
        return pdf_bytes, None
    except Exception as e:
        return None, [f"Error saving PDF: {repr(e)}"]

def merge_pdfs_bytes(file_objs):
    merger = PdfMerger()
    try:
        for f in file_objs:
            # PdfMerger accepts file-like objects
            f.seek(0)
            merger.append(f)
        out = io.BytesIO()
        merger.write(out)
        merger.close()
        out.seek(0)
        return out, None
    except Exception as e:
        return None, [repr(e)]

def delete_pages_from_pdf_bytes(pdf_file, delete_pages_list):
    try:
        pdf_file.seek(0)
        reader = PdfReader(pdf_file)
        writer = PdfWriter()
        total = len(reader.pages)
        del_indices = set()
        for p in delete_pages_list:
            if 0 <= p < total:
                del_indices.add(p)
        for i, page in enumerate(reader.pages):
            if i not in del_indices:
                writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        out.seek(0)
        return out, None
    except Exception as e:
        return None, [repr(e)]

# --- Adobe API helpers (placeholder sample) ---
def get_adobe_access_token():
    """Placeholder: Use your ADOBE_CLIENT_ID/SECRET to obtain token if needed.
       Many Adobe services require JWT/OAuth. Adjust to your flow.
       Here we attempt a naive client_credentials POST to an imaginary token endpoint.
    """
    if not ADOBE_CLIENT_ID or not ADOBE_CLIENT_SECRET:
        return None, "Missing ADOBE_CLIENT_ID or ADOBE_CLIENT_SECRET in Streamlit secrets."
    # NOTE: This endpoint is illustrative. Replace by actual token endpoint if your Adobe app uses OAuth.
    token_url = "https://ims-na1.adobelogin.com/ims/token/v1"  # example Adobe IMS token URL
    data = {
        "grant_type": "client_credentials",
        "client_id": "702badd4a1634f1a914cba03aa36114d",
        "client_secret": "p8e-47C4dyLDI_FbPiR3GlNmwcy_qytGZaUW",
        # "scope": "openid,AdobePDFServices_sdk"  # set scopes needed by your integration
    }
    try:
        resp = requests.post(token_url, data=data, timeout=30)
        if resp.ok:
            j = resp.json()
            access_token = j.get("access_token")
            if access_token:
                return access_token, None
            else:
                return None, f"No access_token in response: {j}"
        else:
            try:
                return None, f"Token request failed ({resp.status_code}): {resp.text}"
            except Exception:
                return None, f"Token request failed ({resp.status_code})"
    except Exception as e:
        return None, repr(e)

def adobe_compress_pdf_bytes(pdf_bytes):
    """Send PDF bytes to Adobe compress endpoint (illustrative).
       You may need to adapt headers, multipart form, or use SDK instead.
    """
    token, err = get_adobe_access_token()
    if err:
        return None, [err]
    # Example Adobe "compress" endpoint (illustrative). Replace with actual Adobe PDF Services endpoint.
    compress_url = "https://pdf-services.adobe.io/operation/compress-pdf"
    files = {"file": ("file.pdf", pdf_bytes, "application/pdf")}
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": ADOBE_CLIENT_ID,
        # "Content-Type": "multipart/form-data"  # requests sets it automatically with files
    }
    try:
        resp = requests.post(compress_url, headers=headers, files=files, timeout=120)
        if resp.ok:
            return io.BytesIO(resp.content), None
        else:
            return None, [f"Adobe compress failed ({resp.status_code}): {resp.text}"]
    except Exception as e:
        return None, [repr(e)]

def adobe_pdf_to_docx_bytes(pdf_bytes):
    """Send PDF to Adobe convert-to-docx endpoint (illustrative)."""
    token, err = get_adobe_access_token()
    if err:
        return None, [err]
    convert_url = "https://pdf-services.adobe.io/operation/pdf-to-docx"
    files = {"file": ("file.pdf", pdf_bytes, "application/pdf")}
    headers = {"Authorization": f"Bearer {token}", "x-api-key": ADOBE_CLIENT_ID}
    try:
        resp = requests.post(convert_url, headers=headers, files=files, timeout=120)
        if resp.ok:
            return io.BytesIO(resp.content), None
        else:
            return None, [f"Adobe pdf->docx failed ({resp.status_code}): {resp.text}"]
    except Exception as e:
        return None, [repr(e)]

# ---------- Streamlit Layout and Tabs ----------

tabs = st.tabs(["Images → PDF", "Merge PDFs", "Compress PDF", "Delete Pages", "PDF → Word"])

# --- Tab 0: Images -> PDF ---
with tabs[0]:
    uploaded_images = st.file_uploader("Upload images)", accept_multiple_files=True,
                                       type=["png","jpg","jpeg","bmp","tiff","webp"])
    if uploaded_images:
        if st.button("Convert to PDF"):
            pdf_bytes, errors = images_to_pdf_bytes(uploaded_images)
            if errors:
                st.error("Có lỗi khi đọc ảnh:")
                for e in errors:
                    st.write("- " + e)
            else:
                st.success("Chuyển ảnh thành PDF thành công.")
                st.download_button("Download PDF", pdf_bytes, file_name="images_to_pdf.pdf", mime="application/pdf")

# --- Tab 1: Merge PDFs ---
with tabs[1]:
    pdf_files = st.file_uploader("Upload PDFs to merge", accept_multiple_files=True, type=["pdf"])
    if pdf_files:
        if st.button("Merge PDFs"):
            merged, errors = merge_pdfs_bytes(pdf_files)
            if errors:
                st.error("Error merging PDFs:")
                for e in errors:
                    st.write("- " + e)
            else:
                st.success("Merged successfully.")
                st.download_button("Download merged PDF", merged, file_name="merged.pdf", mime="application/pdf")

# --- Tab 2: Compress PDF (Adobe) ---
with tabs[2]:
    pdf_for_compress = st.file_uploader("Upload a PDF to compress", type=["pdf"])
    if pdf_for_compress:
        st.info("Compression uses Adobe API — ensure ADOBE_CLIENT_ID and ADOBE_CLIENT_SECRET are set in secrets.")
        if st.button("Compress with Adobe"):
            try:
                pdf_for_compress.seek(0)
                pdf_bytes = pdf_for_compress.read()
                out_io, errors = adobe_compress_pdf_bytes(pdf_bytes)
                if errors:
                    st.error("Compress failed:")
                    for e in errors:
                        st.write("- " + e)
                else:
                    st.success("Compression successful.")
                    st.download_button("Download compressed PDF", out_io, file_name="compressed.pdf", mime="application/pdf")
            except Exception as e:
                st.error("Unexpected error: " + repr(e))

# --- Tab 3: Delete Pages ---
with tabs[3]:
    st.header("Delete pages from PDF")
    pdf_to_edit = st.file_uploader("Upload PDF to edit)", type=["pdf"])
    pages_text = st.text_input("Pages to delete (comma-separated, e.g. 1,3-5)", "")
    def parse_pages(text):
        pages = set()
        if not text.strip():
            return []
        parts = [p.strip() for p in text.split(",") if p.strip()]
        for part in parts:
            if "-" in part:
                try:
                    a,b = part.split("-",1)
                    a = int(a); b = int(b)
                    for i in range(a, b+1):
                        pages.add(i-1)
                except Exception:
                    pass
            else:
                if part.isdigit():
                    pages.add(int(part)-1)
        return sorted(list(pages))
    if pdf_to_edit and st.button("Delete pages"):
        del_pages = parse_pages(pages_text)
        if not del_pages:
            st.error("Không có trang hợp lệ để xóa (hãy nhập ví dụ: 1,3-5).")
        else:
            out, errors = delete_pages_from_pdf_bytes(pdf_to_edit, del_pages)
            if errors:
                st.error("Error editing PDF:")
                for e in errors:
                    st.write("- " + e)
            else:
                st.success("Pages deleted.")
                st.download_button("Download edited PDF", out, file_name="edited.pdf", mime="application/pdf")

# --- Tab 4: PDF -> Word (Adobe) ---
with tabs[4]:
    pdf_to_convert = st.file_uploader("Upload PDF to convert to Word", type=["pdf"])
    if pdf_to_convert:
        if st.button("Convert to Word (Adobe)"):
            try:
                pdf_to_convert.seek(0)
                pdf_bytes = pdf_to_convert.read()
                out_io, errors = adobe_pdf_to_docx_bytes(pdf_bytes)
                if errors:
                    st.error("Conversion failed:")
                    for e in errors:
                        st.write("- " + e)
                else:
                    st.success("Conversion successful.")
                    st.download_button("Download DOCX", out_io, file_name="converted.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            except Exception as e:
                st.error("Unexpected error: " + repr(e))

# ---------- Footer / notes ----------
st.markdown("---")
