"""
KOS Core Components

This package contains the core components of the KOS operating system,
including hardware abstraction, process management, memory management,
and filesystem operations.
"""

import logging
import importlib
import sys
import os
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('KOS.core')

# Core components initialization status
_core_state = {
    'initialized': False,
    'components': {
        'boot': False,
        'kernel': False,
        'hal': False,
        'process': False,
        'memory': False,
        'filesystem': False,
        'syscall': False
    }
}

def initialize_core(config=None):
    """
    Initialize KOS core components
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Success status
    """
    global _core_state
    
    if _core_state['initialized']:
        logger.warning("KOS core already initialized")
        return True
    
    logger.info("Initializing KOS core components")
    
    config = config or {}
    
    # Import and initialize core components in dependency order
    try:
        # 1. Initialize kernel (central component)
        from .kernel import initialize as init_kernel
        kernel_result = init_kernel()
        _core_state['components']['kernel'] = kernel_result
        logger.info(f"Kernel initialization: {'Success' if kernel_result else 'Failed'}")
        
        # 2. Initialize hardware abstraction layer
        from .hal import initialize as init_hal
        hal_result = init_hal()
        _core_state['components']['hal'] = hal_result
        logger.info(f"HAL initialization: {'Success' if hal_result else 'Failed'}")
        
        # 3. Initialize memory management
        from .memory import initialize as init_memory
        memory_result = init_memory()
        _core_state['components']['memory'] = memory_result
        logger.info(f"Memory initialization: {'Success' if memory_result else 'Failed'}")
        
        # 4. Initialize filesystem
        from .filesystem import initialize as init_filesystem
        filesystem_result = init_filesystem()
        _core_state['components']['filesystem'] = filesystem_result
        logger.info(f"Filesystem initialization: {'Success' if filesystem_result else 'Failed'}")
        
        # 5. Initialize process management
        from .process import initialize as init_process
        process_result = init_process()
        _core_state['components']['process'] = process_result
        logger.info(f"Process initialization: {'Success' if process_result else 'Failed'}")
        
        # 6. Initialize system call interface
        from .syscall import initialize as init_syscall
        syscall_result = init_syscall()
        _core_state['components']['syscall'] = syscall_result
        logger.info(f"Syscall initialization: {'Success' if syscall_result else 'Failed'}")
        
        # Mark core as initialized if all components initialized successfully
        if all(_core_state['components'].values()):
            _core_state['initialized'] = True
            logger.info("KOS core initialization complete")
            return True
        else:
            failed = [comp for comp, status in _core_state['components'].items() if not status]
            logger.error(f"KOS core initialization failed. Failed components: {', '.join(failed)}")
            return False
    
    except Exception as e:
        logger.error(f"Error initializing KOS core: {e}")
        return False


def get_core_status():
    """
    Get status of core components
    
    Returns:
        Dictionary of component status
    """
    return {
        'initialized': _core_state['initialized'],
        'components': dict(_core_state['components'])
    }


def shutdown_core():
    """
    Shutdown KOS core components
    
    Returns:
        Success status
    """
    global _core_state
    
    if not _core_state['initialized']:
        logger.warning("KOS core not initialized")
        return True
    
    logger.info("Shutting down KOS core components")
    
    # Shutdown components in reverse order of initialization
    try:
        # 1. Shutdown system call interface
        if _core_state['components']['syscall']:
            from .syscall import shutdown as shutdown_syscall
            shutdown_syscall()
        
        # 2. Shutdown process management
        if _core_state['components']['process']:
            from .process import stop_scheduler
            stop_scheduler()
        
        # 3. Shutdown filesystem
        # (No explicit shutdown needed as it's handled by mount/unmount)
        
        # 4. Shutdown memory management
        # (No explicit shutdown needed)
        
        # 5. Shutdown hardware abstraction layer
        # (No explicit shutdown needed)
        
        # 6. Shutdown kernel
        if _core_state['components']['kernel']:
            from .kernel import shutdown as shutdown_kernel
            shutdown_kernel()
        
        # Reset core state
        for component in _core_state['components']:
            _core_state['components'][component] = False
        
        _core_state['initialized'] = False
        
        logger.info("KOS core shutdown complete")
        return True
    
    except Exception as e:
        logger.error(f"Error shutting down KOS core: {e}")
        return False
