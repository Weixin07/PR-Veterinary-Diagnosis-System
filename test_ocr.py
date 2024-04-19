import pytest
from unittest.mock import Mock
import pytesseract
from app import process_pdf
from PIL import Image
import time


# Helper function to create fake image objects
def fake_image(text):
    image = Mock(spec=Image)
    pytesseract.image_to_string = Mock(return_value=text)
    return image


@pytest.mark.parametrize(
    "input_text, expected_output",
    [
        ("This is a simple PDF text.", "This is a simple PDF text."),
        ("First page text. Second page text.", "First page text. Second page text."),
    ],
)
def test_text_extraction_accuracy(mocker, input_text, expected_output):
    # Mocking convert_from_path to return an image with known text
    mocker.patch("app.convert_from_path", return_value=[fake_image(input_text)])
    assert process_pdf("fake_path.pdf") == expected_output


def test_multi_page_handling(mocker):
    # Mocking multi-page PDF processing
    texts = ["First page text.", "Second page text."]
    images = [fake_image(text) for text in texts]
    mocker.patch("app.convert_from_path", return_value=images)
    mocker.patch("pytesseract.image_to_string", side_effect=texts)
    expected_result = " ".join(texts)
    output = process_pdf("multi_page.pdf")
    assert output == expected_result, f"Expected '{expected_result}', got '{output}'"


def test_error_handling(mocker):
    mocker.patch("app.convert_from_path", side_effect=Exception("Failed to read PDF"))
    with pytest.raises(Exception) as excinfo:
        process_pdf("corrupted.pdf")
    assert "Failed to read PDF" in str(excinfo.value)


def test_performance(mocker):
    mocker.patch(
        "app.convert_from_path",
        return_value=[fake_image("Some lengthy text here" * 1000)],
    )
    start_time = time.time()
    process_pdf("large_text_dense.pdf")
    duration = time.time() - start_time
    assert duration < 1, "Processing took too long."


def test_ocr_accuracy_on_image_based_pdfs(mocker):
    input_text = "Extracted text from an image-based PDF."
    mocker.patch("app.convert_from_path", return_value=[fake_image(input_text)])
    assert process_pdf("image_based.pdf") == input_text


def test_non_text_content_handling(mocker):
    input_text = (
        "Non-text content like images and graphs should minimally affect output."
    )
    mocker.patch("app.convert_from_path", return_value=[fake_image(input_text)])
    assert process_pdf("nontext_content.pdf") == input_text
