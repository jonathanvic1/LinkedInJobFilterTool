"""
Unit tests for linkedin_scraper.py
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def mock_load_cookies(self):
    """Helper to mock load_cookies and set csrf_token."""
    self.csrf_token = None


class TestLinkedInScraperInit:
    """Tests for LinkedInScraper initialization."""
    
    @patch('linkedin_scraper.db')
    @patch('linkedin_scraper.requests.Session')
    def test_init_with_defaults(self, mock_session, mock_db):
        """Test scraper initializes with default values."""
        from linkedin_scraper import LinkedInScraper
        
        with patch.object(LinkedInScraper, 'load_cookies', mock_load_cookies):
            scraper = LinkedInScraper(cookie_string="test_cookie=value")
            
            assert scraper.keywords == ''
            assert scraper.location == 'Canada'
            assert scraper.limit_jobs == 0
            assert scraper.easy_apply == False
            assert scraper.relevant == False
            assert scraper.time_filter == 'all'
    
    @patch('linkedin_scraper.db')
    @patch('linkedin_scraper.requests.Session')
    def test_dismiss_titles_lowercase(self, mock_session, mock_db):
        """Test that dismiss keywords are lowercased."""
        from linkedin_scraper import LinkedInScraper
        
        with patch.object(LinkedInScraper, 'load_cookies', mock_load_cookies):
            scraper = LinkedInScraper(
                dismiss_keywords=['SENIOR', 'Manager', 'DIRECTOR'],
                cookie_string="test=1"
            )
            
            assert 'senior' in scraper.dismiss_titles
            assert 'manager' in scraper.dismiss_titles
            assert 'director' in scraper.dismiss_titles
    
    @patch('linkedin_scraper.db')
    @patch('linkedin_scraper.requests.Session')
    def test_company_url_extraction(self, mock_session, mock_db):
        """Test that company URLs are properly extracted to slugs."""
        from linkedin_scraper import LinkedInScraper
        
        with patch.object(LinkedInScraper, 'load_cookies', mock_load_cookies):
            scraper = LinkedInScraper(
                dismiss_companies=[
                    'https://www.linkedin.com/company/google/',
                    'https://linkedin.com/company/meta?ref=123',
                    'amazon'
                ],
                cookie_string="test=1"
            )
            
            assert 'google' in scraper.dismiss_companies
            assert 'meta' in scraper.dismiss_companies
            assert 'amazon' in scraper.dismiss_companies


class TestDismissJob:
    """Tests for dismiss_job method."""
    
    @patch('linkedin_scraper.db')
    @patch('linkedin_scraper.requests.Session')
    def test_dismiss_job_success(self, mock_session, mock_db):
        """Test successful job dismissal returns job data."""
        from linkedin_scraper import LinkedInScraper
        
        # Setup mock session
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session_instance = Mock()
        mock_session_instance.post.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        with patch.object(LinkedInScraper, 'load_cookies', mock_load_cookies):
            scraper = LinkedInScraper(cookie_string="test=1", user_id="test_user")
            scraper.session = mock_session_instance
            
            result = scraper.dismiss_job(
                job_id="123",
                title="Software Engineer",
                company="Test Corp",
                location="Toronto",
                reason="job_title"
            )
            
            assert result is not None
            assert result['job_id'] == "123"
            assert result['title'] == "Software Engineer"
            assert result['user_id'] == "test_user"
    
    @patch('linkedin_scraper.db')
    @patch('linkedin_scraper.requests.Session')
    def test_dismiss_job_failure(self, mock_session, mock_db):
        """Test failed job dismissal returns None."""
        from linkedin_scraper import LinkedInScraper
        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_session_instance = Mock()
        mock_session_instance.post.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        with patch.object(LinkedInScraper, 'load_cookies', mock_load_cookies):
            scraper = LinkedInScraper(cookie_string="test=1")
            scraper.session = mock_session_instance
            
            result = scraper.dismiss_job(
                job_id="123",
                title="Test Job",
                company="Test Corp",
                location="Toronto"
            )
            
            assert result is None


class TestProcessPageResult:
    """Tests for process_page_result method."""
    
    @patch('linkedin_scraper.db')
    @patch('linkedin_scraper.requests.Session')
    def test_empty_page_returns_zeros(self, mock_session, mock_db):
        """Test that empty page returns zero stats and empty list."""
        from linkedin_scraper import LinkedInScraper
        
        with patch.object(LinkedInScraper, 'load_cookies', mock_load_cookies):
            scraper = LinkedInScraper(cookie_string="test=1")
            
            stats, dismissed = scraper.process_page_result([])
            
            assert stats == (0, 0, 0, 0, 0, 0, 0, 0, 0)
            assert dismissed == []
    
    @patch('linkedin_scraper.db')
    @patch('linkedin_scraper.requests.Session')
    def test_skips_already_dismissed(self, mock_session, mock_db):
        """Test that already dismissed jobs are skipped."""
        from linkedin_scraper import LinkedInScraper
        
        # Mock db to return job as already dismissed
        mock_db.get_dismissed_job_ids.return_value = {'123'}
        
        with patch.object(LinkedInScraper, 'load_cookies', mock_load_cookies):
            scraper = LinkedInScraper(cookie_string="test=1")
            
            page_jobs = [
                {'job_id': '123', 'title': 'Test Job', 'company': 'Test Corp'}
            ]
            
            stats, dismissed = scraper.process_page_result(page_jobs)
            
            # Should have processed 1, skipped 1, dismissed 0
            assert stats[0] == 1  # processed
            assert stats[2] == 1  # skipped
            assert stats[1] == 0  # dismissed
    
    @patch('linkedin_scraper.db')
    @patch('linkedin_scraper.requests.Session')
    def test_matches_title_blocklist(self, mock_session, mock_db):
        """Test that jobs matching title blocklist are dismissed."""
        from linkedin_scraper import LinkedInScraper
        
        mock_db.get_dismissed_job_ids.return_value = set()
        
        # Mock successful dismiss
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session_instance = Mock()
        mock_session_instance.post.return_value = mock_response
        
        with patch.object(LinkedInScraper, 'load_cookies', mock_load_cookies):
            scraper = LinkedInScraper(
                dismiss_keywords=['senior'],
                cookie_string="test=1",
                job_delay=0
            )
            scraper.session = mock_session_instance
            
            page_jobs = [
                {'job_id': '456', 'title': 'Senior Engineer', 'company': 'Test Corp'}
            ]
            
            stats, dismissed = scraper.process_page_result(page_jobs)
            
            assert stats[1] == 1  # dismissed count
            assert len(dismissed) == 1
            assert dismissed[0]['job_id'] == '456'


class TestTimeRangeFilter:
    """Tests for time range filter conversion."""
    
    @patch('linkedin_scraper.db')
    @patch('linkedin_scraper.requests.Session')
    def test_time_filter_values(self, mock_session, mock_db):
        """Test that time filters are correctly stored."""
        from linkedin_scraper import LinkedInScraper
        
        time_mappings = {
            '30m': 'r1800',
            '1h': 'r3600',
            '8h': 'r28800',
            '24h': 'r86400',
            '2d': 'r172800',
            '3d': 'r259200',
            'week': 'r604800',
            'month': 'r2592000',
        }
        
        for time_filter, expected_range in time_mappings.items():
            with patch.object(LinkedInScraper, 'load_cookies', mock_load_cookies):
                scraper = LinkedInScraper(
                    time_filter=time_filter,
                    cookie_string="test=1"
                )
                
                # Verify the filter is stored correctly
                assert scraper.time_filter == time_filter


class TestFetchPage:
    """Tests for fetch_page method."""
    
    @patch('linkedin_scraper.db')
    @patch('linkedin_scraper.requests.Session')
    def test_retry_on_500_error(self, mock_session, mock_db):
        """Test that 500 errors trigger retry logic."""
        from linkedin_scraper import LinkedInScraper
        
        # Setup: first call returns 500, second returns 200
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {
            'data': {'elements': [], 'paging': {'total': 0}},
            'included': []
        }
        
        mock_session_instance = Mock()
        mock_session_instance.get.side_effect = [mock_response_500, mock_response_200]
        
        with patch.object(LinkedInScraper, 'load_cookies', mock_load_cookies):
            with patch('linkedin_scraper.sleep'):  # Skip actual sleep
                scraper = LinkedInScraper(cookie_string="test=1")
                scraper.session = mock_session_instance
                
                jobs, total = scraper.fetch_page(0)
                
                # Should have retried and succeeded
                assert mock_session_instance.get.call_count == 2
    
    @patch('linkedin_scraper.db')
    @patch('linkedin_scraper.requests.Session')
    def test_returns_empty_after_max_retries(self, mock_session, mock_db):
        """Test that max retries returns empty list."""
        from linkedin_scraper import LinkedInScraper
        
        mock_response = Mock()
        mock_response.status_code = 500
        
        mock_session_instance = Mock()
        mock_session_instance.get.return_value = mock_response
        
        with patch.object(LinkedInScraper, 'load_cookies', mock_load_cookies):
            with patch('linkedin_scraper.sleep'):
                scraper = LinkedInScraper(cookie_string="test=1")
                scraper.session = mock_session_instance
                
                jobs, total = scraper.fetch_page(0)
                
                assert jobs == []
                assert total == 0
                assert mock_session_instance.get.call_count == 3  # 3 retries
