import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="jinja2html",
    version="0.2.1",
    author="Fastily",
    author_email="fastily@users.noreply.github.com",
    description="friendly generation of websites with jinja2 templates",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/fastily/jinja2html",
    include_package_data=True,
    packages=setuptools.find_packages(),
    install_requires=['beautifulsoup4', 'Jinja2', 'lxml', 'watchdog', 'websockets'],
    entry_points={
        'console_scripts': [
            'jinja2html = jinja2html:__main__.main'
        ]
    },
    classifiers=[
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
