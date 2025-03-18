#!/usr/bin/env python3
from kos.commands import KaedeShell
from kos.filesystem import FileSystem
from kos.package_manager import KappManager
from kos.user_system import UserSystem

def main():
    # Initialize core systems
    filesystem = FileSystem(disk_size_mb=100)
    kapp_manager = KappManager()
    user_system = UserSystem()

    # Start the shell
    shell = KaedeShell(filesystem, kapp_manager, user_system)
    shell.cmdloop()

if __name__ == "__main__":
    main()