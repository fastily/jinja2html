import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="jinja2html",
    version="0.5.0",
    author="Fastily",
    author_email="fastily@users.noreply.github.com",
    description="user-friendly generation of websites with jinja2 templates",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/fastily/jinja2html",
    project_urls={
        "Bug Tracker": "https://github.com/fastily/jinja2html/issues",
    },
    include_package_data=True,
    packages=setuptools.find_packages(include=["jinja2html"]),
    install_requires=['beautifulsoup4', 'Jinja2', 'lxml', 'rich', 'starlette', 'uvicorn[standard]'],
    entry_points={
        'console_scripts': [
            'jinja2html = jinja2html.__main__:_main'
        ]
    },
    classifiers=[
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9',
)
