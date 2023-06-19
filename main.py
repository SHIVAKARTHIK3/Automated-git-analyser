from flask import Flask, request, render_template
import requests
import re
import os
import shutil
import subprocess
from github import Github
import openai

app = Flask(__name__)

# GitHub API token
GITHUB_TOKEN = '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'

# OpenAI API token
OPENAI_API_KEY = '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'

# Set up GitHub and OpenAI clients
github_client = Github(GITHUB_TOKEN)
openai.api_key = OPENAI_API_KEY


# Home page
@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')


# Result page
@app.route('/result', methods=['POST'])
def result():
    github_url = request.form['github_url']
    repositories = fetch_user_repositories(github_url)
    most_complex_repo, gpt_analysis = identify_complex_repository(repositories)
    return render_template('result.html', repo_link=most_complex_repo, gpt_analysis=gpt_analysis)


# Function to fetch repositories from GitHub user URL
def fetch_user_repositories(github_url):
    username = re.search('github.com/(.*)', github_url).group(1)
    user = github_client.get_user(username)
    repositories = user.get_repos()
    return repositories


# Function to clone repository locally
def clone_repository(repository):
    repo_name = repository.name
    clone_url = repository.clone_url

    # Clone repository using git
    subprocess.call(['git', 'clone', clone_url])

    return repo_name


# Function to preprocess code files in a repository
def preprocess_repository(repo_name):
    repo_path = os.path.join(os.getcwd(), repo_name)
    files = []
    for root, _, filenames in os.walk(repo_path):
        for filename in filenames:
            if filename.endswith('.ipynb') or filename.endswith('.py'):
                files.append(os.path.join(root, filename))

    for file_path in files:
        # Check file size and split if necessary
        if os.path.getsize(file_path) > 50000:
            split_file(file_path)

        # Remove large Jupyter notebooks
        if file_path.endswith('.ipynb'):
            os.remove(file_path)


# Function to split large code files into smaller chunks
def split_file(file_path):
    file_dir, file_name = os.path.split(file_path)
    split_dir = os.path.join(file_dir, file_name + '_split')

    os.makedirs(split_dir, exist_ok=True)

    # Split the file into smaller chunks
    subprocess.call(['split', '-l', '1000', file_path, os.path.join(split_dir, 'split_')])

    # Remove the original large file
    os.remove(file_path)

    # Move the split files to the original directory
    for split_file in os.listdir(split_dir):
        shutil.move(os.path.join(split_dir, split_file), file_dir)

    # Remove the split directory
    os.rmdir(split_dir)


# Function to evaluate technical complexity using GPT
def evaluate_complexity(code):
    prompt = """
    This code is evaluated based on its technical complexity.

    Code:
    """

    # Combine prompt and code
    prompt += code

    # Generate response using OpenAI GPT
    response = openai.Completion.create(
        engine='text-davinci-003',
        prompt=prompt,
        max_tokens=100,
        temperature=0.7,
        n=1,
        stop=None
    )

    return response.choices[0].text.strip()


# Function to identify the most technically complex repository
def identify_complex_repository(repositories):
    most_complex_repo = None
    max_complexity_score = float('-inf')
    gpt_analysis = ""

    for repository in repositories:
        repo_name = clone_repository(repository)
        preprocess_repository(repo_name)

        complexity_score = 0

        # Calculate complexity score for each code file
        for root, _, filenames in os.walk(repo_name):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        code = file.read()
                except:
                    with open(file_path, 'r', encoding='latin-1') as file:
                        code = file.read()

                complexity_score += len(code)

                    #Perform prompt engineering
                prompt_analysis = evaluate_complexity(code)
                gpt_analysis += f"\n\nAnalysis for {filename}:\n{prompt_analysis}"

        if complexity_score > max_complexity_score:
            max_complexity_score = complexity_score
            most_complex_repo = repository.html_url

    return most_complex_repo, gpt_analysis


if __name__ == '__main__':
    app.run(debug=True)