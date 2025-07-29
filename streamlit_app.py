import streamlit as st
import boto3
from PIL import Image
import io
import json
import logging
from datetime import datetime
from try2 import extract_summary_fields, extract_line_items

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

# Streamlit UI with enhanced layout
st.set_page_config(page_title="Document OCR with Textract", page_icon=":page_facing_up:", layout="wide")

# Sidebar for input fields
with st.sidebar:
    st.title("OCR Document Processing")
    s3_bucket = st.text_input('Enter S3 Bucket Name:', 'fp-prod-s3')

    # Directly list image files from the selected S3 bucket
    s3 = boto3.client('s3')
    try:
        s3_objects = s3.list_objects_v2(Bucket=s3_bucket)
        if 'Contents' in s3_objects:
            image_filenames = [obj['Key'] for obj in s3_objects['Contents'] if obj['Key'].lower().endswith(('.jpg', '.jpeg', '.png'))]
        else:
            image_filenames = []
    except Exception as e:
        st.error(f"Error accessing S3 bucket: {e}")
        image_filenames = []

    selected_image = st.selectbox('Select Image Filename from S3:', image_filenames) if image_filenames else ""
    uploaded_file = st.file_uploader("Or Upload an Image", type=["jpg", "jpeg", "png"])

# Main content area
st.title(" OCR Processing ON Bill of Lading images with Amazon Textract")
st.markdown("""
    This app allows you to process documents (images) using Amazon Textract. You can either select an image from the S3 bucket 
    or upload your own image for text extraction. Once processed, the extracted data will be displayed.
""")

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

# Displaying results and UI enhancements
def display_results(img, lines, extracted):
    st.image(img, caption="Uploaded Document", use_container_width=True)

    # Popover-style comparison with wider box
    with st.expander("🔍 Compare Extracted Data"):
        col1, col2 = st.columns([1.5, 2.5])  # Wider column for extracted data

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

# Processing section
if uploaded_file:
    st.write("Processing uploaded image...")

    with st.spinner("Processing the document, please wait..."):
        img, lines, _, _, extracted = process_image_and_extract_data(s3_bucket, uploaded_file)

        if img:
            display_results(img, lines, extracted)
else:
    if selected_image:
        if st.button('Process Document'):
            with st.spinner("Processing the selected document, please wait..."):
                img, lines, _, _, extracted = process_image_and_extract_data(s3_bucket, selected_image)

                if img:
                    display_results(img, lines, extracted)

    else:
        st.write("Please select or upload an image to process.")

# Custom CSS for better appearance
st.markdown("""
    <style>
        .sidebar .sidebar-content {
            background-color: #f0f2f6;
            padding: 20px;
        }
        .stButton > button {
            background-color: #4CAF50;
            color: white;
            border-radius: 10px;
            height: 50px;
            width: 200px;
        }
        .stButton > button:hover {
            background-color: #45a049;
        }
        h1, h2 {
            color: #2c3e50;
        }
        .stExpander > div {
            background-color: #ecf0f1;
        }
    </style>
""", unsafe_allow_html=True)
