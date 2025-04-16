import streamlit as st
import os
import logging
import tempfile
import io

from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
from adobe.pdfservices.operation.exception.exceptions import ServiceApiException, ServiceUsageException, SdkException
from adobe.pdfservices.operation.io.cloud_asset import CloudAsset
from adobe.pdfservices.operation.io.stream_asset import StreamAsset
from adobe.pdfservices.operation.pdf_services import PDFServices
from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType
from adobe.pdfservices.operation.pdfjobs.jobs.export_pdf_job import ExportPDFJob
from adobe.pdfservices.operation.pdfjobs.params.export_pdf.export_pdf_params import ExportPDFParams
from adobe.pdfservices.operation.pdfjobs.params.export_pdf.export_pdf_target_format import ExportPDFTargetFormat
from adobe.pdfservices.operation.pdfjobs.result.export_pdf_result import ExportPDFResult

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thông tin API Adobe
CLIENT_ID = "01cf11f8e93e4d2c96f6f970c539cdee"
CLIENT_SECRET = "p8e-5tr_FTuckBRf82Ss2CTVc9pf-oWoX1hk"  # Thêm client secret của bạn vào đây

def convert_pdf_to_docx(pdf_bytes):
    try:
        # Thiết lập thông tin xác thực
        credentials = ServicePrincipalCredentials(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET
        )
        
        # Tạo instance PDF Services
        pdf_services = PDFServices(credentials=credentials)
        
        # Tạo asset từ file nguồn và tải lên
        input_asset = pdf_services.upload(input_stream=pdf_bytes, mime_type=PDFServicesMediaType.PDF)
        
        # Tạo tham số cho công việc
        export_pdf_params = ExportPDFParams(target_format=ExportPDFTargetFormat.DOCX)
        
        # Tạo instance công việc mới
        export_pdf_job = ExportPDFJob(input_asset=input_asset, export_pdf_params=export_pdf_params)
        
        # Gửi công việc và nhận kết quả
        location = pdf_services.submit(export_pdf_job)
        pdf_services_response = pdf_services.get_job_result(location, ExportPDFResult)
        
        # Lấy nội dung từ asset kết quả
        result_asset = pdf_services_response.get_result().get_asset()
        stream_asset = pdf_services.get_content(result_asset)
        
        # Trả về dữ liệu bytes của file DOCX
        return stream_asset.get_input_stream()
        
    except (ServiceApiException, ServiceUsageException, SdkException) as e:
        logger.error(f"Lỗi khi chuyển đổi PDF: {str(e)}")
        return None

# Thiết lập giao diện Streamlit
st.set_page_config(page_title="PDF sang Word Converter", page_icon="📄")

st.title("Chuyển đổi PDF sang Word")
st.write("Ứng dụng này sử dụng Adobe PDF Services API để chuyển đổi tệp PDF sang định dạng Word (.docx)")

uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"])

if uploaded_file is not None:
    st.write("File đã tải lên:", uploaded_file.name)
    
    if st.button("Chuyển đổi"):
        with st.spinner("Đang chuyển đổi..."):
            # Đọc nội dung file PDF đã tải lên
            pdf_bytes = uploaded_file.getvalue()
            
            # Tạo tên file output
            output_filename = uploaded_file.name.replace(".pdf", ".docx")
            
            # Chuyển đổi PDF sang DOCX
            docx_bytes = convert_pdf_to_docx(pdf_bytes)
            
            if docx_bytes:
                st.success("Chuyển đổi thành công!")
                
                # Tạo nút tải xuống file Word
                st.download_button(
                    label="Tải xuống file Word",
                    data=docx_bytes,
                    file_name=output_filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                st.error("Có lỗi xảy ra trong quá trình chuyển đổi. Vui lòng thử lại.")

st.markdown("---")
st.write("Được xây dựng với Streamlit và Adobe PDF Services API")
