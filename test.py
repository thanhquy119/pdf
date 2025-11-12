import streamlit as st
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from PIL import Image
import io
import requests
import zipfile

# Lấy Adobe credentials từ secrets
ADOBE_CLIENT_ID = st.secrets["ADOBE_CLIENT_ID"]
ADOBE_CLIENT_SECRET = st.secrets["ADOBE_CLIENT_SECRET"]

st.set_page_config(page_title="PDF Toolkit", layout="wide")
st.title("📄 PDF Toolkit using Adobe API")

# Tabs
tabs = st.tabs(["🖼️ Images to PDF", "📚 Merge PDFs", "📦 Compress PDF", "🧹 Delete Pages", "🔄 PDF to Word"])

# --- IMAGES TO PDF ---
with tabs[0]:
    uploaded_images = st.file_uploader("Upload images", accept_multiple_files=True, type=["png", "jpg", "jpeg"])
    if uploaded_images:
        if st.button("Convert to PDF"):
            images = [Image.open(img).convert("RGB") for img in uploaded_images]
            pdf_bytes = io.BytesIO()
            images[0].save(pdf_bytes, save_all=True, append_images=images[1:])
            pdf_bytes.seek(0)
            st.download_button("Download PDF", pdf_bytes, "images_to_pdf.pdf")

# --- MERGE PDF ---
with tabs[1]:
    pdf_files = st.file_uploader("Upload PDFs", accept_multiple_files=True, type="pdf")
    if pdf_files:
        if st.button("Merge PDFs"):
            merger = PdfMerger()
            for pdf in pdf_files:
                merger.append(pdf)
            merged = io.BytesIO()
            merger.write(merged)
            merger.close()
            merged.seek(0)
            st.download_button("Download merged PDF", merged, "merged.pdf")

# --- COMPRESS PDF (using Adobe API) ---
with tabs[2]:
    pdf = st.file_uploader("Upload PDF to compress", type="pdf")
    if pdf and st.button("Compress"):
        url = "https://pdf-services.adobe.io/operation/compress-pdf"
        headers = {
            "x-api-key": ADOBE_CLIENT_ID,
            "Authorization": f"Bearer {ADOBE_CLIENT_SECRET}"
        }
        files = {'file': pdf.getvalue()}
        response = requests.post(url, headers=headers, files=files)
        if response.ok:
            st.download_button("Download compressed PDF", response.content, "compressed.pdf")
        else:
            st.error("Compression failed. Check Adobe API credentials.")

# --- DELETE PAGES ---
with tabs[3]:
    pdf = st.file_uploader("Upload PDF to delete pages from", type="pdf")
    pages = st.text_input("Enter pages to delete (comma-separated, e.g. 1,3,5)")
    if pdf and pages and st.button("Delete pages"):
        reader = PdfReader(pdf)
        writer = PdfWriter()
        del_pages = [int(p) - 1 for p in pages.split(",") if p.strip().isdigit()]
        for i, page in enumerate(reader.pages):
            if i not in del_pages:
                writer.add_page(page)
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        st.download_button("Download updated PDF", output, "deleted_pages.pdf")

# --- PDF TO WORD (Adobe API) ---
with tabs[4]:
    pdf = st.file_uploader("Upload PDF to convert to Word", type="pdf")
    if pdf and st.button("Convert to Word"):
        url = "https://pdf-services.adobe.io/operation/pdf-to-docx"
        headers = {
            "x-api-key": ADOBE_CLIENT_ID,
            "Authorization": f"Bearer {ADOBE_CLIENT_SECRET}"
        }
        files = {'file': pdf.getvalue()}
        response = requests.post(url, headers=headers, files=files)
        if response.ok:
            st.download_button("Download Word File", response.content, "converted.docx")
        else:
            st.error("Conversion failed. Check Adobe API credentials.")
