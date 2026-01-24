"""
Unit tests for database.py
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDatabaseSingleton:
    """Tests for Database singleton pattern."""
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_singleton_returns_same_instance(self, mock_create_client):
        """Test that Database() always returns the same instance."""
        # Reset singleton for test
        import database
        database.Database._instance = None
        
        db1 = database.Database()
        db2 = database.Database()
        
        assert db1 is db2
    
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_env_vars_sets_client_none(self):
        """Test that missing env vars result in client=None."""
        import database
        database.Database._instance = None
        
        # Remove env vars
        os.environ.pop('SUPABASE_URL', None)
        os.environ.pop('SUPABASE_KEY', None)
        os.environ.pop('SUPABASE_SERVICE_ROLE_KEY', None)
        
        db = database.Database()
        
        assert db.client is None


class TestIsJobDismissed:
    """Tests for is_job_dismissed method."""
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_returns_true_when_job_exists(self, mock_create_client):
        """Test returns True when job is in database."""
        import database
        database.Database._instance = None
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [{'job_id': '123'}]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        mock_create_client.return_value = mock_client
        
        db = database.Database()
        
        result = db.is_job_dismissed('123')
        
        assert result is True
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_returns_false_when_job_not_exists(self, mock_create_client):
        """Test returns False when job is not in database."""
        import database
        database.Database._instance = None
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        mock_create_client.return_value = mock_client
        
        db = database.Database()
        
        result = db.is_job_dismissed('999')
        
        assert result is False
    
    def test_returns_false_when_no_client(self):
        """Test returns False when client is None."""
        import database
        database.Database._instance = None
        
        # Create instance without env vars
        os.environ.pop('SUPABASE_URL', None)
        os.environ.pop('SUPABASE_KEY', None)
        
        db = database.Database()
        db.client = None
        
        result = db.is_job_dismissed('123')
        
        assert result is False


class TestGetDismissedJobIds:
    """Tests for batch get_dismissed_job_ids method."""
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_returns_set_of_dismissed_ids(self, mock_create_client):
        """Test returns set of dismissed job IDs."""
        import database
        database.Database._instance = None
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [{'job_id': '123'}, {'job_id': '456'}]
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = mock_response
        mock_create_client.return_value = mock_client
        
        db = database.Database()
        
        result = db.get_dismissed_job_ids(['123', '456', '789'])
        
        assert result == {'123', '456'}
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_returns_empty_set_for_empty_input(self, mock_create_client):
        """Test returns empty set for empty input list."""
        import database
        database.Database._instance = None
        
        mock_create_client.return_value = Mock()
        db = database.Database()
        
        result = db.get_dismissed_job_ids([])
        
        assert result == set()


class TestBatchSaveDismissedJobs:
    """Tests for batch_save_dismissed_jobs method."""
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_batch_upserts_jobs(self, mock_create_client):
        """Test batch upsert is called with correct data."""
        import database
        database.Database._instance = None
        
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        db = database.Database()
        
        jobs_data = [
            {'job_id': '123', 'title': 'Job 1'},
            {'job_id': '456', 'title': 'Job 2'}
        ]
        
        db.batch_save_dismissed_jobs(jobs_data)
        
        mock_client.table.return_value.upsert.assert_called_once_with(jobs_data)
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_filters_out_none_values(self, mock_create_client):
        """Test that None values are filtered out."""
        import database
        database.Database._instance = None
        
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        db = database.Database()
        
        jobs_data = [
            {'job_id': '123', 'title': 'Job 1'},
            None,
            {'job_id': '456', 'title': 'Job 2'},
            {}  # No job_id, should be filtered
        ]
        
        db.batch_save_dismissed_jobs(jobs_data)
        
        # Should only include the 2 valid jobs
        call_args = mock_client.table.return_value.upsert.call_args[0][0]
        assert len(call_args) == 2
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_does_nothing_for_empty_list(self, mock_create_client):
        """Test that empty list does not call upsert."""
        import database
        database.Database._instance = None
        
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        db = database.Database()
        
        db.batch_save_dismissed_jobs([])
        
        mock_client.table.return_value.upsert.assert_not_called()


class TestGetBlocklist:
    """Tests for get_blocklist method."""
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_returns_list_of_items(self, mock_create_client):
        """Test returns list of blocklist items."""
        import database
        database.Database._instance = None
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [{'item': 'senior'}, {'item': 'manager'}]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        mock_create_client.return_value = mock_client
        
        db = database.Database()
        
        result = db.get_blocklist('job_title')
        
        assert result == ['senior', 'manager']
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_filters_by_user_id(self, mock_create_client):
        """Test filters by user_id when provided."""
        import database
        database.Database._instance = None
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = []
        
        # Setup chain
        select_mock = Mock()
        eq_blocklist_mock = Mock()
        eq_user_mock = Mock()
        
        mock_client.table.return_value.select.return_value = select_mock
        select_mock.eq.return_value = eq_blocklist_mock
        eq_blocklist_mock.eq.return_value = eq_user_mock
        eq_user_mock.execute.return_value = mock_response
        
        mock_create_client.return_value = mock_client
        
        db = database.Database()
        
        db.get_blocklist('job_title', user_id='user123')
        
        # Verify user_id filter was applied
        eq_blocklist_mock.eq.assert_called_with('user_id', 'user123')


class TestGetEarliestDuplicate:
    """Tests for get_earliest_duplicate method."""
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_returns_earliest_job_id(self, mock_create_client):
        """Test returns the earliest job_id for duplicates."""
        import database
        database.Database._instance = None
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [{'job_id': '100'}]  # Earliest
        
        # Build the chain
        table_mock = Mock()
        select_mock = Mock()
        eq_title_mock = Mock()
        eq_company_mock = Mock()
        order_mock = Mock()
        limit_mock = Mock()
        
        mock_client.table.return_value = table_mock
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_title_mock
        eq_title_mock.eq.return_value = eq_company_mock
        eq_company_mock.order.return_value = order_mock
        order_mock.limit.return_value = limit_mock
        limit_mock.execute.return_value = mock_response
        
        mock_create_client.return_value = mock_client
        
        db = database.Database()
        
        result = db.get_earliest_duplicate('Software Engineer', 'Test Corp')
        
        assert result == '100'
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'https://test.supabase.co', 'SUPABASE_KEY': 'test_key'})
    @patch('database.create_client')
    def test_returns_none_when_no_duplicate(self, mock_create_client):
        """Test returns None when no duplicate found."""
        import database
        database.Database._instance = None
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = []
        
        # Build the chain  
        table_mock = Mock()
        select_mock = Mock()
        eq_title_mock = Mock()
        eq_company_mock = Mock()
        order_mock = Mock()
        limit_mock = Mock()
        
        mock_client.table.return_value = table_mock
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_title_mock
        eq_title_mock.eq.return_value = eq_company_mock
        eq_company_mock.order.return_value = order_mock
        order_mock.limit.return_value = limit_mock
        limit_mock.execute.return_value = mock_response
        
        mock_create_client.return_value = mock_client
        
        db = database.Database()
        
        result = db.get_earliest_duplicate('Unique Job', 'Unique Corp')
        
        assert result is None
