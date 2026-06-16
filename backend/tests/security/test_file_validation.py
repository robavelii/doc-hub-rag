from app.utils.file_validation import detect_file_type, sanitize_filename


def test_sanitize_filename_strips_path():
    assert sanitize_filename("../../etc/passwd") == "passwd"


def test_detect_pdf_magic():
    assert detect_file_type(b"%PDF-1.4 content", "text/plain") == "pdf"
