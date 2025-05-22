"""
Custom shell loop implementation for KOS to prevent unwanted exits
"""
import sys
import traceback
import logging
from typing import Any, Optional

# Set up logger
logger = logging.getLogger('KOS.shell_loop')

class ShellLoop:
    """Custom shell loop implementation to prevent unwanted exits"""
    
    def __init__(self, shell, debug=False):
        """
        Initialize the shell loop
        
        Args:
            shell: The shell instance to run
            debug: If True, enable debug logging
        """
        self.shell = shell
        self.running = True
        self.debug = debug
        
    def _debug_log(self, message, *args, **kwargs):
        """Log a debug message if debug mode is enabled"""
        if self.debug:
            logger.debug(message, *args, **kwargs)
            
    def run(self):
        """Run the main shell loop"""
        self._debug_log("Starting shell loop")
        self.shell.preloop()
        self._debug_log("After preloop")
        
        try:
            self._debug_log("Entering main shell loop")
            while self.running:
                try:
                    self._debug_log("Starting new command cycle")
                    
                    # Get command input
                    if self.shell.cmdqueue:
                        line = self.shell.cmdqueue.pop(0)
                        self._debug_log("Got command from queue: %s", line)
                    else:
                        if self.shell.use_rawinput:
                            try:
                                self._debug_log("Waiting for user input")
                                line = input(self.shell.prompt)
                                self._debug_log("User input: %s", line)
                                if not line.strip():
                                    self._debug_log("Empty input, skipping")
                                    continue
                            except (EOFError, KeyboardInterrupt):
                                self._debug_log("Caught KeyboardInterrupt or EOF")
                                line = 'EOF'
                        else:
                            # Not using raw input, read from stdin
                            self._debug_log("Reading from stdin (non-interactive mode)")
                            line = sys.stdin.readline()
                            if not line:
                                line = 'EOF'
                            else:
                                line = line.rstrip('\r\n')
                                self._debug_log("Read line from stdin: %s", line)
                    
                    # Process the command
                    self._debug_log("Processing command: %s", line)
                    try:
                        # Handle special commands first
                        if line.strip() in ('exit', 'quit'):
                            self._debug_log("Exit command detected")
                            self.running = False
                            break
                            
                        line = self.shell.precmd(line)
                        self._debug_log("After precmd: %s", line)
                        
                        # Run the command
                        _ = self.shell.onecmd(line)
                        self._debug_log("Command executed")
                        
                        # Process post-command but ignore stop flag for normal commands
                        _ = self.shell.postcmd(False, line)
                        self._debug_log("Command completed")
                        
                    except Exception as e:
                        logger.error(f"Error processing command: {e}", exc_info=True)
                        print(f"Error: {e}")
                    
                    self._debug_log("Starting new command cycle")
                    
                except KeyboardInterrupt:
                    self._debug_log("KeyboardInterrupt in command loop")
                    print("^C")
                except Exception as e:
                    logger.error(f"Unexpected error in command loop: {e}", exc_info=True)
                    print(f"Unexpected error: {e}")
        except Exception as e:
            logger.error(f"Fatal error in shell loop: {e}", exc_info=True)
            print(f"Fatal error: {e}")
        finally:
            self._debug_log("Cleaning up shell")
            try:
                self.shell.postloop()
                self._debug_log("Postloop completed")
            except Exception as e:
                logger.error(f"Error during shell cleanup: {e}", exc_info=True)
            
    def stop(self):
        """Stop the shell loop"""
        self.running = False
