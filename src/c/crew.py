from c.tools import github_tools
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from c.tools.github_tools import get_github_repos_tool, clone_github_repo_tool, get_repo_info_tool
from c.tools.dependency_tools import extract_project_dependencies
import os
from c.tools.analyze_python_ast import generate_ast_usage_pdf


@CrewBase
class Automation():
    """Automation crew"""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def github_manager(self) -> Agent:
        return Agent(
            config=self.agents_config['github_manager'], # type: ignore[index]
            tools=[get_github_repos_tool, clone_github_repo_tool, get_repo_info_tool],
            verbose=True
        )
    
    @agent
    def dependency_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['dependency_agent'],  # from agent.yaml
            tools=[extract_project_dependencies],
            verbose=True
        )
    @agent
    def python_ast_parser(self) -> Agent:
        return Agent(
            config=self.agents_config['python_ast_parser'],
            tools=[generate_ast_usage_pdf],
            verbose=True
        )
    

    @task
    def clone_repositories_task(self) -> Task:
        return Task(
            config=self.tasks_config['clone_repositories_task'], # type: ignore[index]
            agent=self.github_manager(),
            # tools=[get_github_repos_tool, clone_github_repo_tool, get_repo_info_tool]
        )
    @task
    def clone_single_repo_task(self) -> Task:
        return Task(
            config=self.tasks_config['clone_single_repo_task'],  # 👈 from YAML
            agent=self.github_manager(),
        )

    @task
    def extract_dependencies_task(self) -> Task:
        return Task(
            config=self.tasks_config['extract_dependencies_task'],  # from task.yaml
            agent=self.dependency_agent(),
            # tools=[extract_project_dependencies]
        )
    @task
    def extract_imports_task(self) -> Task:
        return Task(
            config=self.tasks_config['extract_imports_task'],
            agent=self.python_ast_parser()
        )

    @crew
    def crew(self) -> Crew:
        tasks = []

        # Choose tasks dynamically based on inputs (only works if you modify `main.py` accordingly)
        repo_url = os.getenv("REPO_URL")
        if repo_url:
            tasks.append(self.clone_single_repo_task())
        else:
            tasks.append(self.clone_repositories_task())

        tasks.append(self.extract_dependencies_task())
        tasks.append(self.extract_imports_task())

        return Crew(
            agents=[self.github_manager(), self.dependency_agent(),self.python_ast_parser()],
            tasks=tasks,
            process=Process.sequential,
            verbose=True,
        )
