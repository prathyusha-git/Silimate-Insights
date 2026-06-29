# silimatespecvalidator/specvalidator/testing/__init__.py

"""
Testing Infrastructure for SpecValidator

Provides test generation, regression management, and coverage analysis.
"""

from .regression_store import append_failure, load_failures
from .golden_store import GoldenStore
from .seed_manager import SeedManager

__all__ = [
    # Regression store
    'append_failure',
    'load_failures',
    
    # Golden references
    'GoldenStore',
    
    # Seed management
    'SeedManager',
]

# Testing utilities
def create_test_environment():
    """Create a complete test environment"""
    from pathlib import Path
    import tempfile
    
    temp_dir = Path(tempfile.mkdtemp())
    
    return {
        'golden': GoldenStore(temp_dir / 'golden'),
        'seeds': SeedManager(),
        'regression_path': temp_dir / 'regressions',
        'workspace': temp_dir
    }

def cleanup_test_environment(env):
    """Clean up test environment"""
    import shutil
    if 'workspace' in env:
        shutil.rmtree(env['workspace'], ignore_errors=True)