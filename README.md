# jinja2html
[![Build Status](https://github.com/fastily/jinja2html/workflows/build/badge.svg)](#)
[![Python 3.11+](https://upload.wikimedia.org/wikipedia/commons/6/62/Blue_Python_3.11%2B_Shield_Badge.svg)](https://www.python.org)
[![License: GPL v3](https://upload.wikimedia.org/wikipedia/commons/8/86/GPL_v3_Blue_Badge.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)

jinja2html takes your jinja2 templates and outputs HTML.

More importantly, it supports developer-friendly live reloading so that you can create that masterpiece of a static website without ripping your hair out.

### Why jinja2html?

Blogging frameworks are a *dime a dozen*.  But what if you don't want to write a blog?  What if you wanted to make a static landing page, but without all that client-heavy nonsense like React/Vue/Angular/etc?  

That's where jinja2html comes in.

No fancy bells and whistles, no bull$hit, just your bold artistic vision + jinja2html.

## Install
```bash
pip install jinja2html
```

This installs the CLI command, `jinja2html`, which can be used to generate html or start the local development server.

## Usage
```
usage: __main__.py [-h] [-d] [-p port] [-i input_dir] [-o output_dir] [-t template_dir] [--debug] [--ignore ignored_dir [ignored_dir ...]]

Render jinja2 templates as html/css/js

optional arguments:
  -h, --help            show this help message and exit
  -d                    enable development mode (live-reload)
  -p port               serve website on this port
  -i input_dir          The input directory (contianing jinja templates) to use. Defaults to the current working directory.
  -o output_dir         The output directory to write website output files to. Defaults to ./out
  -t template_dir       Shared templates directory (relative path only, this must be a subfolder of the input directory). Defaults to templates
  --debug               Enables debug level logging
  --ignore ignored_dir [ignored_dir ...]
                        directories to ignore
```

#### Examples
```bash
# generate html files for use in prod
jinja2html

# run in dev mode, in the current directory
jinja2html -d

# generate html files for use in prod and ignore folders Foo/ and Bar/
jinja2html -d --ignore Foo/ Bar/

# run in dev mode, on port 8080 and ignore folder hello/world/
jinja2html -d -p 8080 --ignore hello/world/
```

See [here](tests/resources/sample_project/) for an example project

## Scope
jinja2html is designed for small and simple static websites.  If you're trying to do something big and complex, then you should stick with the tooling of a conventional front-end framework.