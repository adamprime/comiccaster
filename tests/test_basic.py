def test_environment():
    """Basic test to verify test environment is working."""
    assert True

def test_sample_comics_list(sample_comics_list):
    """Test that our sample comics list fixture works."""
    import json
    with open(sample_comics_list) as f:
        comics = json.load(f)
    assert len(comics) == 2
    assert comics[0]["name"] == "Calvin and Hobbes"
    assert comics[1]["name"] == "Peanuts"

def test_directories(mock_feed_dir, mock_token_dir):
    """Test that our directory fixtures work."""
    import os
    assert os.path.exists(mock_feed_dir)
    assert os.path.exists(mock_token_dir)
    assert os.path.isdir(mock_feed_dir)
    assert os.path.isdir(mock_token_dir) 