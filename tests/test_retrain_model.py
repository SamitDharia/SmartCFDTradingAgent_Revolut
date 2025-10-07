import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import os
import shutil
from datetime import datetime, timedelta

# Add project root to allow imports
import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from scripts.retrain_model import main as retrain_main, backup_model

# Define paths used in tests
TEST_MODEL_DIR = Path("tests/test_models")
TEST_MODEL_PATH = TEST_MODEL_DIR / "model.joblib"
TEST_BACKUP_DIR = TEST_MODEL_DIR / "backup"

@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Manages the test model directory for each test."""
    # Setup: Ensure a clean state before each test
    if TEST_MODEL_DIR.exists():
        shutil.rmtree(TEST_MODEL_DIR)
    os.makedirs(TEST_MODEL_DIR)
    
    yield  # This is where the test runs
    
    # Teardown: Clean up after each test
    if TEST_MODEL_DIR.exists():
        shutil.rmtree(TEST_MODEL_DIR)

def create_dummy_model(path: Path):
    """Creates a dummy file to simulate a model."""
    with open(path, "w") as f:
        f.write("dummy model")

def test_backup_model_exists():
    """Test that an existing model is correctly backed up."""
    create_dummy_model(TEST_MODEL_PATH)
    
    backup_model(str(TEST_MODEL_PATH))
    
    assert not TEST_MODEL_PATH.exists()
    assert TEST_BACKUP_DIR.exists()
    
    backup_files = list(TEST_BACKUP_DIR.glob("model_*.joblib"))
    assert len(backup_files) == 1

def test_backup_model_does_not_exist():
    """Test that nothing happens if no model exists to back up."""
    backup_model(str(TEST_MODEL_PATH))
    assert not TEST_BACKUP_DIR.exists()

@patch('scripts.retrain_model.train_and_evaluate_model')
@patch('scripts.retrain_model.DEFAULT_MODEL_PATH', str(TEST_MODEL_PATH))
def test_retrain_main_flow(mock_train_and_evaluate):
    """
    Test the main retraining flow, ensuring backup and training are called.
    """
    # 1. Create a dummy model to be backed up
    create_dummy_model(TEST_MODEL_PATH)
    
    # 2. Run the main retraining script
    retrain_main()
    
    # 3. Assert that the backup was created
    assert TEST_BACKUP_DIR.exists()
    assert len(list(TEST_BACKUP_DIR.glob("*.joblib"))) == 1
    
    # 4. Assert that the training function was called
    mock_train_and_evaluate.assert_called_once()
    
    # 5. Check the date range passed to the training function
    args, kwargs = mock_train_and_evaluate.call_args
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * 2)
    
    assert 'start_date' in kwargs
    assert 'end_date' in kwargs
    
    # Check if the dates are approximately correct (within a small delta)
    passed_start_date = datetime.strptime(kwargs['start_date'], "%Y-%m-%d")
    passed_end_date = datetime.strptime(kwargs['end_date'], "%Y-%m-%d")
    
    assert abs((end_date - passed_end_date).days) <= 1
    assert abs((start_date - passed_start_date).days) <= 1

@patch('scripts.retrain_model.train_and_evaluate_model')
@patch('scripts.retrain_model.DEFAULT_MODEL_PATH', str(TEST_MODEL_PATH))
def test_retrain_main_no_existing_model(mock_train_and_evaluate):
    """
    Test that retraining is triggered even if no previous model exists.
    """
    # Ensure no model file exists
    assert not TEST_MODEL_PATH.exists()
    
    retrain_main()
    
    # Assert that no backup was attempted
    assert not TEST_BACKUP_DIR.exists()
    
    # Assert that training was still called
    mock_train_and_evaluate.assert_called_once()
