"""
Test suite for Phase 1: OCR System Removal

Following TDD principles - these tests validate that:
1. OCR module can be safely removed
2. processor.py works without OCR calls
3. llm_extractor.py works without ocr_results parameter
4. Dependencies are properly cleaned up
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add Scraping_code directory to path for relative imports
sys.path.insert(0, str(Path(__file__).parent.parent / "Scraping_code"))


class TestOCRRemoval:
    """Tests ensuring OCR removal doesn't break functionality."""

    def test_processor_imports_without_ocr(self):
        """Test that processor.py can import without ocr module."""
        # This will fail initially (RED) because ocr is still imported
        with patch.dict('sys.modules', {'ocr': None}):
            try:
                # Try importing without ocr module available
                import importlib
                if 'processor' in sys.modules:
                    del sys.modules['processor']

                # This should eventually succeed after refactoring
                import processor
                assert processor is not None
            except ImportError as e:
                # Expected to fail before refactoring
                pytest.fail(f"processor.py should not depend on ocr module: {e}")

    def test_llm_extractor_works_without_ocr_results(self):
        """Test that extract_company_seeds works without ocr_results parameter."""
        from llm_extractor import extract_company_seeds

        # Mock OpenAI client
        with patch('llm_extractor.client') as mock_client:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = '[]'
            mock_client.chat.completions.create.return_value = mock_response

            # Call without ocr_results (should work after refactoring)
            result = extract_company_seeds(
                source_url="https://example.com",
                investor_name="Test Fund",
                page_text="Test content",
                anchors=[],
                blocks=[],
                dom_chunks=[],
                embedded_json=[]
            )

            # Should return empty list without crashing
            assert isinstance(result, list)

    def test_processor_process_portfolio_without_ocr(self):
        """Test that process_portfolio_url works without OCR processing."""
        from processor import process_portfolio_url

        # Mock all external dependencies
        with patch('processor.crawl_portfolio_page') as mock_crawl, \
             patch('processor.extract_company_seeds') as mock_extract, \
             patch('processor.crawl_domain') as mock_domain, \
             patch('processor.insert_portfolio_row') as mock_insert:

            # Setup mocks
            mock_crawl.return_value = (
                "test text",  # page_text
                [],           # logo_urls (not used after OCR removal)
                [],           # anchors
                [],           # blocks
                [],           # dom_chunks
                [],           # embedded_json
                set()         # dom_filter_keywords
            )

            mock_extract.return_value = []
            mock_domain.return_value = {}

            # Call should work without OCR processing
            result = process_portfolio_url(
                source_url="https://example.com/portfolio",
                investor_name="Test Investor"
            )

            # Verify OCR was not called (will pass after refactoring)
            # Should not raise any OCR-related errors
            assert isinstance(result, bool)

    def test_requirements_without_ocr_dependencies(self):
        """Test that requirements.txt doesn't include OCR dependencies."""
        requirements_path = Path(__file__).parent.parent / "Scraping_code" / "requirements.txt"

        if requirements_path.exists():
            content = requirements_path.read_text()

            # After refactoring, these should not be present
            assert "easyocr" not in content, "easyocr should be removed from requirements"
            assert "opencv-python-headless" not in content, "opencv should be removed from requirements"

    def test_ocr_module_not_imported(self):
        """Test that ocr module is not imported anywhere."""
        import processor

        # Check processor module doesn't import ocr
        processor_file = Path(__file__).parent.parent / "Scraping_code" / "processor.py"
        content = processor_file.read_text()

        # After refactoring, ocr import should be removed
        assert "from ocr import" not in content, "processor.py should not import ocr"
        assert "run_logo_ocr" not in content, "processor.py should not call run_logo_ocr"


class TestLLMExtractorRefactoring:
    """Tests for llm_extractor.py refactoring."""

    def test_extract_company_seeds_signature_no_ocr(self):
        """Test that extract_company_seeds doesn't require ocr_results."""
        from llm_extractor import extract_company_seeds
        import inspect

        # Get function signature
        sig = inspect.signature(extract_company_seeds)
        params = sig.parameters

        # After refactoring, ocr_results should be removed or optional
        if 'ocr_results' in params:
            # Should be optional with default value
            param = params['ocr_results']
            assert param.default != inspect.Parameter.empty, \
                "ocr_results should have a default value or be removed"

    def test_llm_prompt_without_ocr_mention(self):
        """Test that LLM prompts don't mention OCR or logos."""
        llm_file = Path(__file__).parent.parent / "Scraping_code" / "llm_extractor.py"
        content = llm_file.read_text()

        # Check system prompt in extract_company_seeds
        # After refactoring, OCR-related text should be removed
        lines = content.split('\n')
        in_system_prompt = False
        prompt_lines = []

        for line in lines:
            if 'system_prompt =' in line:
                in_system_prompt = True
            if in_system_prompt:
                prompt_lines.append(line)
            if in_system_prompt and line.strip().endswith(')'):
                break

        prompt_text = '\n'.join(prompt_lines)

        # After refactoring, these should not appear
        assert "Logos may represent companies" not in prompt_text, \
            "OCR logo reference should be removed from prompt"


class TestProcessorRefactoring:
    """Tests for processor.py refactoring."""

    def test_no_ocr_results_variable(self):
        """Test that processor.py doesn't create ocr_results variable."""
        processor_file = Path(__file__).parent.parent / "Scraping_code" / "processor.py"
        content = processor_file.read_text()

        # After refactoring, ocr_results variable should not exist
        assert "ocr_results = []" not in content, \
            "ocr_results variable should be removed"
        assert "run_logo_ocr(" not in content, \
            "run_logo_ocr function call should be removed"

    def test_extract_company_seeds_called_without_ocr(self):
        """Test that extract_company_seeds is called without ocr_results."""
        processor_file = Path(__file__).parent.parent / "Scraping_code" / "processor.py"
        content = processor_file.read_text()

        # Find the extract_company_seeds call
        lines = content.split('\n')
        call_found = False

        for i, line in enumerate(lines):
            if 'extract_company_seeds(' in line:
                call_found = True
                # Check next few lines for ocr_results parameter
                call_block = '\n'.join(lines[i:i+10])

                # After refactoring, ocr_results should not be passed
                assert 'ocr_results=' not in call_block, \
                    "ocr_results parameter should not be passed to extract_company_seeds"
                break

        if not call_found:
            pytest.skip("extract_company_seeds call not found in expected format")


class TestIntegrationAfterOCRRemoval:
    """Integration tests ensuring system works without OCR."""

    def test_full_pipeline_without_ocr(self):
        """Test that full pipeline works without OCR system."""
        # Mock all external dependencies
        with patch('processor.crawl_portfolio_page') as mock_crawl, \
             patch('processor.extract_company_seeds') as mock_extract, \
             patch('processor.crawl_domain') as mock_domain, \
             patch('processor.find_official_company_website') as mock_google, \
             patch('processor.insert_portfolio_row') as mock_insert, \
             patch('processor.fuse_deep_profile') as mock_fuse, \
             patch('processor.select_company_docs') as mock_select:

            from processor import process_portfolio_url
            from schema import CompanySeed, PortfolioCsvRow

            # Setup mocks
            mock_crawl.return_value = (
                "Acme Corp is a leading software company",
                [],  # logo_urls
                [{"text": "Acme Corp", "href": "https://acme.com"}],
                ["Acme Corp"],
                [],
                [],
                set()
            )

            mock_extract.return_value = [
                CompanySeed(
                    source_url="https://fund.com/portfolio",
                    investor_name="Test Fund",
                    company_name="Acme Corp",
                    company_website="https://acme.com"
                )
            ]

            mock_domain.return_value = {}
            mock_select.return_value = []

            mock_fuse.return_value = PortfolioCsvRow(
                source_url="https://fund.com/portfolio",
                investor_name="Test Fund",
                company_name="Acme Corp",
                company_website="https://acme.com"
            )

            # Execute pipeline
            result = process_portfolio_url(
                source_url="https://fund.com/portfolio",
                investor_name="Test Fund"
            )

            # Should complete successfully
            assert result is True
            assert mock_extract.called
            assert mock_insert.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
