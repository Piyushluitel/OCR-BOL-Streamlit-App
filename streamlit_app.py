import streamlit as st
import boto3
from PIL import Image
import io
import json
import logging
from datetime import datetime
from try2 import extract_summary_fields, extract_line_items
import pdf2image  # Required for PDF to Image conversion

# Initialize AWS
aws_access_key_id = st.secrets["AWS_ACCESS_KEY_ID"]
aws_secret_access_key = st.secrets["AWS_SECRET_ACCESS_KEY"]
session = boto3.Session(
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key
)
textract = session.client('textract', region_name='us-east-1')

# Configure logger
logger = logging.getLogger("TextractLogger")
logger.setLevel(logging.INFO)

if not logger.handlers:
    log_file = "textract_processing.log"
    file_handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

# Streamlit UI
st.title("Document OCR Processing using Amazon Textract")
s3_bucket = st.text_input('Enter S3 Bucket Name:', 'fp-prod-s3')

def load_s3_filenames(file_path="s3_filenames.txt"):
    try:
        with open(file_path, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        st.error(f"File {file_path} not found.")
        return []

image_filenames = load_s3_filenames()
selected_image = st.selectbox('Select Image Filename from S3:', image_filenames) if image_filenames else ""

# Function to handle PDF upload and conversion to image
def convert_pdf_to_image(pdf_file):
    try:
        images = pdf2image.convert_from_path(pdf_file)
        # Convert the first page to an image (can be adjusted if needed)
        return images[0]  
    except Exception as e:
        st.error(f"Error in PDF conversion: {e}")
        return None

# Function to process image and extract data using Textract
def process_image_and_extract_data(bucket, key_or_image):
    try:
        logger.info("\n\n" + "#" * 80)
        logger.info(f"Processing file: {key_or_image}")
        
        s3 = boto3.client('s3')
        if isinstance(key_or_image, str):  # If it's an S3 key
            obj = s3.get_object(Bucket=bucket, Key=key_or_image)
            image_data = obj['Body'].read()
            image = Image.open(io.BytesIO(image_data))
        else:  # If it's an uploaded file
            image = key_or_image
        
        # AnalyzeExpense
        response_expense = textract.analyze_expense(Document={'S3Object': {'Bucket': bucket, 'Name': key_or_image}} if isinstance(key_or_image, str) else {'Bytes': image.tobytes()})
        summary_data = extract_summary_fields(response_expense, logger)
        products_data = extract_line_items(response_expense, logger)

        # AnalyzeDocument for Tables and Forms
        response_doc = textract.analyze_document(
            Document={'S3Object': {'Bucket': bucket, 'Name': key_or_image}} if isinstance(key_or_image, str) else {'Bytes': image.tobytes()},
            FeatureTypes=['TABLES', 'FORMS']
        )

        # Extract lines, tables, forms
        lines = [block['Text'] for block in response_doc['Blocks'] if block['BlockType'] == 'LINE']
        tables = [block for block in response_doc['Blocks'] if block['BlockType'] == 'TABLE']
        key_value_pairs = [block for block in response_doc['Blocks'] if block['BlockType'] == 'KEY_VALUE_SET']

        logger.info("\nExtracted Text Lines:")
        for line in lines:
            logger.info(line)

        output = summary_data
        output["products"] = products_data

        json_output = json.dumps(output, indent=4)
        logger.info("\nExtracted JSON:")
        logger.info(json_output)

        return image, lines, key_value_pairs, tables, output
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        st.error(f"Error: {e}")
        return None, [], [], [], {}

# File upload and S3 selection handling
uploaded_file = st.file_uploader("Upload a document (PDF or Image)", type=["pdf", "jpg", "jpeg", "png"])
if uploaded_file:
    if uploaded_file.type == "application/pdf":
        st.write("Processing PDF...")
        image_from_pdf = convert_pdf_to_image(uploaded_file)
        if image_from_pdf:
            st.image(image_from_pdf, caption="Converted PDF Page", use_container_width=True)
            st.write("PDF conversion successful. Now extracting text...")

            # Process the PDF as an image in the same way
            img, lines, _, _, extracted = process_image_and_extract_data(s3_bucket, uploaded_file.name)
    else:
        st.write("Processing Image...")
        img, lines, _, _, extracted = process_image_and_extract_data(s3_bucket, uploaded_file.name)

    if img:
        st.image(img, caption="Uploaded Document", use_container_width=True)

        # Popover-style comparison
        with st.popover("🔍 Compare Extracted Data"):
            col1, col2 = st.columns([1.2, 1.8])

            with col1:
                st.subheader("Extracting Text Line by Line")
                st.markdown(
                    "<div style='height: 300px; overflow-y: auto; border: 1px solid #ccc; padding: 10px;'>"
                    + "<br>".join(lines)
                    + "</div>",
                    unsafe_allow_html=True
                )

            with col2:
                st.subheader("Structured JSON using AnalyzeExpense")
                st.code(json.dumps(extracted, indent=4), language="json")

# Process S3 document when button is clicked
if st.button('Process Document') and selected_image:
    img, lines, _, _, extracted = process_image_and_extract_data(s3_bucket, selected_image)

    if img:
        st.image(img, caption="Uploaded Document", use_container_width=True)

        # Popover-style comparison
        with st.popover("🔍 Compare Extracted Data"):
            col1, col2 = st.columns([1.2, 1.8])

            with col1:
                st.subheader("Extracting Text Line by Line")
                st.markdown(
                    "<div style='height: 300px; overflow-y: auto; border: 1px solid #ccc; padding: 10px;'>"
                    + "<br>".join(lines)
                    + "</div>",
                    unsafe_allow_html=True
                )

            with col2:
                st.subheader("Structured JSON using AnalyzeExpense")
                st.code(json.dumps(extracted, indent=4), language="json")
