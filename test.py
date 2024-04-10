from pdf2image import convert_from_path
import pytesseract

# Convert PDF to images
pages = convert_from_path(
    'C:\\Users\\Faithlin Hoe\\Downloads\\__SLEEPY_20231003_103741_2682.pdf'
)

# Use pytesseract to do OCR on the images
text = ""
for page in pages:
    text += pytesseract.image_to_string(page)

print(text)
# Now, text contains the extracted text from the image-based PDF
