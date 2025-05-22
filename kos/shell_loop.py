"""
Custom shell loop implementation for KOS to prevent unwanted exits
"""
import sys
import traceback
import logging
from typing import Any, Optional

# Set up logging
logger = logging.getLogger('KOS.shell_loop')
logger.setLevel(logging.DEBUG)

# Create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

class ShellLoop:
    """Custom shell loop implementation to prevent unwanted exits"""
    
    def __init__(self, shell):
        self.shell = shell
        self.running = True
        
    def run(self):
        """Run the main shell loop"""
        logger.debug("Starting shell loop")
        self.shell.preloop()
        logger.debug("After preloop")
        
        try:
            logger.debug("Entering main shell loop")
            while self.running:
                try:
                    logger.debug("Starting new command cycle")
                    
                    # Get command input
                    if self.shell.cmdqueue:
                        line = self.shell.cmdqueue.pop(0)
                        logger.debug(f"Got command from queue: {line}")
                    else:
                        if self.shell.use_rawinput:
                            try:
                                logger.debug("Waiting for user input")
                                line = input(self.shell.prompt)
                                logger.debug(f"User input: {line}")
                                if not line.strip():
                                    logger.debug("Empty input, skipping")
                                    continue
                            except (EOFError, KeyboardInterrupt):
                                logger.debug("Caught KeyboardInterrupt or EOF")
                                print("^C")
                                continue
                        else:
                            logger.debug("Reading from non-interactive input")
                            line = sys.stdin.readline()
                            if not line:
                                logger.debug("No more input, breaking")
                                break
                    
                    # Process the command
                    logger.debug(f"Processing command: {line}")
                    try:
                        line = self.shell.precmd(line)
                        logger.debug(f"After precmd: {line}")
                        stop = self.shell.onecmd(line)
                        logger.debug(f"After onecmd, stop={stop}")
                        stop = self.shell.postcmd(stop, line)
                        logger.debug(f"After postcmd, stop={stop}")
                        
                        # Reset stop to prevent exit
                        if stop:
                            logger.debug("Stop flag set, exiting shell loop")
                            self.running = False
                    except Exception as e:
                        logger.error(f"Error processing command: {e}", exc_info=True)
                        print(f"Error: {e}")
                    
                except SystemExit as e:
                    # Handle exit command
                    logger.debug(f"SystemExit caught with code: {e.code}")
                    break
                    
                except Exception as e:
                    logger.error(f"Unexpected error in command loop: {e}", exc_info=True)
                    print(f"Error: {e}")
                    continue
                    
        except Exception as e:
            logger.critical(f"Critical error in shell loop: {e}", exc_info=True)
            raise
            
        finally:
            logger.debug("Cleaning up shell")
            try:
                self.shell.postloop()
                logger.debug("Postloop completed")
            except Exception as e:
                logger.error(f"Error during postloop: {e}", exc_info=True)
            
    def stop(self):
        """Stop the shell loop"""
        self.running = False
