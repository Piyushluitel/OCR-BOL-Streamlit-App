# import streamlit as st
# import boto3
# from PIL import Image
# import io
# import json
# import logging
# from datetime import datetime
# from try2 import extract_summary_fields, extract_line_items

# # Set up Textract client
# textract = boto3.client('textract', region_name='us-east-1')

# # Configure logger
# logger = logging.getLogger("TextractLogger")
# logger.setLevel(logging.INFO)

# if not logger.handlers:
#     log_file = "textract_processing.log"
#     file_handler = logging.FileHandler(log_file)
#     formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#     file_handler.setFormatter(formatter)
#     logger.addHandler(file_handler)

# # Streamlit UI
# st.title("Document OCR Processing using Amazon Textract")
# s3_bucket = st.text_input('Enter S3 Bucket Name:', 'fp-prod-s3')

# def load_s3_filenames(file_path="s3_filenames.txt"):
#     try:
#         with open(file_path, "r") as f:
#             return [line.strip() for line in f if line.strip()]
#     except FileNotFoundError:
#         st.error(f"File {file_path} not found.")
#         return []

# image_filenames = load_s3_filenames()
# selected_image = st.selectbox('Select Image Filename from S3:', image_filenames) if image_filenames else ""

# def process_image_and_extract_data(bucket, key):
#     try:
#         logger.info("\n\n" + "#" * 80)
#         logger.info(f"Processing file: {key}")
        
#         s3 = boto3.client('s3')
#         obj = s3.get_object(Bucket=bucket, Key=key)
#         image_data = obj['Body'].read()
#         image = Image.open(io.BytesIO(image_data))

#         # AnalyzeExpense
#         response_expense = textract.analyze_expense(Document={'S3Object': {'Bucket': bucket, 'Name': key}})
#         summary_data = extract_summary_fields(response_expense, logger)
#         products_data = extract_line_items(response_expense, logger)

#         # AnalyzeDocument for Tables and Forms
#         response_doc = textract.analyze_document(
#             Document={'S3Object': {'Bucket': bucket, 'Name': key}},
#             FeatureTypes=['TABLES', 'FORMS']
#         )

#         # Extract lines, tables, forms
#         lines = [block['Text'] for block in response_doc['Blocks'] if block['BlockType'] == 'LINE']
#         tables = [block for block in response_doc['Blocks'] if block['BlockType'] == 'TABLE']
#         key_value_pairs = [block for block in response_doc['Blocks'] if block['BlockType'] == 'KEY_VALUE_SET']

#         logger.info("\nExtracted Text Lines:")
#         for line in lines:
#             logger.info(line)

#         output = summary_data
#         output["products"] = products_data

#         json_output = json.dumps(output, indent=4)
#         logger.info("\nExtracted JSON:")
#         logger.info(json_output)

#         return image, lines, key_value_pairs, tables, output
#     except Exception as e:
#         logger.error(f"Processing failed: {e}")
#         st.error(f"Error: {e}")
#         return None, [], [], [], {}

# # UI Section
# if selected_image:
#     if st.button("Process Document"):
#         image, lines, key_value_pairs, tables, output = process_image_and_extract_data(s3_bucket, selected_image)

#         if image:
#             st.image(image, caption="Uploaded Document", use_column_width=True)

#             st.header("Using Analyze Document")

#             st.subheader("Lines")
#             for line in lines:
#                 st.write(f"- {line}")

#             st.subheader("Forms (Key-Value Pairs)")
#             if key_value_pairs:
#                 for kv in key_value_pairs:
#                     st.json(kv)
#             else:
#                 st.write("No key-value pairs detected.")

#             st.subheader("Tables")
#             if tables:
#                 for i, table in enumerate(tables):
#                     st.write(f"Table {i+1}:")
#                     st.json(table)
#             else:
#                 st.write("No tables detected.")

#             st.header("Using Analyze Expense")
#             st.subheader("Extracted Summary and Products")
#             st.json(output)






# # streamlit_app.py

import streamlit as st
import boto3
from PIL import Image
import io
import json
import logging
from datetime import datetime
from try2 import extract_summary_fields, extract_line_items

# Set up Textract client
textract = boto3.client('textract', region_name='us-east-1')

# Configure logger once
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

def process_image_and_extract_data(bucket, key):
    try:
        logger.info("\n\n" + "#" * 80)
        logger.info(f"Processing file: {key}")
        
        s3 = boto3.client('s3')
        obj = s3.get_object(Bucket=bucket, Key=key)
        image_data = obj['Body'].read()
        image = Image.open(io.BytesIO(image_data))

        # AnalyzeExpense
        response_expense = textract.analyze_expense(Document={'S3Object': {'Bucket': bucket, 'Name': key}})
        summary_data = extract_summary_fields(response_expense, logger)
        products_data = extract_line_items(response_expense, logger)

        # AnalyzeDocument for Tables and Forms
        response_doc = textract.analyze_document(
            Document={'S3Object': {'Bucket': bucket, 'Name': key}},
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


# if st.button('Process Document') and selected_image:
#     img, lines, extracted = process_image_and_extract_data(s3_bucket, selected_image)

#     if img:
#         st.image(img, caption="Uploaded Document", use_container_width=True)

#         # Expander-style comparison
#         with st.expander("📋 Compare Extracted Results", expanded=False):
#             col1, col2 = st.columns([1, 2])

#             with col1:
#                 st.markdown("**Text Lines**")
#                 st.markdown(
#                     "<div style='height: 300px; overflow-y: auto; border: 1px solid #ccc; padding: 10px;'>"
#                     + "<br>".join(lines)
#                     + "</div>",
#                     unsafe_allow_html=True
#                 )

#             with col2:
#                 st.markdown("**Extracted JSON**")
#                 st.code(json.dumps(extracted, indent=4), language="json")
#     else:
#         st.error("Failed to extract data or display the image.")

 

if st.button('Process Document') and selected_image:
    img, lines, extracted = process_image_and_extract_data(s3_bucket, selected_image)

    if img:
        st.image(img, caption="Uploaded Document", use_container_width=True)

        # Popover-style comparison
        with st.popover("🔍 Compare Extracted Data"):
            col1, col2 = st.columns([1.2, 1.8])

            with col1:
                st.subheader("Text Lines")
                st.markdown(
                    "<div style='height: 300px; overflow-y: auto; border: 1px solid #ccc; padding: 10px;'>"
                    + "<br>".join(lines)
                    + "</div>",
                    unsafe_allow_html=True
                )

            with col2:
                st.subheader("Structured JSON")
                st.code(json.dumps(extracted, indent=4), language="json")
    else:
        st.error("Failed to extract data or display the image.")

# # if st.button('Process Document') and selected_image:
# #     img, lines, extracted = process_image_and_extract_data(s3_bucket, selected_image)

# #     if img:
# #         st.image(img, caption="Uploaded Document", use_container_width=True)

# #         col1, col2 = st.columns([1.2, 1.8])  # Adjust width ratio for better layout

# #         with col1:
# #             st.subheader("Extracted Text Lines")
# #             with st.container():
# #                 st.markdown(
# #                     "<div style='height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 10px;'>"
# #                     + "<br>".join(lines)
# #                     + "</div>",
# #                     unsafe_allow_html=True
# #                 )

# #         with col2:
# #             st.subheader("Extracted Data (JSON)")
# #             with st.expander("View JSON", expanded=True):
# #                 st.code(json.dumps(extracted, indent=4), language="json")

# #     else:
# #         st.error("Failed to extract data or display the image.")
# # else:
# #     if not selected_image:
# #         st.warning("Please select an image to begin.")



# # import streamlit as st
# # import boto3
# # from PIL import Image
# # import io
# # import json
# # import logging
# # from try2 import extract_summary_fields, extract_line_items  # Import from try2.py

# # # Set up logging configuration to log to a file
# # log_file = "textract_processing.log"
# # log_handler = logging.FileHandler(log_file)
# # log_handler.setLevel(logging.INFO)
# # log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')  # Corrected string
# # log_handler.setFormatter(log_formatter)

# # logger = logging.getLogger()
# # logger.setLevel(logging.INFO)
# # logger.addHandler(log_handler)

# # # Set up the AWS Textract client
# # textract = boto3.client('textract', region_name='us-east-1')

# # # Add a title to the Streamlit app
# # st.title("Document OCR Processing using Amazon Textract")  # Add title

# # # Define S3 bucket
# # s3_bucket = st.text_input('Enter S3 Bucket Name:', 'fp-prod-s3')

# # # Load image filenames from 's3_filenames.txt' to populate the dropdown
# # def load_s3_filenames(file_path="../s3_filenames.txt"):
# #     try:
# #         with open(file_path, "r") as file:
# #             filenames = [line.strip() for line in file.readlines() if line.strip()]
# #         return filenames
# #     except FileNotFoundError:
# #         logger.error(f"File {file_path} not found.")
# #         st.error(f"File {file_path} not found.")
# #         return []

# # # Load filenames from the file
# # image_filenames = load_s3_filenames()

# # # Display the dropdown for selecting an image
# # if image_filenames:
# #     selected_image = st.selectbox('Select Image Filename from S3:', image_filenames)
# # else:
# #     selected_image = ""

# # # Process Image and Extract Data
# # def process_image_and_extract_data(s3_bucket, s3_file):
# #     """
# #     Fetch image from S3, perform Textract analysis, and return the result.
# #     """
# #     try:
# #         logger.info(f"Processing image {s3_file} from bucket {s3_bucket}...")

# #         # Get the image from S3
# #         s3_client = boto3.client('s3')
# #         image_obj = s3_client.get_object(Bucket=s3_bucket, Key=s3_file)
# #         image_data = image_obj['Body'].read()

# #         # Convert to image for display
# #         image = Image.open(io.BytesIO(image_data))

# #         # Call Textract AnalyzeExpense API with the input document in S3
# #         response_expense = textract.analyze_expense(
# #             Document={
# #                 'S3Object': {
# #                     'Bucket': s3_bucket,
# #                     'Name': s3_file
# #                 }
# #             }
# #         )

# #         # Extract summary fields and product details using AnalyzeExpense
# #         summary_data = extract_summary_fields(response_expense)
# #         products_data = extract_line_items(response_expense)

# #         # Call Textract AnalyzeDocument API to extract text line by line
# #         try:
# #             response_document = textract.analyze_document(
# #                 Document={
# #                     'S3Object': {
# #                         'Bucket': s3_bucket,
# #                         'Name': s3_file
# #                     }
# #                 },
# #                 FeatureTypes=['TEXT']
# #             )
# #         except textract.exceptions.InvalidParameterException as e:
# #             logger.error(f"InvalidParameterException: {e}")
# #             st.error(f"InvalidParameterException: {e}")
# #             return None, None, None
# #         except Exception as e:
# #             logger.error(f"Error calling AnalyzeDocument: {e}")
# #             st.error(f"Error calling AnalyzeDocument: {e}")
# #             return None, None, None

# #         # Extract lines of text from the AnalyzeDocument response
# #         lines_of_text = []
# #         for item in response_document['Blocks']:
# #             if item['BlockType'] == 'LINE':
# #                 lines_of_text.append(item['Text'])

# #         # Prepare final output data
# #         output = summary_data
# #         output["products"] = products_data

# #         logger.info("Extraction complete.")
        
# #         return image, lines_of_text, output

# #     except Exception as e:
# #         logger.error(f"An error occurred: {e}")
# #         st.error(f"An error occurred while processing the image: {e}")
# #         return None, None, None

# # # Process Image and Extract Data
# # def process_image_and_extract_data(s3_bucket, s3_file):
# #     try:
# #         logger.info(f"Processing image {s3_file} from bucket {s3_bucket}...")

# #         # Get the image from S3
# #         s3_client = boto3.client('s3')
# #         image_obj = s3_client.get_object(Bucket=s3_bucket, Key=s3_file)
# #         image_data = image_obj['Body'].read()

# #         # Convert to image for display
# #         image = Image.open(io.BytesIO(image_data))

# #         # Call Textract AnalyzeExpense
# #         response_expense = textract.analyze_expense(
# #             Document={'S3Object': {'Bucket': s3_bucket, 'Name': s3_file}}
# #         )

# #         # Extract summary and line items
# #         summary_data = extract_summary_fields(response_expense)
# #         products_data = extract_line_items(response_expense)

# #         # Analyze document for raw text
# #         response_document = textract.analyze_document(
# #             Document={'S3Object': {'Bucket': s3_bucket, 'Name': s3_file}},
# #             FeatureTypes=['TABLES', 'FORMS']  # You can include TEXT if needed
# #         )

# #         # Extract line text blocks
# #         lines_of_text = []
# #         for block in response_document.get('Blocks', []):
# #             if block.get('BlockType') == 'LINE':
# #                 text = block.get('Text', '').strip()
# #                 if text:
# #                     lines_of_text.append(text)

# #         # Combine data
# #         output = summary_data
# #         output["products"] = products_data

# #         logger.info("Extraction complete.")

# #         return image, lines_of_text, output

# #     except Exception as e:
# #         logger.error(f"An error occurred: {e}")
# #         st.error(f"An error occurred while processing the image: {e}")
# #         return None, None, None


# # # Display the results when the button is clicked
# # if st.button('Process Document') and selected_image:
# #     image, lines_of_text, extracted_data = process_image_and_extract_data(s3_bucket, selected_image)

# #     if image and extracted_data:
# #         # Display the image first
# #         st.image(image, caption="Uploaded Document", use_container_width=True)

# #         # Then display text and JSON side by side
# #         col1, col2 = st.columns([1, 1])

# #         with col1:
# #             st.subheader("Extracted Text Lines:")
# #             for line in lines_of_text:
# #                 st.write(line)

# #         with col2:
# #             st.subheader("Extracted Data:")
# #             st.json(extracted_data)

# #     else:
# #         st.error("Failed to extract data or display the image.")
# # else:
# #     if not selected_image:
# #         st.error("Please select an image from the dropdown.")
