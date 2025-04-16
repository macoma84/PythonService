from setuptools import setup, find_packages
import os

# Function to read requirements from requirements.txt
def read_requirements():
    with open('requirements.txt') as f:
        return f.read().splitlines()

# Extract version from environment variable set by GitHub Actions
version = os.environ.get('RELEASE_VERSION', '0.1.0') # Default version if not set

setup(
    name='PythonService',
    version=version,
    author='Mariano',
    author_email='macoma84@gmail.com',
    description='A FastAPI service packaged as a .deb file.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/macoma84/PythonService', # Replace with your repo URL
    packages=find_packages(exclude=['__pycache__']), # Automatically find packages
    include_package_data=True, # Include non-code files specified in MANIFEST.in (if any)
    install_requires=read_requirements(), # Read dependencies from requirements.txt
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: MIT License', # Choose your license
        'Operating System :: OS Independent',
        'Framework :: FastAPI',
    ],
    python_requires='>=3.10', # Specify compatible Python versions
    # If your application has a command-line entry point, define it here
    # entry_points={
    #     'console_scripts': [
    #         'python-service=main:app', # Example: command=module:function
    #     ],
    # },
)