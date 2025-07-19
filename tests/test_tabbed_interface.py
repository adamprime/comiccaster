"""
Test suite for Epic 3 - Frontend UI Implementation.
Tests the tabbed interface functionality for separating daily comics from political cartoons.
"""

import pytest
import json
import os
from pathlib import Path

class TestTabbedInterface:
    """Test cases for the tabbed interface implementation."""
    
    @pytest.fixture
    def project_root(self):
        """Get the project root directory."""
        return Path(__file__).parent.parent
    
    @pytest.fixture
    def index_html_content(self, project_root):
        """Load the index.html content."""
        index_path = project_root / 'public' / 'index.html'
        with open(index_path, 'r') as f:
            return f.read()
    
    @pytest.fixture
    def political_comics_data(self, project_root):
        """Load political comics data."""
        data_path = project_root / 'public' / 'political_comics_list.json'
        with open(data_path, 'r') as f:
            return json.load(f)
    
    @pytest.fixture
    def opml_function_content(self, project_root):
        """Load the generate-opml.js content."""
        opml_path = project_root / 'functions' / 'generate-opml.js'
        with open(opml_path, 'r') as f:
            return f.read()
    
    def test_political_comics_list_exists(self, project_root):
        """Test that political_comics_list.json exists in public directory."""
        file_path = project_root / 'public' / 'political_comics_list.json'
        assert file_path.exists(), "political_comics_list.json should exist in public directory"
    
    def test_political_comics_data_structure(self, political_comics_data):
        """Test that political comics data has correct structure."""
        assert len(political_comics_data) > 0, "Political comics list should not be empty"
        
        # Check first comic has required fields
        first_comic = political_comics_data[0]
        required_fields = ['name', 'slug', 'url', 'is_political']
        for field in required_fields:
            assert field in first_comic, f"Political comic should have '{field}' field"
        
        assert first_comic['is_political'] is True, "Political comics should have is_political=true"
    
    def test_html_tab_structure(self, index_html_content):
        """Test that HTML contains proper tab structure."""
        # Check for tab buttons
        assert 'data-tab="daily"' in index_html_content, "Should have daily comics tab"
        assert 'data-tab="political"' in index_html_content, "Should have political comics tab"
        assert 'data-tab="daily-opml"' in index_html_content, "Should have daily OPML tab"
        assert 'data-tab="political-opml"' in index_html_content, "Should have political OPML tab"
        
        # Check for tab content divs
        assert 'id="daily-tab"' in index_html_content, "Should have daily tab content"
        assert 'id="political-tab"' in index_html_content, "Should have political tab content"
        assert 'id="daily-opml-tab"' in index_html_content, "Should have daily OPML tab content"
        assert 'id="political-opml-tab"' in index_html_content, "Should have political OPML tab content"
    
    def test_css_tab_styling(self, index_html_content):
        """Test that CSS includes tab styling."""
        assert '.tabs {' in index_html_content, "Should have tabs container styling"
        assert '.tab-button {' in index_html_content, "Should have tab button styling"
        assert '.tab-button.active {' in index_html_content, "Should have active tab styling"
        assert '.tab-content {' in index_html_content, "Should have tab content styling"
        assert '.tab-content.active {' in index_html_content, "Should have active tab content styling"
    
    def test_javascript_tab_functionality(self, index_html_content):
        """Test that JavaScript includes tab switching functionality."""
        assert 'setupTabSwitching()' in index_html_content, "Should have tab switching setup function"
        assert "fetch('/political_comics_list.json')" in index_html_content, "Should fetch political comics"
        assert 'populateComicsTable(politicalComics' in index_html_content, "Should populate political table"
        assert 'generatePoliticalOPMLBtn' in index_html_content, "Should have political OPML button"
    
    def test_separate_search_inputs(self, index_html_content):
        """Test that each tab has its own search input."""
        assert 'id="comicSearch"' in index_html_content, "Should have daily comic search"
        assert 'id="politicalComicSearch"' in index_html_content, "Should have political comic search"
        assert 'id="customFeedSearch"' in index_html_content, "Should have daily feed search"
        assert 'id="politicalFeedSearch"' in index_html_content, "Should have political feed search"
    
    def test_separate_tables(self, index_html_content):
        """Test that browse section has separate tables for each comic type."""
        assert 'id="comics-table-body"' in index_html_content, "Should have daily comics table"
        assert 'id="political-comics-table-body"' in index_html_content, "Should have political comics table"
    
    def test_separate_comic_lists(self, index_html_content):
        """Test that OPML section has separate lists for each comic type."""
        assert 'id="comics-list"' in index_html_content, "Should have daily comics list"
        assert 'id="political-comics-list"' in index_html_content, "Should have political comics list"
    
    def test_opml_type_parameter(self, index_html_content):
        """Test that OPML generation includes type parameter."""
        assert "type: 'daily'" in index_html_content, "Should send type='daily' for daily comics"
        assert "type: 'political'" in index_html_content, "Should send type='political' for political comics"
    
    def test_opml_filenames(self, index_html_content):
        """Test that OPML files have type-specific names."""
        assert 'daily-comics.opml' in index_html_content, "Should use daily-comics.opml filename"
        assert 'political-cartoons.opml' in index_html_content, "Should use political-cartoons.opml filename"
    
    def test_opml_function_type_handling(self, opml_function_content):
        """Test that generate-opml.js handles type parameter."""
        assert "type = body.type || 'daily'" in opml_function_content, "Should extract type from request"
        assert "loadComicsList(type)" in opml_function_content, "Should load comics based on type"
        assert "type === 'political'" in opml_function_content, "Should handle political type"
        assert 'political-cartoons.opml' in opml_function_content, "Should use political filename"
        assert 'daily-comics.opml' in opml_function_content, "Should use daily filename"
    
    def test_opml_function_loads_political_list(self, opml_function_content):
        """Test that generate-opml.js can load political_comics_list.json."""
        assert 'political_comics_list.json' in opml_function_content, "Should reference political comics file"
        assert "filename = type === 'political'" in opml_function_content, "Should select file by type"
    
    def test_tab_button_icons(self, index_html_content):
        """Test that tab buttons have appropriate icons."""
        assert '📰 Daily Comics' in index_html_content, "Daily comics tab should have newspaper icon"
        assert '🏛️ Political Cartoons' in index_html_content, "Political tab should have building icon"
    
    def test_placeholder_text(self, index_html_content):
        """Test that search inputs have appropriate placeholder text."""
        assert 'placeholder="Search daily comics' in index_html_content, "Daily search should specify type"
        assert 'placeholder="Search political cartoons' in index_html_content, "Political search should specify type"