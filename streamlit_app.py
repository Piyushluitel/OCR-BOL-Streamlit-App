import streamlit as st
import boto3
from PIL import Image
import io
import json
import logging
from datetime import datetime
from try2 import extract_summary_fields, extract_line_items
import time

# Authentication credentials
USERNAME = st.secrets["USERNAME"]
PASSWORD = st.secrets["PASSWORD"] # The strong password

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

# Function to display login form centered on the page
def show_login_form():
    st.markdown("""
        <style>
            /* Centering the login popup */
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
                width: 200px;  /* Smaller box width */
            }
            .login-popup h3 {
                text-align: center;
                color: #2c3e50;
                margin-bottom: 10px;
            }
            .login-popup input {
                width: 100%;
                padding: 8px;
                margin: 8px 0;
                border: 1px solid #ccc;
                border-radius: 5px;
                font-size: 14px;
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

    # Add title to the authentication page
    st.markdown("<h2 style='text-align: center;'>OCR on BOL</h2>", unsafe_allow_html=True)

    # Authentication form inputs
    username_input = st.text_input("Username", key="username_input")
    password_input = st.text_input("Password", type="password", key="password_input")
    
    # Authenticate button
    login_button = st.button("Authenticate", key="login_button")
    
    return username_input, password_input, login_button

# Function to display the main OCR content after successful login
def display_ocr_content():
    st.title("Document OCR Processing with Amazon Textract")
    st.markdown("""
        This app allows you to process documents (images) using Amazon Textract. You can either select an image from the S3 bucket 
        or upload your own image for text extraction. Once processed, the extracted data will be displayed.
    """)

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

        default_image = '00052AAF-AE51-4918-A307-4C35480299F0.jpg'
        selected_image = st.selectbox(
            'Select Image Filename from S3:', 
            image_filenames, 
            index=image_filenames.index(default_image) if default_image in image_filenames else 0
        )
        uploaded_file = st.file_uploader("Or Upload a Document (Image Only)", type=["jpg", "jpeg", "png"])

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
            if st.button('See Extracted Results'):
                with st.spinner("Extracting and parsing... please wait..."):
                    time.sleep(3)  # Simulate a delay for processing (3-4 seconds)
                    img, lines, _, _, extracted = process_image_and_extract_data(s3_bucket, selected_image)

                    if img:
                        display_results(img, lines, extracted)

        else:
            st.write("Please select or upload an image to process.")

# Main logic
if __name__ == "__main__":
    # Check if user is authenticated
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    # If not authenticated, show the login form
    if not st.session_state.authenticated:
        username_input, password_input, login_button = show_login_form()

        # Simulate login process with a loading spinner
        if login_button:
            with st.spinner("Authenticating... please wait..."):
                time.sleep(3)  # Simulate login delay
                if username_input == USERNAME and password_input == PASSWORD:
                    st.session_state.authenticated = True
                    st.success("Login successful!")
                    if st.button('Start OCR'):
                        display_ocr_content()  # Show main content after "Start OCR"
                    else:
                        st.write("Click 'Start OCR' to begin processing your documents.")
                else:
                    st.error("Invalid credentials! Please try again.")
    # else:
    #     # After successful login, display the "Start OCR" button
    #     if st.button('Start OCR'):
    #         display_ocr_content()  # Show main content after "Start OCR"
    #     else:
    #         st.write("Click 'Start OCR' to begin processing your documents.")
