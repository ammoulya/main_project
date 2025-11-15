import os
from crewai.tools import tool

import subprocess
import requests
from urllib.parse import urlparse
from typing import Dict, List


GITHUB_TOKEN =os.getenv("GITHUB_TOKEN")
@tool
def get_github_repos_tool(account: str) -> List[Dict]:
    """Useful for fetching public & private repositories from a GitHub user or organization.
    
    Args:
        account (str): GitHub username or organization name
    """
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    # Check if the account is an organization
    org_api = f"https://api.github.com/orgs/{account}"
    org_response = requests.get(org_api, headers=headers)
    
    if org_response.status_code == 200:
        # Organization: fetch both public & private repos (if accessible)
        api_url = f"https://api.github.com/orgs/{account}/repos?type=all"
    else:
        # User: fetch all repos (including private ones if authenticated)
        api_url = "https://api.github.com/user/repos"

    repos = []
    page = 1
    while True:
        response = requests.get(api_url, headers=headers, params={"page": page, "per_page": 100})
        
        if response.status_code != 200:
            return [{"error": response.json().get("message", "Unknown error")}]
        
        data = response.json()
        if not data:
            break
        
        for repo in data:
            repo_info = {
                "name": repo['name'],
                "language": repo.get('language', 'Unknown'),
                "stars": repo['stargazers_count'],
                "forks": repo['forks_count'],
                "watchers": repo['watchers_count'],
                "updated_at": repo['updated_at'],
                "private": repo['private'],
                "clone_url": repo['clone_url'],
                "ssh_url": repo['ssh_url']
            }
            repos.append(repo_info)
        
        page += 1
    
    return repos

@tool
def clone_github_repo_tool(repo: Dict, destination_folder: str, github_account: str) -> str:
    """Useful for cloning a GitHub repository (public or private).
    
    Args:
        repo (Dict): Repository information dictionary
        destination_folder (str): Local directory path where to clone the repository
        github_account (str): GitHub username or organization name
    """
    os.makedirs(destination_folder, exist_ok=True)
    clone_path = os.path.join(destination_folder, repo["name"])
    
    if os.path.exists(clone_path):
        return f"✅ Repository '{repo['name']}' already exists at {clone_path}"
    
    # Use HTTPS authentication for private repos
    if repo['private']:
        repo_url = f"https://{GITHUB_TOKEN}@github.com/{github_account}/{repo['name']}.git"
    else:
        repo_url = repo["clone_url"]

    try:
        result = subprocess.run(
            ["git", "clone", repo_url, clone_path],
            capture_output=True,
            text=True,
            check=True
        )
        return f"✅ Successfully cloned {repo['name']} into {clone_path}"
    except subprocess.CalledProcessError as e:
        return f"❌ Failed to clone {repo['name']}: {e.stderr or e.stdout}"

@tool
def get_repo_info_tool(repo_url: str) -> Dict:
    """Useful for getting information about a specific GitHub repository.
    
    Args:
        repo_url (str): The full URL of the GitHub repository
    """
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    # Parse the GitHub URL
    parsed = urlparse(repo_url)
    if not parsed.netloc == 'github.com':
        return {"error": "Invalid GitHub URL"}
    
    path_parts = parsed.path.strip('/').split('/')
    if len(path_parts) < 2:
        return {"error": "Invalid GitHub URL"}
    
    owner, repo_name = path_parts[0], path_parts[1].replace('.git', '')
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        repo = response.json()
        
        return {
            "name": repo['name'],
            "language": repo.get('language', 'Unknown'),
            "stars": repo['stargazers_count'],
            "forks": repo['forks_count'],
            "watchers": repo['watchers_count'],
            "updated_at": repo['updated_at'],
            "private": repo['private'],
            "clone_url": repo['clone_url'],
            "ssh_url": repo['ssh_url'],
            "owner": owner
        }
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def cache_repo_clone(args: dict, result: str) -> bool:
    """Determine whether to cache the clone operation result."""
    return "Successfully" in result

# Add caching function to clone_github_repo_tool
clone_github_repo_tool.cache_function = cache_repo_clone

# Export tools
__all__ = ['get_github_repos_tool', 'clone_github_repo_tool', 'get_repo_info_tool']