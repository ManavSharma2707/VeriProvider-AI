import os
import json
import time
import typing
import mimetypes
import warnings
from dotenv import load_dotenv
from abc import ABC, abstractmethod
from PIL import Image

# NEW IMPORTS FOR GOOGLE GENAI
from google import genai
from google.genai import types

# Suppress warnings to keep output clean
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


# ==============================================================================
# CONFIGURATION MANAGEMENT
# ==============================================================================

class ConfigurationManager:
    """Handles environment configuration."""
    
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('GEMINI_API_KEY')
        # Note: New SDK uses client instantiation, so we don't need a global configure step here.
    
    def is_configured(self) -> bool:
        """Check if API key is present."""
        if not self.api_key:
            print("WARNING: GEMINI_API_KEY not found. API calls will fail.")
            return False
        return True


# ==============================================================================
# FILE CONTENT PREPARATION
# ==============================================================================

class ContentPreparer(ABC):
    """Abstract base class for content preparation strategies."""
    
    @abstractmethod
    def can_handle(self, file_path: str, mime_type: str) -> bool:
        pass
    
    @abstractmethod
    def prepare(self, file_path: str) -> typing.List:
        pass


class DocxContentPreparer(ContentPreparer):
    """Prepares Word document content."""
    
    def can_handle(self, file_path: str, mime_type: str) -> bool:
        return file_path.lower().endswith('.docx')
    
    def prepare(self, file_path: str) -> typing.List:
        print(f"Detected format: Word Document (.docx)")
        text_content = self._extract_text_from_docx(file_path)
        return [text_content]
    
    def _extract_text_from_docx(self, docx_path: str) -> str:
        """Helper to extract raw text from a Word document."""
        try:
            import docx
        except ImportError:
            raise ImportError("To process .docx files, please run: pip install python-docx")
        
        try:
            doc = docx.Document(docx_path)
        except Exception as e:
            raise ValueError(f"Could not open Word document. It might be corrupted. Details: {e}")

        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return "\n".join(full_text)


class PdfContentPreparer(ContentPreparer):
    """Prepares PDF content."""
    
    def can_handle(self, file_path: str, mime_type: str) -> bool:
        return mime_type == 'application/pdf'
    
    def prepare(self, file_path: str) -> typing.List:
        print(f"Detected format: PDF")
        with open(file_path, "rb") as f:
            pdf_data = f.read()
        
        # New SDK Requirement: Use types.Part for binary blobs
        return [types.Part.from_bytes(data=pdf_data, mime_type='application/pdf')]


class ImageContentPreparer(ContentPreparer):
    """Prepares image content."""
    
    def can_handle(self, file_path: str, mime_type: str) -> bool:
        return True 
    
    def prepare(self, file_path: str) -> typing.List:
        mime_type, _ = mimetypes.guess_type(file_path)
        print(f"Detected format: Image ({mime_type})")
        img = Image.open(file_path)
        # The new SDK handles PIL images natively in the contents list
        return [img]


class ContentPreparerFactory:
    """Factory for selecting appropriate content preparer."""
    
    def __init__(self):
        self.preparers = [
            DocxContentPreparer(),
            PdfContentPreparer(),
            ImageContentPreparer()  # Must be last as it's the fallback
        ]
    
    def get_preparer(self, file_path: str) -> ContentPreparer:
        mime_type, _ = mimetypes.guess_type(file_path)
        for preparer in self.preparers:
            if preparer.can_handle(file_path, mime_type):
                return preparer
        return self.preparers[-1]


# ==============================================================================
# RESPONSE PROCESSING
# ==============================================================================

class ResponseProcessor:
    """Processes and parses API responses."""
    
    def process(self, raw_text: str) -> dict:
        cleaned_text = raw_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        
        return json.loads(cleaned_text.strip())


# ==============================================================================
# API INTERACTION (UPDATED FOR NEW SDK)
# ==============================================================================

class GeminiApiClient:
    """Handles interactions with the updated Google GenAI API."""
    
    def __init__(self, api_key: str, model_name: str = 'gemini-2.5-flash'):
        self.model_name = model_name
        self.client = None
        if api_key:
            try:
                # NEW CLIENT INIT
                self.client = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"Error initializing GenAI Client: {e}")
                raise
    
    def generate_content(self, request_content: list, max_retries: int = 3) -> typing.Optional[str]:
        if not self.client:
            print("Client not initialized.")
            return None

        for attempt in range(max_retries):
            try:
                # NEW GENERATION CALL
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=request_content
                )
                return response.text
            except Exception as e:
                print(f"Attempt {attempt + 1}/{max_retries}: API call failed - {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return None
        return None


# ==============================================================================
# PROVIDER EXTRACTION
# ==============================================================================

class ProviderExtractor:
    """Main extractor that orchestrates the extraction process."""
    
    def __init__(self, 
                 content_preparer_factory: ContentPreparerFactory,
                 api_client: GeminiApiClient,
                 response_processor: ResponseProcessor):
        self.content_preparer_factory = content_preparer_factory
        self.api_client = api_client
        self.response_processor = response_processor
        self.prompt = (
            'Analyze this document (image, PDF, or text) regarding a healthcare provider. '
            'Extract the following fields strictly as JSON: '
            '"provider_name", "npi_number" (if visible, else null), '
            '"address_raw" (full address string), "phone", "website". '
            'Do not wrap the output in markdown. Return raw JSON only.'
        )
        self.max_retries = 3
    
    def extract_provider_from_file(self, file_path: str) -> typing.Optional[dict]:
        # Don't print full processing header here to avoid spamming loops in fallback
        
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return None
        
        try:
            preparer = self.content_preparer_factory.get_preparer(file_path)
            content_parts = preparer.prepare(file_path)
        except ImportError as e:
            print(f"Missing Library Error: {e}")
            return None
        except Exception as e:
            print(f"Error preparing file {os.path.basename(file_path)}: {e}")
            return None
        
        request_content = [self.prompt] + content_parts
        
        for attempt in range(self.max_retries):
            try:
                raw_text = self.api_client.generate_content(request_content, max_retries=1)
                
                if raw_text is None:
                    if attempt < self.max_retries - 1:
                        time.sleep(2)
                        continue
                    else:
                        return None
                
                provider_data = self.response_processor.process(raw_text)
                print("✓ Successfully extracted provider data")
                return provider_data
                
            except json.JSONDecodeError as e:
                print(f"Attempt {attempt + 1}/{self.max_retries}: JSON parsing failed - {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                else:
                    print(f"Max retries reached. Raw: {raw_text}")
                    return None
        
        return None


# ==============================================================================
# BATCH PROCESSING
# ==============================================================================

class BatchProcessor:
    """Processes multiple files in batch."""
    
    def __init__(self, extractor: ProviderExtractor):
        self.extractor = extractor
    
    def batch_process_files(self, file_paths: list) -> list:
        results = []
        for file_path in file_paths:
            print(f"--- Processing File: {os.path.basename(file_path)} ---")
            result = self.extractor.extract_provider_from_file(file_path)
            if result:
                results.append({
                    'file': os.path.basename(file_path),
                    'path': file_path,
                    'data': result,
                    'status': 'success'
                })
            else:
                results.append({
                    'file': os.path.basename(file_path),
                    'path': file_path,
                    'data': None,
                    'status': 'failed'
                })
            print()
        return results


# ==============================================================================
# RESULTS MANAGEMENT
# ==============================================================================

class ResultsManager:
    """Manages saving and displaying results."""
    
    def save_results_to_json(self, results: list, output_path: str = 'extracted_providers.json') -> bool:
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"✓ Results saved to {output_path}")
            return True
        except Exception as e:
            print(f"Error saving results: {e}")
            return False
    
    def display_summary(self, results: list):
        print("\n" + "=" * 60)
        print("EXTRACTION SUMMARY")
        print("=" * 60)
        
        successful = sum(1 for r in results if r['status'] == 'success')
        failed = len(results) - successful
        
        print(f"Total files processed: {len(results)}")
        print(f"Successful extractions: {successful}")
        print(f"Failed extractions: {failed}")
        print()
        
        for result in results:
            if result['status'] == 'success':
                print(f"\n✓ {result['file']}:")
                print(json.dumps(result['data'], indent=2))
            else:
                print(f"\n✗ {result['file']}: Extraction failed")


# ==============================================================================
# FILE PATH RESOLVER (Auto-Discovery)
# ==============================================================================

class FilePathResolver:
    """Resolves and discovers file paths for the application."""
    
    def __init__(self):
        self.current_script_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.current_script_dir)
        self.input_dir = os.path.join(self.project_root, 'input_images')
    
    def get_all_input_files(self) -> list:
        """
        Auto-Discovers ALL supported files in the input_images directory.
        """
        if not os.path.exists(self.input_dir):
            print(f"Warning: Directory {self.input_dir} does not exist.")
            return []
            
        files = []
        # List of extensions we know we can handle
        supported_extensions = (
            '.jpg', '.jpeg', '.png', '.webp', '.heic', '.bmp', # Images
            '.pdf',                                            # PDFs
            '.docx'                                            # Word
        )
        
        print(f"Scanning directory: {self.input_dir} ...")
        
        for filename in os.listdir(self.input_dir):
            if filename.lower().endswith(supported_extensions):
                full_path = os.path.join(self.input_dir, filename)
                files.append(full_path)
                
        return files


# ==============================================================================
# APPLICATION ORCHESTRATOR
# ==============================================================================

class DocumentExtractorApplication:
    """Main application orchestrator."""
    
    def __init__(self):
        self.config_manager = ConfigurationManager()
        self.content_preparer_factory = ContentPreparerFactory()
        
        if self.config_manager.is_configured():
            # Pass the key explicitly to the new client wrapper
            self.api_client = GeminiApiClient(api_key=self.config_manager.api_key)
        else:
            self.api_client = None
            
        self.response_processor = ResponseProcessor()
        
        if self.api_client:
            self.extractor = ProviderExtractor(
                self.content_preparer_factory,
                self.api_client,
                self.response_processor
            )
            self.batch_processor = BatchProcessor(self.extractor)
        else:
            self.extractor = None
            self.batch_processor = None
            
        self.results_manager = ResultsManager()
        self.file_path_resolver = FilePathResolver()
    
    def run(self):
        print("=" * 60)
        print("Gemini 2.5 Document Extractor - Batch Processor")
        print("=" * 60)
        print()
        
        if not self.extractor:
             print("Critical Error: Application not configured correctly.")
             return

        # AUTO-DISCOVERY: Get all files in input_images
        input_files = self.file_path_resolver.get_all_input_files()
        
        if not input_files:
            print(f"No valid files (images/PDF/Word) found in 'input_images'.")
            return
        
        # Process files
        print(f"Found {len(input_files)} file(s) to process.\n")
        results = self.batch_processor.batch_process_files(input_files)
        
        # Display & Save
        self.results_manager.display_summary(results)
        print("\n" + "=" * 60)
        self.results_manager.save_results_to_json(results)


# ==============================================================================
# HELPER FOR EXTERNAL IMPORT
# ==============================================================================
def extract_provider_from_file(file_path: str) -> typing.Optional[dict]:
    """
    Standalone wrapper that prioritizes the requested file but falls back 
    to iterating through ALL valid files in 'input_images' until one works.
    """
    config_manager = ConfigurationManager()
    if not config_manager.is_configured(): return None
    
    # Init dependencies (Pass API Key)
    content_preparer_factory = ContentPreparerFactory()
    api_client = GeminiApiClient(api_key=config_manager.api_key)
    response_processor = ResponseProcessor()
    extractor = ProviderExtractor(content_preparer_factory, api_client, response_processor)

    # --- BUILD CANDIDATE LIST ---
    candidates = []

    # 1. Check if direct path exists
    resolved_path = None
    if os.path.exists(file_path):
        resolved_path = file_path
    else:
        # Check relative to project root / input_images
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_script_dir)
        
        potential_path = os.path.join(project_root, file_path)
        if os.path.exists(potential_path):
            resolved_path = potential_path
        else:
            basename = os.path.basename(file_path)
            potential_path_2 = os.path.join(project_root, 'input_images', basename)
            if os.path.exists(potential_path_2):
                resolved_path = potential_path_2
    
    if resolved_path:
        candidates.append(resolved_path)
    else:
        print(f"Requested file '{file_path}' not found.")

    # 2. Add ALL other files in input_images as fallback
    resolver = FilePathResolver()
    all_files = resolver.get_all_input_files()
    if not all_files and not candidates:
        print("Error: No valid files found in input_images directory.")
        return None

    # Merge lists (keeping user request first)
    for f in all_files:
        if f not in candidates:
            candidates.append(f)

    # --- EXECUTE WITH ROBUST FALLBACK ---
    print(f"Found {len(candidates)} potential file(s) to process.")
    
    for i, candidate in enumerate(candidates):
        print(f"\n--- Attempt {i+1}/{len(candidates)}: {os.path.basename(candidate)} ---")
        result = extractor.extract_provider_from_file(candidate)
        
        if result:
            return result
        else:
            print(f"Failed to process {os.path.basename(candidate)}. Trying next candidate...")
            
    print("\n❌ All attempts failed. No usable document found.")
    return None


# ==============================================================================
# MAIN
# ==============================================================================
def main():
    app = DocumentExtractorApplication()
    app.run()

if __name__ == "__main__":
    main()