"""KOS Package Manager Repository Configuration"""
import json
import os
from datetime import datetime
import requests  # Import requests here


class RepositoryConfig:

    def __init__(self):
        self.config_file = "kos_repos.json"
        self.repos = {"repositories": {}}
        self._load_repos()

    def _load_repos(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    self.repos = json.load(f)
        except Exception as e:
            print(f"Error loading repositories: {e}")

    def _save_config(self):
        with open(self.config_file, "w") as f:
            json.dump(self.repos, f, indent=2)

    def add_repository(self, url: str) -> bool:
        try:
            name = url.split('/')[-1]
            self.repos["repositories"][name] = {
                "url": url,
                "enabled": True,
                "last_update": datetime.now().isoformat()
            }
            self._save_config()
            return True
        except Exception as e:
            print(f"Failed to add repository {url}: {e}")
            return False

    def remove_repository(self, name: str) -> bool:
        if name in self.repos["repositories"]:
            del self.repos["repositories"][name]
            self._save_config()
            return True
        return False

    def list_repositories(self):
        return [{
            "name": name,
            **repo
        } for name, repo in self.repos["repositories"].items()]

    def update_repository(self, name: str) -> bool:
        print(
            f"DEBUG: update_repository called for repo: {name}")  # DEBUG PRINT
        if name not in self.repos["repositories"]:
            print(f"Repository '{name}' not found.")
            return False

        repo_url = self.repos["repositories"][name]["url"]
        print(f"DEBUG: Fetching index.json from: {repo_url}/repo/index.json"
              )  # DEBUG PRINT
        try:
            response = requests.get(f"{repo_url}/repo/index.json")
            print(f"DEBUG: Response status code: {response.status_code}"
                  )  # DEBUG PRINT
            if response.status_code == 200:
                raw_content = response.text  # Get raw text content
                print(f"DEBUG: Raw index.json content:\n{raw_content}"
                      )  # DEBUG PRINT - PRINT RAW CONTENT
                try:
                    response.json(
                    )  # Try parsing JSON again (for error message)
                except json.JSONDecodeError as json_error:
                    print(f"DEBUG: JSON Parse Error: {json_error}"
                          )  # Print specific JSON error
                # In a real implementation, you would process the index.json here
                self.repos["repositories"][name]["last_update"] = datetime.now(
                ).isoformat()
                self._save_config()
                print(f"Repository '{name}' updated.")
                return True
            else:
                print(
                    f"Failed to update repository '{name}' from {repo_url}: HTTP {response.status_code}"
                )
                return False
        except requests.exceptions.RequestException as e:
            print(f"Failed to update repository '{name}' from {repo_url}: {e}")
            return False
