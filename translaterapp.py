import io
import re
import streamlit as st
from deep_translator import GoogleTranslator
import fitz  # PyMuPDF
import tempfile
import os
import base64
import time

class PDFTranslator:
    """Handles PDF translation with improved text positioning, formatting preservation and context awareness"""
    
    def __init__(self):
        """Initialize translator with Google Translator"""
        self.translator = GoogleTranslator  # Using GoogleTranslator from deep_translator
        
        # Keep the dictionaries as fallback for languages not supported by GoogleTranslator
        # or for when translation fails
        self.translation_dictionaries = {
            "es": {
                # Common words dictionary content (kept for fallback)
                "Hello": "Hola", "Document": "Documento", "Translation": "Traducción", 
                "File": "Archivo", "Text": "Texto", "Language": "Idioma",
                # Rest of the dictionary...
            },
            # Other language dictionaries would go here...
        }
        
        # Extend dictionaries as in original code
        self.extend_dictionaries()
    
    def extend_dictionaries(self):
        """Add more translation dictionaries with basic words for additional languages"""
        # Implementation from original code would go here
        pass
        
    def translate_text(self, text, target_language, max_retries=3, preserve_paragraphs=True):
        """
        Translate text using Google Translator with improved error handling and context preservation
        
        Args:
            text: Text to translate
            target_language: Target language code
            max_retries: Number of retries if translation fails
            preserve_paragraphs: Whether to preserve paragraph structure during translation
            
        Returns:
            Translated text with preserved formatting
        """
        if not text or not text.strip():
            return ""
            
        # Clean and prepare text while preserving paragraph structure
        if preserve_paragraphs:
            # Split text into paragraphs
            paragraphs = re.split(r'\n\s*\n', text)
            paragraphs = [p.strip() for p in paragraphs if p.strip()]
            
            if not paragraphs:
                return ""
                
            # If we have multiple paragraphs, translate them separately to maintain context
            if len(paragraphs) > 1:
                translated_paragraphs = []
                for paragraph in paragraphs:
                    # Skip translation for very short strings or numbers
                    if len(paragraph) < 3 or paragraph.isdigit():
                        translated_paragraphs.append(paragraph)
                        continue
                    # Translate each paragraph individually but maintain context within paragraph
                    trans_para = self.translate_text(paragraph, target_language, max_retries, False)
                    translated_paragraphs.append(trans_para)
                
                # Rejoin with original paragraph separation
                return "\n\n".join(translated_paragraphs)
        
        # Proceed with normal translation (single paragraph or full text)
        for attempt in range(max_retries):
            try:
                # Use deep_translator's GoogleTranslator
                translator = self.translator(source='auto', target=target_language)
                
                # Split longer texts to avoid token limits while preserving complete sentences
                max_length = 4000  # Google Translate limit is around 5000 chars, but we use a lower limit
                
                if len(text) > max_length:
                    # Split by sentences while respecting max_length
                    sentence_pattern = r'(?<=[.!?])\s+'
                    sentences = re.split(sentence_pattern, text)
                    chunks = []
                    current_chunk = []
                    current_length = 0
                    
                    for sentence in sentences:
                        # If adding this sentence exceeds max_length, finalize current chunk
                        if current_length + len(sentence) > max_length and current_chunk:
                            chunks.append(" ".join(current_chunk))
                            current_chunk = [sentence]
                            current_length = len(sentence)
                        else:
                            current_chunk.append(sentence)
                            current_length += len(sentence)
                    
                    # Add the last chunk if it exists
                    if current_chunk:
                        chunks.append(" ".join(current_chunk))
                    
                    # Translate each chunk while preserving context
                    translated_chunks = []
                    for chunk in chunks:
                        if not chunk.strip():
                            continue
                        translation = translator.translate(chunk)
                        translated_chunks.append(translation)
                        # Add a small delay to avoid rate limiting
                        time.sleep(0.5)
                    
                    return " ".join(translated_chunks)
                else:
                    translation = translator.translate(text)
                    return translation
                    
            except Exception as e:
                st.error(f"Translation error (attempt {attempt+1}/{max_retries}): {str(e)}")
                time.sleep(1)  # Wait before retrying
        
        # On failure after all retries, try fallback dictionary translation
        translated_text = self._fallback_dictionary_translation(text, target_language)
        if translated_text != text:  # If fallback succeeded
            return translated_text
            
        # If all else fails, return original text
        st.warning(f"Unable to translate text after {max_retries} attempts. Keeping original text.")
        return text

    def _fallback_dictionary_translation(self, text, target_language):
        """Fallback to dictionary-based translation when API fails"""
        if target_language not in self.translation_dictionaries:
            # If language not supported, return original
            return text
        
        # Ensure we're working with a string
        if not isinstance(text, str):
            text = str(text)
            
        # Get dictionary for target language
        dictionary = self.translation_dictionaries[target_language]
        translated_text = text
        
        # Replace words and phrases found in the dictionary
        for eng, trans in dictionary.items():
            # Make sure both eng and trans are strings before comparison
            if not isinstance(eng, str):
                eng = str(eng)
            if not isinstance(trans, str):
                trans = str(trans)
                
            try:
                # Use regex pattern for case-insensitive replacement
                pattern = re.compile(r'\b' + re.escape(eng) + r'\b', re.IGNORECASE)
                translated_text = pattern.sub(trans, translated_text)
            except Exception as e:
                # If any error occurs during replacement, continue with next word
                continue
        
        return translated_text
        
    def analyze_pdf(self, pdf_bytes):
        """Analyze the PDF structure to prepare for translation with enhanced text positioning"""
        try:
            # Open the PDF document
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Store text blocks with their formatting and position information
            text_blocks = []
            
            # Process each page
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Get page dimensions
                page_width = page.rect.width
                page_height = page.rect.height
                
                # Extract font information
                page_fonts = {}
                for font in page.get_fonts():
                    if font:
                        page_fonts[font[0]] = {
                            "name": font[0],
                            "type": font[1],
                            "embedded": font[2]
                        }
                
                # Extract text blocks with position and formatting information
                blocks = page.get_text("dict", sort=True)["blocks"]
                
                # Process blocks and merge related text blocks for better translation
                merged_blocks = self._merge_related_blocks(blocks, page_width)
                
                for block in merged_blocks:
                    if "lines" in block:
                        # Extract all text from the block to maintain context
                        block_text = ""
                        block_spans = []
                        min_x = float('inf')
                        min_y = float('inf')
                        max_x = 0
                        max_y = 0
                        
                        for line in block["lines"]:
                            for span in line["spans"]:
                                if span["text"].strip():
                                    block_text += span["text"] + " "
                                    block_spans.append(span)
                                    
                                    # Update bounding box
                                    min_x = min(min_x, span["bbox"][0])
                                    min_y = min(min_y, span["bbox"][1])
                                    max_x = max(max_x, span["bbox"][2])
                                    max_y = max(max_y, span["bbox"][3])
                        
                        if block_text.strip():
                            text_blocks.append({
                                'page': page_num,
                                'text': block_text.strip(),
                                'spans': block_spans,
                                'bbox': (min_x, min_y, max_x, max_y),
                                'block_type': block.get("type", 0),
                                'page_width': page_width,
                                'page_height': page_height
                            })
            
            return text_blocks, pdf_document
            
        except Exception as e:
            st.error(f"Error analyzing PDF: {str(e)}")
            return None, None
    
    def _merge_related_blocks(self, blocks, page_width):
        """Merge related text blocks to maintain context for translation"""
        if not blocks:
            return []
            
        # First, sort blocks by vertical position (y coordinate)
        sorted_blocks = sorted(blocks, key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])
        
        merged_blocks = []
        current_block = None
        current_y = 0
        max_y_gap = 15  # Maximum vertical gap to consider blocks as related
        
        for block in sorted_blocks:
            # Skip non-text blocks
            if block.get("type", 0) != 0 or "lines" not in block:
                merged_blocks.append(block)
                continue
                
            block_y = block.get("bbox", [0, 0, 0, 0])[1]
            
            # Start a new merged block if this is the first block or there's a significant gap
            if current_block is None or abs(block_y - current_y) > max_y_gap:
                # Add the previous merged block if it exists
                if current_block is not None:
                    merged_blocks.append(current_block)
                
                # Start a new block
                current_block = block.copy()
                current_y = block_y
            else:
                # Merge with the current block
                if "lines" in current_block:
                    current_block["lines"].extend(block.get("lines", []))
                
                # Update the bounding box
                current_block_bbox = current_block.get("bbox", [0, 0, 0, 0])
                block_bbox = block.get("bbox", [0, 0, 0, 0])
                
                current_block["bbox"] = (
                    min(current_block_bbox[0], block_bbox[0]),
                    min(current_block_bbox[1], block_bbox[1]),
                    max(current_block_bbox[2], block_bbox[2]),
                    max(current_block_bbox[3], block_bbox[3])
                )
                
                # Update current_y to the bottom of the merged block
                current_y = current_block["bbox"][3]
        
        # Add the last merged block if it exists
        if current_block is not None:
            merged_blocks.append(current_block)
            
        return merged_blocks
    
    def calculate_text_wrap(self, text, font_size, max_width):
        """
        Calculate how text should wrap within a given width
        with improved handling of sentence structure
        """
        # Approximate text width based on font size (simplified calculation)
        avg_char_width = font_size * 0.6
        text_width = len(text) * avg_char_width
        
        if text_width <= max_width:
            return [text]  # No wrapping needed
            
        # Calculate how many characters can fit per line (approximate)
        chars_per_line = int(max_width / avg_char_width)
        
        # Split text into sentences then words to preserve sentence structure where possible
        sentences = re.split(r'(?<=[.!?])\s+', text)
        lines = []
        current_line = []
        current_count = 0
        
        for sentence in sentences:
            # If sentence is short enough to fit on one line, try to keep it together
            if len(sentence) <= chars_per_line:
                if current_count + len(sentence) + 1 <= chars_per_line:
                    current_line.append(sentence)
                    current_count += len(sentence) + 1
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [sentence]
                    current_count = len(sentence)
            else:
                # Split long sentences into words
                words = sentence.split()
                for word in words:
                    word_len = len(word)
                    if current_count + word_len + 1 <= chars_per_line:  # +1 for space
                        current_line.append(word)
                        current_count += word_len + 1
                    else:
                        if current_line:
                            lines.append(" ".join(current_line))
                        current_line = [word]
                        current_count = word_len
        
        if current_line:
            lines.append(" ".join(current_line))
            
        return lines
    
    def adjust_font_size(self, text, rect_width, original_font_size):
        """
        Dynamically adjust font size if translated text is too long
        with improved handling of different character widths
        """
        # Adjust estimation factors for different languages
        lang_factors = {
            'zh-CN': 1.0,  # Chinese characters need more space
            'zh-TW': 1.0,
            'ja': 1.0,     # Japanese characters need more space
            'ko': 1.0,     # Korean characters need more space
            'de': 1.2,     # German tends to have longer words
            'ru': 1.1,     # Russian can have longer words
            'ar': 1.1,     # Arabic may need more space
            'default': 0.6 # Default factor for Latin-based languages
        }
        
        # Detect if text contains non-Latin characters and adjust factor accordingly
        factor = lang_factors['default']
        if any(ord(c) > 127 for c in text):
            # Use higher factor for non-Latin text
            for lang, lang_factor in lang_factors.items():
                if lang != 'default' and any(ord(c) > 1000 for c in text):
                    factor = lang_factor
                    break
        
        # Quick estimation of text width using the appropriate factor
        approx_width = len(text) * original_font_size * factor
        
        if approx_width <= rect_width:
            return original_font_size
        
        # Calculate scaling factor
        scaling_factor = rect_width / approx_width
        # Don't reduce by more than 30%
        min_scale = 0.7
        return max(original_font_size * scaling_factor, original_font_size * min_scale)
    
    def translate_pdf(self, pdf_bytes, target_language):
        """Translate PDF content with improved text positioning and formatting preservation"""
        try:
            # Analyze PDF structure
            text_blocks, pdf_document = self.analyze_pdf(pdf_bytes)
            
            if not text_blocks or not pdf_document:
                return None
            
            # Create a new PDF document (copy of the original)
            output_buffer = io.BytesIO()
            pdf_document.save(output_buffer)
            output_buffer.seek(0)
            
            translated_pdf = fitz.open(stream=output_buffer.getvalue(), filetype="pdf")
            
            # Group blocks by page
            blocks_by_page = {}
            for block in text_blocks:
                page_num = block['page']
                if page_num not in blocks_by_page:
                    blocks_by_page[page_num] = []
                blocks_by_page[page_num].append(block)
            
            # Process each page
            total_pages = len(translated_pdf)
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for page_num in range(total_pages):
                if page_num in blocks_by_page:
                    # Get the page
                    page = translated_pdf[page_num]
                    
                    # Process text blocks for this page
                    for i, block in enumerate(blocks_by_page[page_num]):
                        # Skip translation for images or non-text blocks
                        if block['block_type'] != 0:
                            continue
                            
                        # Skip translation for numbers or special characters only
                        block_text = block['text'].strip()
                        if not block_text or block_text.isdigit() or len(block_text) < 3:
                            continue
                        
                        # Check if text contains actual words (not just symbols)
                        if not re.search(r'[a-zA-Z\u0400-\u04FF\u0600-\u06FF\u3040-\u30FF\u4E00-\u9FFF\uAC00-\uD7AF]', block_text):
                            continue
                            
                        try:
                            # Get block information
                            bbox = block['bbox']
                            rect = fitz.Rect(bbox)
                            
                            # Skip very small blocks
                            if rect.width < 10 or rect.height < 10:
                                continue
                                
                            # Translate the text with paragraph preservation
                            translated_text = self.translate_text(block_text, target_language, preserve_paragraphs=True)
                            
                            # Create a redaction annotation to remove the original text
                            annot = page.add_redact_annot(rect)
                            
                            # Apply the redactions
                            page.apply_redactions()
                            
                            # Enhanced text placement with improved wrapping
                            if len(block['spans']) > 0:
                                span = block['spans'][0]  # Get first span for formatting
                                
                                # Calculate available space
                                rect_width = rect.width
                                rect_height = rect.height
                                
                                # Adjust font size if needed
                                original_font_size = span['size']
                                adjusted_font_size = self.adjust_font_size(translated_text, rect_width, original_font_size)
                                
                                # Calculate text wrapping with improved handling
                                wrapped_lines = self.calculate_text_wrap(translated_text, adjusted_font_size, rect_width)
                                
                                # Calculate line height
                                line_height = adjusted_font_size * 1.3
                                
                                # Position for text insertion (top-left of rectangle)
                                start_x = rect.x0 + 2  # Small padding
                                start_y = rect.y0 + adjusted_font_size  # Start with font size offset
                                
                                # Insert each line of text
                                for line_idx, line in enumerate(wrapped_lines):
                                    y_pos = start_y + line_idx * line_height
                                    
                                    # Check if we're still within vertical bounds
                                    if y_pos <= rect.y1:
                                        # Get text color from span or use default black
                                        color = span.get('color', (0, 0, 0))
                                        
                                        # Convert RGB tuple to hex color if needed
                                        if isinstance(color, tuple) and len(color) == 3:
                                            r, g, b = color
                                            color = (r/255, g/255, b/255)
                                            
                                        # Insert text with appropriate formatting
                                        page.insert_text(
                                            (start_x, y_pos),
                                            line,
                                            fontsize=adjusted_font_size,
                                            color=color
                                        )
                        except Exception as e:
                            st.warning(f"Skipping block due to error: {str(e)}")
                            continue
                
                # Update progress
                progress_value = (page_num + 1) / total_pages
                progress_bar.progress(progress_value)
                status_text.text(f"Translating page {page_num + 1} of {total_pages}...")
            
            # Save the translated PDF
            output_buffer = io.BytesIO()
            translated_pdf.save(output_buffer)
            output_buffer.seek(0)
            
            # Clear progress bar and status
            progress_bar.empty()
            status_text.empty()
            
            return output_buffer.getvalue()
            
        except Exception as e:
            st.error(f"Error translating PDF: {str(e)}")
            return None


# The rest of the functions (get_pdf_display_html, create_sidebar, display_features, main)
# remain the same as in your original code
# Include them below:

def get_pdf_display_html(pdf_bytes):
    """Convert PDF bytes to HTML for display in Streamlit with enhanced controls"""
    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    return f"""
        <div class="pdf-viewer-container">
            <div class="pdf-controls">
                <button class="pdf-btn" onclick="document.getElementById('pdf-frame').contentWindow.PDFViewerApplication.zoomIn();">
                    <span>🔍+</span>
                </button>
                <button class="pdf-btn" onclick="document.getElementById('pdf-frame').contentWindow.PDFViewerApplication.zoomOut();">
                    <span>🔍-</span>
                </button>
            </div>
            <iframe
                id="pdf-frame"
                src="data:application/pdf;base64,{base64_pdf}#view=FitH"
                width="100%"
                height="600"
                style="border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"
                type="application/pdf">
            </iframe>
        </div>
    """

def create_sidebar():
    """Create an informative sidebar with modern design"""
    with st.sidebar:
        st.markdown("<div class='sidebar-content'>", unsafe_allow_html=True)
        
        # Modern logo style with animated gradient
        st.markdown("""
        <div style="text-align: center; margin-bottom: 20px;">
            <div class="logo-container">
                <div class="logo-icon">🌏</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h2 style='text-align: center; margin-bottom: 25px; background: linear-gradient(to right, #4287f5, #7db9e8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>PDF Translator Pro</h2>", unsafe_allow_html=True)
        
        # Add improved sidebar content with animations
        st.markdown("""
        <div class="sidebar-card">
            <h3 class="sidebar-card-title">🌐 Available Languages</h3>
            <div class="sidebar-card-content">
                <div class="language-row"><span class="language-icon">✓</span>English, Spanish, French</div>
                <div class="language-row"><span class="language-icon">✓</span>German, Chinese, Japanese</div>
                <div class="language-row"><span class="language-icon">✓</span>Korean, Russian, Italian</div>
            </div>
        </div>
        
        <div class="sidebar-card">
            <h3 class="sidebar-card-title">🔄 How It Works</h3>
            <div class="sidebar-card-content">
                <div class="step-row"><span class="step-number">1</span><b>Upload</b> your PDF document</div>
                <div class="step-row"><span class="step-number">2</span><b>Preview</b> the original content</div>
                <div class="step-row"><span class="step-number">3</span><b>Select</b> target language</div>
                <div class="step-row"><span class="step-number">4</span><b>Translate</b> with formatting</div>
                <div class="step-row"><span class="step-number">5</span><b>Download</b> translated PDF</div>
            </div>
        </div>
        
        <div class="sidebar-card">
            <h3 class="sidebar-card-title">⭐ Pro Features</h3>
            <div class="sidebar-card-content">
                <div class="feature-row"><span class="feature-bullet">•</span>Google Neural Translation</div>
                <div class="feature-row"><span class="feature-bullet">•</span>Smart Text Wrapping</div>
                <div class="feature-row"><span class="feature-bullet">•</span>Intelligent Font Scaling</div>
                <div class="feature-row"><span class="feature-bullet">•</span>Layout Preservation</div>
                <div class="feature-row"><span class="feature-bullet">•</span>Image Retention</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

def display_features():
    """Display feature cards in a modern and attractive layout"""
    st.markdown("<h3 class='section-header'>Key Features</h3>", unsafe_allow_html=True)
    
    # Create a 2x2 grid of features with improved styling & hover effects
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🔄</div>
            <div class="feature-title">Smart Text Wrapping</div>
            <p class="feature-description">Intelligent text handling that automatically adjusts and wraps translated content to fit perfectly within the original layout.</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🧠</div>
            <div class="feature-title">Neural Translation</div>
            <p class="feature-description">Powered by Google's neural translation technology for accurate, context-aware translations across multiple languages.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Add a second row of features
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">📝</div>
            <div class="feature-title">Dynamic Font Scaling</div>
            <p class="feature-description">Automatically adjusts font sizes for different languages to maintain readability while preserving document layout.</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">👁️</div>
            <div class="feature-title">Interactive Preview</div>
            <p class="feature-description">Enhanced document viewer with zoom controls for detailed inspection before and after translation.</p>
        </div>
        """, unsafe_allow_html=True)

def main():
    # Set page config with a wider layout
    st.set_page_config(
        page_title="PDF Translator Pro",
        page_icon="🔄",
        layout="wide"
    )
    
    # Add custom CSS with improved styles and animations
    st.markdown("""
    <style>
    /* Modern color scheme with vibrant gradients */
    :root {
        --primary: #7C4DFF;
        --primary-light: #B388FF;
        --primary-dark: #5E35B1;
        --accent: #FF9A3C;
        --accent-light: #FFB74D;
        --text-dark: #2D3748;
        --text-light: #F7FAFC;
        --bg-light: #F7FAFC;
        --bg-dark: #1A202C;
        --success: #48BB78;
        --error: #F56565;
        --text-unique: #E83E8C; /* New unique text color (vibrant pink) */
    }
    
    /* Global styling with modern dark theme option */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4eaf0 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Typography enhancements */
    h1, h2, h3, h4, h5 {
        font-family: 'Poppins', sans-serif;
        letter-spacing: -0.5px;
    }
    
    /* Header with animated gradient */
    .main-header {
        font-size: 3.2rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
        text-align: center;
        background: linear-gradient(to right, var(--primary), var(--accent));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: gradient-shift 8s ease infinite;
        text-shadow: 0px 1px 2px rgba(0,0,0,0.1);
    }
    
    @keyframes gradient-shift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    .sub-header {
        font-size: 1.3rem;
        margin-bottom: 2.5rem;
        text-align: center;
        color: var(--text-unique); /* Changed to unique text color */
        opacity: 0.8;
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }
    
    /* Main container with glassmorphism effect */
    .glass-container {
        background: rgba(255, 255, 255, 0.6);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border-radius: 24px;
        padding: 2.5rem;
        box-shadow: 0 8px 32px rgba(31, 38, 135, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.18);
        margin-bottom: 2rem;
    }
    
    /* Section headers with accent lines */
    .section-header {
        position: relative;
        margin-top: 1.5rem;
        margin-bottom: 1.5rem;
        color: var(--primary-dark);
        font-size: 1.6rem;
        font-weight: 600;
        padding-bottom: 0.75rem;
        display: flex;
        align-items: center;
    }
    
    .section-header::before {
        content: "";
        display: inline-block;
        width: 8px;
        height: 28px;
        margin-right: 12px;
        background: linear-gradient(to bottom, var(--primary), var(--primary-light));
        border-radius: 4px;
    }
    
    /* Card containers with hover effects */
    .content-card {
        background: white;
        border-radius: 16px;
        padding: 1.8rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        border: 1px solid rgba(0,0,0,0.03);
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    
    .content-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 28px rgba(0,0,0,0.1);
        border-color: rgba(124, 77, 255, 0.2);
    }
    
    /* Feature cards with icons */
    .feature-card {
        border-radius: 16px;
        padding: 1.8rem;
        background: linear-gradient(145deg, #ffffff, #f0f0f0);
        box-shadow: 5px 5px 15px rgba(0,0,0,0.05), 
                   -5px -5px 15px rgba(255,255,255,0.6);
        transition: all 0.3s ease;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
        text-align: center;
    }
    
    .feature-card:hover {
        transform: translateY(-5px) scale(1.02);
    }
    
    .feature-card::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 4px;
        background: linear-gradient(90deg, var(--primary), var(--accent));
        transform: scaleX(0);
        transform-origin: left;
        transition: transform 0.4s ease;
    }
    
    .feature-card:hover::after {
        transform: scaleX(1);
    }
    
    .feature-icon {
        font-size: 2.5rem;
        margin-bottom: 1.2rem;
        height: 80px;
        width: 80px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 1.2rem auto;
        background: linear-gradient(145deg, #ffffff, #f0f0f0);
        border-radius: 50%;
        box-shadow: 5px 5px 10px rgba(0,0,0,0.05), 
                   -5px -5px 10px rgba(255,255,255,0.6);
        color: var(--primary);
    }
    
    .feature-title {
        font-size: 1.4rem;
        font-weight: 600;
        margin-bottom: 0.8rem;
        color: var(--text-unique); /* Changed to unique text color */
    }
    
    .feature-description {
        color: var(--text-unique); /* Changed to unique text color */
        opacity: 0.75;
        font-size: 0.95rem;
        line-height: 1.6;
    }
    
    /* Progress indicators */
    .progress-steps {
        display: flex;
        justify-content: space-between;
        margin-bottom: 2rem;
        position: relative;
    }
    
    .progress-steps::before {
        content: '';
        position: absolute;
        top: 40px;
        left: 0;
        right: 0;
        height: 3px;
        background: #e0e0e0;
        z-index: 1;
    }
    
    .step {
        position: relative;
        z-index: 2;
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 33.33%;
    }
    
    .step-number {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        background: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.8rem;
        font-weight: 600;
        margin-bottom: 1rem;
        color: var(--primary);
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
        position: relative;
        transition: all 0.3s ease;
    }
    
    .step-number::after {
        content: '';
        position: absolute;
        width: 60px;
        height: 60px;
        border-radius: 50%;
        border: 2px dashed var(--primary-light);
        animation: spin 20s linear infinite;
    }
    
    .step.active .step-number {
        background: var(--primary);
        color: white;
        transform: scale(1.1);
        box-shadow: 0 8px 24px rgba(124, 77, 255, 0.3);
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .step-title {
        font-weight: 600;
        color: var(--text-unique); /* Changed to unique text color */
        margin-top: 0.5rem;
        text-align: center;
    }
    
    /* Form controls with custom styling */
    .custom-file-upload {
        border: 2px dashed var(--primary-light);
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        transition: all 0.3s ease;
        cursor: pointer;
        background-color: rgba(124, 77, 255, 0.05);
    }
    
    .custom-file-upload:hover {
        border-color: var(--primary);
        background-color: rgba(124, 77, 255, 0.1);
    }
    
    .upload-icon {
        font-size: 3rem;
        color: var(--primary);
        margin-bottom: 1rem;
    }
    
    /* Language selector styling */
    .language-select {
        background-color: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.05);
    }
    
    .language-container {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
        gap: 10px;
        margin-top: 1rem;
    }
    
    .language-option {
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        cursor: pointer;
        transition: all 0.2s ease;
        border: 1px solid #e0e0e0;
    }
    
    .language-option:hover {
        background-color: rgba(124, 77, 255, 0.1);
        border-color: var(--primary-light);
    }
    
    .language-option.selected {
        background-color: var(--primary);
        color: white;
        border-color: var(--primary-dark);
        box-shadow: 0 4px 12px rgba(124, 77, 255, 0.3);
    }
    
    /* Action buttons with animations */
    .action-button {
        background: linear-gradient(90deg, var(--primary), var(--primary-dark));
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.8rem 2rem;
        font-weight: 600;
        font-size: 1.1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 16px rgba(124, 77, 255, 0.3);
        position: relative;
        overflow: hidden;
        cursor: pointer;
        display: inline-block;
        text-align: center;
        width: 100%;
    }
    
    .action-button:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(124, 77, 255, 0.4);
    }
    
    .action-button::before {
        content: "";
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(
            90deg, 
            rgba(255, 255, 255, 0) 0%, 
            rgba(255, 255, 255, 0.2) 50%, 
            rgba(255, 255, 255, 0) 100%
        );
        transition: left 0.7s ease;
    }
    
    .action-button:hover::before {
        left: 100%;
    }
    
    /* PDF viewer with custom controls */
    .pdf-viewer {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 8px 24px rgba(0,0,0,0.1);
        background-color: white;
    }
    
    .pdf-controls {
        position: absolute;
        top: 15px;
        right: 15px;
        display: flex;
        gap: 8px;
        z-index: 100;
    }
    
    .pdf-control-btn {
        background: rgba(255,255,255,0.9);
        border: none;
        border-radius: 8px;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.2s ease;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    
    .pdf-control-btn:hover {
        background: white;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0,0,0,0.15);
    }
    
    /* Status indicators */
    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    .status-badge.processing {
        background-color: rgba(255, 154, 60, 0.15);
        color: #B45309;
    }
    
    .status-badge.complete {
        background-color: rgba(72, 187, 120, 0.15);
        color: #2F855A;
    }
    
    .status-badge.error {
        background-color: rgba(245, 101, 101, 0.15);
        color: #C53030;
    }
    
    /* Download button with pulse effect */
    .download-button {
        position: relative;
        display: inline-block;
        padding: 12px 24px;
        background: linear-gradient(90deg, var(--success), #38A169);
        color: white;
        border-radius: 12px;
        font-weight: 600;
        font-size: 1.1rem;
        text-align: center;
        text-decoration: none;
        transition: all 0.3s ease;
        box-shadow: 0 6px 16px rgba(72, 187, 120, 0.3);
        width: 100%;
        margin-top: 1.5rem;
    }
    
    .download-button:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(72, 187, 120, 0.4);
    }
    
    .download-button::after {
        content: '';
        position: absolute;
        width: 100%;
        height: 100%;
        top: 0;
        left: 0;
        border-radius: 12px;
        background: rgba(72, 187, 120, 0.4);
        z-index: -1;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% {
            transform: scale(1);
            opacity: 0.7;
        }
        50% {
            transform: scale(1.05);
            opacity: 0.3;
        }
        100% {
            transform: scale(1);
            opacity: 0.7;
        }
    }
    
    /* Empty state with illustrations */
    .empty-state {
        text-align: center;
        padding: 3rem 1.5rem;
        border-radius: 16px;
        background-color: white;
        box-shadow: 0 4px 16px rgba(0,0,0,0.05);
    }
    
    .empty-state-icon {
        width: 150px;
        height: 150px;
        margin: 0 auto 1.5rem;
        opacity: 0.7;
    }
    
    .empty-state-title {
        font-size: 1.6rem;
        font-weight: 600;
        color: var(--text-unique); /* Changed to unique text color */
        margin-bottom: 1rem;
    }
    
    .empty-state-desc {
        color: var(--text-unique); /* Changed to unique text color */
        opacity: 0.7;
        max-width: 500px;
        margin: 0 auto;
        line-height: 1.6;
    }
    
    /* Sidebar styling */
    .sidebar-header {
        display: flex;
        align-items: center;
        margin-bottom: 2rem;
    }
    
    .app-logo {
        width: 60px;
        height: 60px;
        border-radius: 16px;
        background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 6px 16px rgba(124, 77, 255, 0.4);
        margin-right: 1rem;
    }
    
    .logo-icon {
        font-size: 2rem;
        color: white;
    }
    
    .app-name {
        font-size: 1.4rem;
        font-weight: 700;
        color: var(--text-unique); /* Changed to unique text color */
    }
    
    .sidebar-menu {
        margin-top: 2rem;
    }
    
    .menu-item {
        display: flex;
        align-items: center;
        padding: 0.8rem 1rem;
        border-radius: 12px;
        transition: all 0.2s ease;
        margin-bottom: 0.5rem;
        cursor: pointer;
    }
    
    .menu-item:hover {
        background-color: rgba(124, 77, 255, 0.1);
    }
    
    .menu-item.active {
        background-color: var(--primary);
        color: white;
        box-shadow: 0 4px 12px rgba(124, 77, 255, 0.3);
    }
    
    .menu-icon {
        margin-right: 1rem;
        font-size: 1.2rem;
    }
    
    /* Loading animation */
    .loading-animation {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 2rem;
    }
    
    .loading-spinner {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        border: 3px solid rgba(124, 77, 255, 0.2);
        border-top-color: var(--primary);
        animation: spinner 1s linear infinite;
    }
    
    @keyframes spinner {
        to {
            transform: rotate(360deg);
        }
    }
    
    /* Tooltip styling */
    .tooltip {
        position: relative;
        display: inline-block;
    }
    
    .tooltip .tooltiptext {
        visibility: hidden;
        background-color: var(--bg-dark);
        color: var(--text-light);
        text-align: center;
        border-radius: 8px;
        padding: 10px 15px;
        position: absolute;
        z-index: 1;
        bottom: 125%;
        left: 50%;
        transform: translateX(-50%);
        opacity: 0;
        transition: opacity 0.3s;
        width: 180px;
        font-size: 0.85rem;
        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
    }
    
    .tooltip .tooltiptext::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -5px;
        border-width: 5px;
        border-style: solid;
        border-color: var(--bg-dark) transparent transparent transparent;
    }
    
    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
    }
    
    /* Footer styling */
    .app-footer {
        text-align: center;
        padding: 2rem 0;
        margin-top: 3rem;
        color: var(--text-unique); /* Changed to unique text color */
        opacity: 0.7;
        font-size: 0.9rem;
        border-top: 1px solid rgba(0,0,0,0.05);
    }
    
    /* Mobile responsiveness */
    @media screen and (max-width: 768px) {
        .main-header {
            font-size: 2.5rem;
        }
        
        .sub-header {
            font-size: 1.1rem;
        }
        
        .glass-container {
            padding: 1.5rem;
        }
        
        .step-number {
            width: 60px;
            height: 60px;
            font-size: 1.5rem;
        }
        
        .step-number::after {
            width: 45px;
            height: 45px;
        }
        
        .progress-steps::before {
            top: 30px;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create sidebar with modern design
    create_sidebar()
    
    # Main container with animated header
    st.markdown("<h1 class='main-header'>PDF Translator Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Transform your documents into multiple languages while preserving perfect layout, formatting, and design across 100+ languages</p>", unsafe_allow_html=True)
    

    # Display feature cards with modern neomorphic design
    display_features()
    
    # Initialize PDF translator
    translator = PDFTranslator()
    
    # Language options with country codes recognized by deep_translator
    language_options = {
        "Spanish": "es",
        "French": "fr",
        "German": "de",
        "Chinese (Simplified)": "zh-CN",
        "Chinese (Traditional)": "zh-TW",
        "Japanese": "ja",
        "Korean": "ko",
        "Russian": "ru",
        "Italian": "it",
        "Portuguese": "pt",
        "Dutch": "nl",
        "Arabic": "ar",
        "Hindi": "hi",
        "Polish": "pl",
        "Turkish": "tr",
        "Vietnamese": "vi",
        "Thai": "th",
        "Swedish": "sv",
        "Norwegian": "no",
        "Finnish": "fi",
        "Danish": "da",
        "Czech": "cs",
        "Greek": "el",
        "Hungarian": "hu",
        "Romanian": "ro",
        "Ukrainian": "uk",
        "Hebrew": "he",
        "Indonesian": "id",
        "Malay": "ms"
    }
    
    # Main workflow container
    st.markdown("<div class='glass-container'>", unsafe_allow_html=True)
    
    # Create a 3-column layout for main content
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.markdown("<div class='content-card'>", unsafe_allow_html=True)
        st.markdown("<h3 class='section-header'>Upload Document</h3>", unsafe_allow_html=True)
        
        # Custom file uploader
        st.markdown("""
        <div class="custom-file-upload">
            <div class="upload-icon">📄</div>
            <h4>Drop your PDF here</h4>
            <p style="opacity: 0.7;">or click to browse files</p>
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("Choose a PDF file", type=['pdf'], label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("<div class='content-card'>", unsafe_allow_html=True)
        st.markdown("<h3 class='section-header'>Select Language</h3>", unsafe_allow_html=True)
        
        # Enhanced language selector
        st.markdown("""
        <div class="language-select">
            <h4>Target Language</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Direct language selection with no tabs
        target_language = st.selectbox("All Languages", list(language_options.keys()), label_visibility="collapsed")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col3:
        st.markdown("<div class='content-card'>", unsafe_allow_html=True)
        st.markdown("<h3 class='section-header'>Process Translation</h3>", unsafe_allow_html=True)
        
        # Enhanced action button
        start_translation = st.button("Translate Document", key="translate_btn", use_container_width=True)
        
        # Settings expander
        with st.expander("Advanced Settings"):
            preserve_formatting = st.toggle("Preserve Original Formatting", value=True)
            translation_quality = st.select_slider(
                "Translation Quality",
                options=["Fast", "Balanced", "High Quality"],
                value="Balanced"
            )
            
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Display original and translated PDFs
    if uploaded_file is not None:
        # Store the uploaded file in a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        # Create a container for the PDFs with a modern design
        st.markdown("<div class='glass-container'>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("<div class='content-card' style='height: auto;'>", unsafe_allow_html=True)
            st.markdown("<h3 class='section-header'>Original Document</h3>", unsafe_allow_html=True)
            
            # Enhanced PDF viewer
            st.markdown("""
            <div class="pdf-viewer">
                <div class="pdf-controls">
                    <button class="pdf-control-btn">
                        <span>➕</span>
                    </button>
                    <button class="pdf-control-btn">
                        <span>➖</span>
                    </button>
                </div>
            """, unsafe_allow_html=True)
            
            pdf_display = get_pdf_display_html(uploaded_file.getvalue())
            st.markdown(pdf_display, unsafe_allow_html=True)
            st.markdown("</div></div>", unsafe_allow_html=True)
        
        # Process translation
        if start_translation:
            try:
                with col2:
                    st.markdown("<div class='content-card' style='height: auto;'>", unsafe_allow_html=True)
                    st.markdown("<h3 class='section-header'>Translated Document</h3>", unsafe_allow_html=True)
                    
                    # Status badge for processing
                    st.markdown("""
                    <div class="status-badge processing">
                        <span>⚙️ Processing Translation</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Get language code
                    lang_code = language_options.get(target_language, "es")
                    
                    with st.spinner(f"Translating document to {target_language}..."):
                        # Translate the PDF
                        translated_pdf = translator.translate_pdf(uploaded_file.getvalue(), lang_code)
                        
                        if translated_pdf:
                            # Update status badge to complete
                            st.markdown("""
                            <div class="status-badge complete">
                                <span>✅ Translation Complete</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Display translated PDF with enhanced viewer
                            st.markdown("""
                            <div class="pdf-viewer">
                                <div class="pdf-controls">
                                    <button class="pdf-control-btn">
                                        <span>➕</span>
                                    </button>
                                    <button class="pdf-control-btn">
                                        <span>➖</span>
                                    </button>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            pdf_display = get_pdf_display_html(translated_pdf)
                            st.markdown(pdf_display, unsafe_allow_html=True)
                            st.markdown("</div>", unsafe_allow_html=True)
                            
                            # Enhanced download button
                            st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
                            st.download_button(
                                label="📥 Download Translated PDF",
                                data=translated_pdf,
                                file_name=f"translated_{uploaded_file.name}",
                                mime="application/pdf",
                                key="download_button",
                                use_container_width=True
                            )
                            st.markdown("</div>", unsafe_allow_html=True)
                        else:
                            st.error("Translation failed. Please try again with a different PDF.")
                    
                    st.markdown("</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"An error occurred during translation: {str(e)}")
    else:
        # Show placeholder or instructions when no file is uploaded
        st.markdown("""
        <div style="text-align: center; padding: 3rem; background-color: white; border-radius: 12px; margin: 2rem 0; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <img src="https://cdn-icons-png.flaticon.com/512/5910/5910208.png" width="120" style="opacity: 0.5; margin-bottom: 1rem;">
            <h3 style="color: #6c757d; font-weight: 500;">Upload a PDF document to begin</h3>
            <p style="color: #adb5bd; max-width: 500px; margin: 0 auto;">PDF Translator Pro will preserve your document layout, formatting, images and text positioning during translation.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Footer section
    st.markdown("""
    <div style="text-align: center; margin-top: 3rem; padding: 1rem; color: #6c757d; font-size: 0.9rem;">
        <p>PDF Translator Pro | Version 2.1 | Powered by Neural Translation Technology</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()