import streamlit as st
import boto3
from PIL import Image
import io
import json
import logging
from try2 import extract_summary_fields, extract_line_items
from pdf2image import convert_from_bytes
import re

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
    return text.replace('\n', ' ').replace('\r', '').strip()

# Clean summary data
def clean_summary_data(summary):
    return {key: clean_text(value) if isinstance(value, str) else value for key, value in summary.items()}

# Clean product data
def clean_products_data(products):
    return [
        {key: clean_text(value) if isinstance(value, str) else value for key, value in product.items()}
        for product in products
    ]

# Function to process and find Load Start Time
def process_load_start_time(final_result):
    load_start_keys = [
        "Load Start", "CARD IN", "Bay In", "IN", "start load time", "START TIME:", 
        "LOAD START TIME", "Load Start Time", "START TIME:", "Start Load Time", 
        "Load In Time", "Cargo Start Time", "Vehicle In Time", "Start Time", "Bay In Time", 
        "Load Begin Time", "Start Load Time:", "Load Time", "Loading Start Time", 
        "Loading In Time", "Truck Arrival Time"
    ]
    
    load_start_keys_lower = [key.lower() for key in load_start_keys]
    
    load_start_time = None
    summary_data = final_result.get("summary", {})
    
    for key in load_start_keys_lower:
        for summary_key in summary_data.keys():
            if key in summary_key.lower():
                load_start_time = summary_data[summary_key]
                break
        if load_start_time:
            break
    
    if not load_start_time:
        products_data = final_result.get("products", [])
        for product in products_data:
            for key in load_start_keys_lower:
                if any(key in k.lower() for k in product.keys()):
                    load_start_time = product[key]
                    break
            if load_start_time:
                break

    processed_result = {"Card In time": load_start_time if load_start_time else "Not Found"}

    return processed_result

# Function to process and find Card Out Time
def process_card_out_time(final_result):
    # Extended list of possible keys for Card Out Time (case-insensitive matching)
    card_out_keys = [
        "Load End", "CARD OUT", "Bay Out", "OUT", "end load time", "END TIME:", 
        "LOAD END TIME", "Load Out Time", "END TIME:", "End Load Time", 
        "Load Out Time", "Cargo End Time", "Vehicle Out Time", "End Time", "Bay Out Time", 
        "Load Finish Time", "End Load Time", "Loading End Time", 
        "Loading Out Time", "Truck Departure Time", "Bay Out", "OUT", 
        "END LOAD TIME", "END TIME:", "Load Stop:", "Load Stop Time", "TIME LOAD COMPLETE:"
    ]
    
    # Convert all card out keys to lowercase for case-insensitive comparison
    card_out_keys_lower = [key.lower() for key in card_out_keys]
    
    card_out_time = None
    summary_data = final_result.get("summary", {})
    
    # Look for matching keys in the summary data
    for key in card_out_keys_lower:
        for summary_key in summary_data.keys():
            if key in summary_key.lower():
                card_out_time = summary_data[summary_key]
                break
        if card_out_time:
            break
    
    # If no Card Out Time found in summary, check products
    if not card_out_time:
        products_data = final_result.get("products", [])
        for product in products_data:
            for key in card_out_keys_lower:
                if any(key in k.lower() for k in product.keys()):
                    card_out_time = product[key]
                    break
            if card_out_time:
                break

    processed_result = {"Card Out time": card_out_time if card_out_time else "Not Found"}

    return processed_result

# Function to process and find BOL number
def process_bol_data(final_result):
    bol_keys = [
        "shippers bol no", "DOCUMENT ", "manifest", "BILL OF LADING #", "incoming bol no", 
        "BOL NUMBER", "BOL #", "Document/BOL#", "BOL NO", "BOL REF", "BILL OF LADING NO", 
        "BILL OF LADING NO:", "BOL REF #", "BOL#", "BILL OF LADING #:", "BOL NUMBER #", 
        "BOL REFERENCE", "DOCUMENT #", "BOL NO:", "SHIPPERS BOL NO", "BILL OF LADING NUMBER", 
        "BOL #: (BILL OF LADING)", "BOL NUMBER:", "BOL ID", "BILL OF LADING IDENTIFIER", 
        "BOL-#", "BILL OF LADING REF NO", "BOL REF NO", "BOL_ID", "BILL OF LADING #:", 
        "BOL NUMBER ID", "BOL NUMBER ID:", "SHIPMENT BOL #", "BOL REFERENCE NUMBER", 
        "TRANSPORTATION BOL #", "TRUCK BOL NUMBER", "CARGO BOL #", "CONTAINER BOL #", 
        "LOADING BOL #", "ORDER BOL #", "WAYBILL #", "SHIPMENT ID", "DELIVERY BOL #", 
        "CARGO BOL ID", "INVOICE BOL #", "OF LADING #",
    ]
    
    bol_keys_lower = [key.lower() for key in bol_keys]
    
    bol_number = None
    summary_data = final_result.get("summary", {})
    
    for key in bol_keys_lower:
        for summary_key in summary_data.keys():
            if key in summary_key.lower():
                bol_number = summary_data[summary_key]
                break
        if bol_number:
            break
    
    if not bol_number:
        products_data = final_result.get("products", [])
        for product in products_data:
            for key in bol_keys_lower:
                if any(key in k.lower() for k in product.keys()):
                    bol_number = product[key]
                    break
            if bol_number:
                break
    
    if not bol_number:
        for fragment in ['of lading #', 'lading #']:
            for summary_key, value in summary_data.items():
                if isinstance(value, str) and fragment in value.lower():
                    bol_number = re.findall(r'\d+', value)
                    if bol_number:
                        bol_number = bol_number[0]
                    break
            if bol_number:
                break
    
    if bol_number:
        bol_number = re.sub(r'\D', '', bol_number)
    
    processed_result = {"BOL #": bol_number if bol_number else "Not Found"}

    return processed_result

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

        if isinstance(key_or_file, str):
            obj = s3.get_object(Bucket=bucket, Key=key_or_file)
            file_data = obj['Body'].read()
            image = Image.open(io.BytesIO(file_data)) if key_or_file.lower().endswith(('.jpg', '.jpeg', '.png')) else None
        else:
            file_data = key_or_file.read()
            image = Image.open(io.BytesIO(file_data)) if key_or_file.type in ['image/jpeg', 'image/png'] else None

        all_lines, line_items = [], []

        if image:
            response_expense = textract.analyze_expense(Document={'Bytes': file_data})
            summary_data = extract_summary_fields(response_expense, logger)
            line_items = extract_line_items(response_expense, logger)

            response_doc = textract.analyze_document(Document={'Bytes': file_data}, FeatureTypes=['TABLES', 'FORMS'])
            all_lines = [block['Text'] for block in response_doc['Blocks'] if block['BlockType'] == 'LINE']

        else:
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

        processed_bol_result = process_bol_data(final_result)
        processed_load_start_result = process_load_start_time(final_result)
        processed_card_out_result = process_card_out_time(final_result)

        processed_result = {**processed_bol_result, **processed_load_start_result, **processed_card_out_result}

        return image, final_result, processed_result
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        st.error(f"Error: {e}")
        return None, {}, {}

# Displaying results
def display_results(img, final_result, processed_result):
    if img:
        st.image(img, caption="Uploaded Document", use_container_width=True)
    
    st.subheader("Structured JSON with Summary and Line Items (Products)")
    st.code(json.dumps(final_result, indent=4), language="json")
    
    st.subheader("Post Processed Result")
    st.code(json.dumps(processed_result, indent=4), language="json")

# Main OCR content and processing flow
def display_ocr_content():
    input_method = st.sidebar.radio("Choose Input Method", ("Upload a file", "Choose from existing list"), index=1)

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
            img, final_result, processed_result = process_image_and_extract_data(s3_bucket, uploaded_file)
            display_results(img, final_result, processed_result)

    elif selected_filename:
        with st.spinner("Processing, please wait..."):
            img, final_result, processed_result = process_image_and_extract_data(s3_bucket, selected_filename)
            display_results(img, final_result, processed_result)

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
