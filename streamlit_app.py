import streamlit as st
import boto3
from PIL import Image
import io
import json
import logging
from try2 import extract_summary_fields, extract_line_items
from pdf2image import convert_from_bytes

# Initialize logging
logger = logging.getLogger("TextractLogger")
logger.setLevel(logging.INFO)

if not logger.handlers:
    log_file = "textract_processing.log"
    file_handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

# Authentication credentials from Streamlit secrets
USERNAME = st.secrets["USERNAME"]
PASSWORD = st.secrets["PASSWORD"]

AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]

# Initialize AWS Textract client
def initialize_textract_client():
    session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    return session.client('textract', region_name='us-east-1')

textract = initialize_textract_client()

# Streamlit UI configuration
st.set_page_config(page_title="Document OCR with Textract", page_icon=":page_facing_up:", layout="wide")

# Login Form
def show_login_form():
    st.markdown("""
        <style>
            .login-popup {
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background-color: white;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0px 5px 15px rgba(0, 0, 0, 0.2);
                z-index: 100;
                width: 250px;
            }
            .login-popup h3 {
                text-align: center;
                color: #2c3e50;
                margin-bottom: 10px;
            }
            .css-1d391kg {
                width: 200px;
                margin: 0 auto;
                padding: 8px;
            }
            .login-popup .login-btn {
                width: 100%;
                padding: 10px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
            }
            .login-popup .login-btn:hover {
                background-color: #45a049;
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='text-align: center;'>Data Extraction from Bill of Lading Image with Amazon Textract OCR</h2>", unsafe_allow_html=True)

    username_input = st.text_input("Username", key="username_input")
    password_input = st.text_input("Password", type="password", key="password_input")
    login_button = st.button("Authenticate", key="login_button")

    return username_input, password_input, login_button

# Function to read filenames from an S3 source
def read_s3_filenames(file_path="s3_filenames.txt"):
    try:
        with open(file_path, 'r') as file:
            return [line.strip() for line in file.readlines() if line.strip()]
    except FileNotFoundError:
        st.error(f"Error: {file_path} not found.")
        return []

# Cleaning text to remove newline characters
def clean_text(text):
    return text.replace('\n', ' ')

# Clean summary data
def clean_summary_data(summary):
    return {key: clean_text(value) if isinstance(value, str) else value for key, value in summary.items()}

# Clean product data
def clean_products_data(products):
    return [
        {key: clean_text(value) if isinstance(value, str) else value for key, value in product.items()}
        for product in products
    ]

# File upload logic
def handle_file_upload(input_method):
    if input_method == "Upload a file":
        return st.file_uploader("Upload a Document (Image or PDF)", type=["jpg", "jpeg", "png"])
    return None

# File selection from list
def handle_file_selection(input_method):
    if input_method == "Choose from existing list":
        filenames = read_s3_filenames()
        default_file = '00052AAF-AE51-4918-A307-4C35480299F0.jpg'
        selected_filename = st.selectbox('Select Image from list:', filenames, index=filenames.index(default_file) if default_file in filenames else 0)
        return selected_filename
    return None

# Image processing and Textract text extraction
def process_image_and_extract_data(bucket, key_or_file):
    try:
        logger.info(f"\n\nProcessing file: {key_or_file}")
        
        s3 = boto3.client('s3')
        file_data, image = None, None

        if isinstance(key_or_file, str):  # If it's an S3 key
            obj = s3.get_object(Bucket=bucket, Key=key_or_file)
            file_data = obj['Body'].read()
            image = Image.open(io.BytesIO(file_data)) if key_or_file.lower().endswith(('.jpg', '.jpeg', '.png')) else None
        else:  # If it's an uploaded file
            file_data = key_or_file.read()
            image = Image.open(io.BytesIO(file_data)) if key_or_file.type in ['image/jpeg', 'image/png'] else None

        all_lines, line_items = [], []

        if image:  # Image processing
            response_expense = textract.analyze_expense(Document={'Bytes': file_data})
            summary_data = extract_summary_fields(response_expense, logger)
            line_items = extract_line_items(response_expense, logger)

            response_doc = textract.analyze_document(Document={'Bytes': file_data}, FeatureTypes=['TABLES', 'FORMS'])
            all_lines = [block['Text'] for block in response_doc['Blocks'] if block['BlockType'] == 'LINE']

        else:  # PDF processing
            images = convert_from_bytes(file_data)
            for img in images:
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)

                response_doc = textract.analyze_document(Document={'Bytes': img_bytes.read()}, FeatureTypes=['TABLES', 'FORMS'])
                all_lines.extend([block['Text'] for block in response_doc['Blocks'] if block['BlockType'] == 'LINE'])

            summary_data = {'lines': all_lines}
            line_items = []

        final_result = {'summary': summary_data, 'products': line_items}
        final_result['summary'] = clean_summary_data(final_result['summary'])
        final_result['products'] = clean_products_data(final_result['products'])

        json_output = json.dumps(final_result, indent=4)
        logger.info(f"Extracted JSON: {json_output}")

        return image, final_result
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        st.error(f"Error: {e}")
        return None, {}

# Displaying results
def display_results(img, final_result):
    if img:
        st.image(img, caption="Uploaded Document", use_container_width=True)
    
    st.subheader("Structured JSON with Summary and Line Items (Products)")
    st.code(json.dumps(final_result, indent=4), language="json")

# Main OCR content and processing flow
def display_ocr_content():
    input_method = st.sidebar.radio("Choose Input Method", ("Upload a file", "Choose from existing list"), index=1)

    # Sidebar content
    with st.sidebar:
        st.title("OCR Document Processing")
        st.markdown("""
            This app allows you to process documents (images or PDFs) using Amazon Textract. You can either select an image from the list 
            of filenames or upload your own image or PDF for text extraction. Once processed, the extracted data will be displayed.
        """)

        uploaded_file = handle_file_upload(input_method)
        selected_filename = handle_file_selection(input_method)

    s3_bucket = 'fp-prod-s3'

    if uploaded_file:
        with st.spinner("Processing the document, please wait..."):
            img, final_result = process_image_and_extract_data(s3_bucket, uploaded_file)
            display_results(img, final_result)

    elif selected_filename:
        with st.spinner("Processing, please wait..."):
            img, final_result = process_image_and_extract_data(s3_bucket, selected_filename)
            display_results(img, final_result)

    else:
        st.write("Please select or upload an image or PDF to process.")

# Main logic
if __name__ == "__main__":
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        username_input, password_input, login_button = show_login_form()

        if login_button:
            if username_input == USERNAME and password_input == PASSWORD:
                st.session_state.authenticated = True
            else:
                st.error("Invalid credentials! Please try again.")
    else:
        display_ocr_content()
