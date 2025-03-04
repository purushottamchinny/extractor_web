import streamlit as st
import cv2
import numpy as np
import pytesseract
from PIL import Image
import io
import os

def preprocess_image(image, preprocessing_steps):
    """Apply various preprocessing techniques to improve OCR results"""
    img = image.copy()
    
    if preprocessing_steps['grayscale']:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if preprocessing_steps['threshold'] != 'none':
        if preprocessing_steps['grayscale'] is False:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
        if preprocessing_steps['threshold'] == 'simple':
            _, img = cv2.threshold(img, preprocessing_steps['threshold_value'], 255, cv2.THRESH_BINARY)
        elif preprocessing_steps['threshold'] == 'adaptive':
            img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY, 11, 2)
        elif preprocessing_steps['threshold'] == 'otsu':
            _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    if preprocessing_steps['blur'] != 'none':
        if preprocessing_steps['blur'] == 'gaussian':
            img = cv2.GaussianBlur(img, (5, 5), 0)
        elif preprocessing_steps['blur'] == 'median':
            img = cv2.medianBlur(img, 5)
    
    if preprocessing_steps['denoise']:
        if len(img.shape) == 2:  # If grayscale
            img = cv2.fastNlMeansDenoising(img)
        else:  # If color
            img = cv2.fastNlMeansDenoisingColored(img)
            
    if preprocessing_steps['dilation']:
        kernel = np.ones((5,5), np.uint8)
        img = cv2.dilate(img, kernel, iterations=1)
        
    if preprocessing_steps['erosion']:
        kernel = np.ones((5,5), np.uint8)
        img = cv2.erode(img, kernel, iterations=1)
    
    return img

def main():
    st.title("Advanced OCR Text Extraction App")
    st.write("Upload an image to extract text with enhanced preprocessing")
    
    # Tesseract configuration section
    with st.sidebar.expander("Tesseract Configuration", expanded=True):
        # Based on previous error, suggest the path
        default_path = "/usr/local/Cellar/tesseract/5.5.0/share/tessdata/"
        
        # Option to set tessdata prefix
        tessdata_prefix = st.text_input(
            "TESSDATA_PREFIX (path to tessdata directory)",
            value=default_path,
            placeholder="e.g., /usr/local/Cellar/tesseract/5.5.0/share/tessdata/"
        )
        
        # OCR language
        lang = st.selectbox(
            "OCR Language", 
            ["eng", "eng+fra", "eng+deu", "eng+spa", "eng+ita"],
            index=0
        )
        
        # OCR config
        config = st.text_input(
            "OCR Config", 
            value="--psm 3",
            help="--psm 3 is default for paragraph text. Use --psm 6 for a single uniform block"
        )
        
        # Apply Tesseract configuration
        if tessdata_prefix:
            os.environ["TESSDATA_PREFIX"] = tessdata_prefix
    
    # Image Preprocessing Options
    with st.sidebar.expander("Image Preprocessing", expanded=True):
        preprocessing_steps = {
            'grayscale': st.checkbox("Convert to Grayscale", value=True),
            'threshold': st.selectbox(
                "Thresholding Method", 
                ["none", "simple", "adaptive", "otsu"],
                index=3
            ),
            'threshold_value': st.slider("Threshold Value", 0, 255, 127) if st.session_state.get('threshold', 'none') == 'simple' else 127,
            'blur': st.selectbox(
                "Blur Method", 
                ["none", "gaussian", "median"],
                index=2
            ),
            'denoise': st.checkbox("Apply Denoising", value=True),
            'dilation': st.checkbox("Apply Dilation", value=False),
            'erosion': st.checkbox("Apply Erosion", value=False)
        }
    
    # File uploader
    uploaded_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        # Read the image
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        # Display the uploaded image
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Original Image")
            st.image(uploaded_file, use_column_width=True)
        
        # Preprocess image
        processed_img = preprocess_image(img, preprocessing_steps)
        
        with col2:
            st.subheader("Processed Image")
            st.image(processed_img, use_column_width=True)
        
        # Add a button to perform OCR
        if st.button("Extract Text"):
            try:
                # Extract text using pytesseract with the processed image
                text = pytesseract.image_to_string(processed_img, lang=lang, config=config)
                
                # Display the extracted text
                st.subheader("Extracted Text:")
                st.text_area("", text, height=200)
                
                # Option to download the extracted text
                text_file = io.StringIO()
                text_file.write(text)
                st.download_button(
                    label="Download extracted text",
                    data=text_file.getvalue(),
                    file_name="extracted_text.txt",
                    mime="text/plain"
                )
            
            except pytesseract.pytesseract.TesseractError as e:
                st.error(f"Tesseract Error: {str(e)}")
                
                st.info("""
                Try these steps to fix the issue:
                1. Check if Tesseract is properly installed:
                   ```
                   tesseract --version
                   ```
                
                2. Make sure the language data files are installed:
                   ```
                   brew install tesseract-lang
                   ```
                
                3. If you're still having issues, try uninstalling and reinstalling Tesseract:
                   ```
                   brew uninstall tesseract tesseract-lang
                   brew install tesseract tesseract-lang
                   ```
                """)

if __name__ == "__main__":
    main()