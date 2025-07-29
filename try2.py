
# try2.py

import boto3
import logging

# Set up Textract client
textract = boto3.client('textract', region_name='us-east-1')

def extract_summary_fields(response, logger):
    summary_fields = response.get('ExpenseDocuments', [])[0].get('SummaryFields', [])
    extracted_data = {}

    for field in summary_fields:
        label = field.get('LabelDetection', {}).get('Text', '')
        field_type = field.get('Type', {}).get('Text', '')
        value = field.get('ValueDetection', {}).get('Text', '')

        key = label or field_type
        if key:
            extracted_data[key] = value

    logger.info(f"Extracted {len(extracted_data)} summary fields.")
    return extracted_data

def extract_line_items(response, logger):
    line_item_groups = response.get('ExpenseDocuments', [])[0].get('LineItemGroups', [])
    products = []

    for group in line_item_groups:
        for item in group.get("LineItems", []):
            product = {}
            for field in item.get("LineItemExpenseFields", []):
                key = field.get('Type', {}).get('Text', '')
                value = field.get('ValueDetection', {}).get('Text', '').strip()
                if key and value:
                    product[key] = value
            if product:
                products.append(product)

    logger.info(f"Extracted {len(products)} line items.")
    return products

# import boto3
# import json
# import logging
# from logging.handlers import RotatingFileHandler

# # Step 1: Set up logging configuration to log to a file
# log_file = "textract_processing.log"

# # Set up a rotating log handler to limit the size of the log file and keep old logs
# log_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)  # 5 MB max, 3 backups
# log_handler.setLevel(logging.INFO)

# # Create a formatter with detailed log messages
# log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# log_handler.setFormatter(log_formatter)

# # Add the handler to the logger
# logger = logging.getLogger()
# logger.setLevel(logging.INFO)
# logger.addHandler(log_handler)

# # Step 2: Set up the AWS Textract client
# textract = boto3.client('textract', region_name='us-east-1')

# # Step 3: Define your S3 bucket and document name
# s3_bucket = "fp-prod-s3"  
# # s3_file = "000A7DE8-9724-4E69-8AEB-840C3A467C43.jpg"  # Replace with your actual file name in S3
# s3_file = "040644B1-FFA1-4665-A8C0-B9EFCB3814B7.jpg"

# def extract_summary_fields(response):
#     """
#     Extracts summary fields from the Textract response and returns them as a dictionary.
#     """
#     try:
#         summary_fields = response.get('ExpenseDocuments', [])[0].get('SummaryFields', [])
#         extracted_data = {}

#         # Loop through each summary field
#         for field in summary_fields:
#             # Get field type (normalized type) and value
#             field_type = field.get('Type', {}).get('Text', '')
#             value = field.get('ValueDetection', {}).get('Text', '')
            
#             # Check if LabelDetection exists and get the label
#             label = field.get('LabelDetection', {}).get('Text', '')
            
#             # If LabelDetection exists, use it as the label
#             if label:
#                 extracted_data[label] = value
#             else:
#                 # If LabelDetection doesn't exist, try using field_type as the label
#                 extracted_data[field_type] = value
        
#         logger.info(f"Extracted {len(extracted_data)} summary fields.")
#         return extracted_data
#     except KeyError as e:
#         logger.error(f"Error extracting summary fields: {e}")
#         return {}


# def extract_line_items(response):
#     """
#     Extracts line items from the Textract response and returns them as a list of products.
#     Instead of mapping the fields, we store the raw fields and values.
#     """
#     try:
#         # Extract line item groups
#         line_item_groups = response.get('ExpenseDocuments', [])[0].get('LineItemGroups', [])
#         products = []

#         # Loop through each line item group and extract line item details
#         for line_item_group in line_item_groups:
#             for line_item in line_item_group.get("LineItems", []):
#                 # Initialize a dictionary to store all extracted fields for the current line item
#                 product_details = {}

#                 # Loop through each field within the LineItemExpenseFields and store them in the product_details
#                 for field in line_item.get('LineItemExpenseFields', []):
#                     field_type = field.get('Type', {}).get('Text', '')
#                     value = field.get('ValueDetection', {}).get('Text', '').strip()

#                     # Store the raw field type and its corresponding value
#                     if field_type and value:
#                         product_details[field_type] = value

#                 # If product details are not empty, append them to the products list
#                 if product_details:
#                     products.append(product_details)

#         logger.info(f"Extracted {len(products)} product(s) from line items.")
#         return products
#     except KeyError as e:
#         logger.error(f"Error extracting line items: {e}")
#         return []


# def main():
#     try:
#         # Call the Textract AnalyzeExpense API with the input document in S3
#         logger.info(f"\n\n#################### Starting new run for file {s3_file} ####################\n")
#         logger.info(f"Processing file {s3_file} from bucket {s3_bucket}...")
        
#         response = textract.analyze_expense(
#             Document={
#                 'S3Object': {
#                     'Bucket': s3_bucket,
#                     'Name': s3_file
#                 }
#             }
#         )

#         # Initialize the output dictionary
#         output = {}

#         # Extract summary fields and append them to the output
#         logger.info("Extracting summary fields...")
#         summary_data = extract_summary_fields(response)
#         output.update(summary_data)

#         # Extract product details and append them to the output
#         logger.info("Extracting line items...")
#         products_data = extract_line_items(response)
#         output["products"] = products_data

#         # Convert the extracted data to a JSON format
#         json_output = json.dumps(output, indent=4)

#         # Print the resulting JSON
#         logger.info("Extraction complete. Here is the extracted data:")
#         logger.info(json_output)

#         # Optional: print the result to stdout
#         print(json_output)

#     except Exception as e:
#         logger.error(f"An error occurred: {e}")
#         raise e

# # if __name__ == "__main__":
# #     main()

# # if __name__ == "__main__":
# #     list_file = "../s3_filenames.txt"   # <-- your txt file with one S3 object key per line
# #     try:
# #         with open(list_file, "r") as fh:
# #             keys = [line.strip() for line in fh if line.strip()]

# #         logger.info(f"Discovered {len(keys)} keys to process from {list_file}")

# #         for key in keys:
# #             # Reuse the existing global variable so main() stays untouched
# #             s3_file = key
# #             main()

# #     except Exception as e:
# #         logger.error(f"Failed to process keys from {list_file}: {e}")
# #         raise
